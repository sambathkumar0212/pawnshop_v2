from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from accounts.models import Customer  # Import Customer from accounts app
from schemes.models import Scheme  # Changed from content_manager.models to schemes.models
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import datetime
import json
from .utils import item_photo_path, loan_document_path
from utils.default_photos import get_default_person_photo, get_default_item_photo

class Loan(models.Model):
    """Pawn loan model"""
    # Loan ID with prefix for easier identification
    loan_number = models.CharField(
        max_length=50, 
        unique=True,
        null=False,  # Ensure null is not allowed
        blank=False, # Ensure blank is not allowed
        help_text="Unique loan identifier"
    )
    
    # Customer and branch relationships
    customer = models.ForeignKey('accounts.Customer', on_delete=models.PROTECT, related_name='loans')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT, related_name='loans')
    items = models.ManyToManyField('inventory.Item', through='LoanItem')
    scheme = models.ForeignKey('schemes.Scheme', on_delete=models.PROTECT, null=True, blank=True)
    
    # Status choices
    STATUS_CHOICES = (
        ('active', _('Active')),
        ('repaid', _('Repaid')),
        ('defaulted', _('Defaulted')),
        ('extended', _('Extended')),
        ('foreclosed', _('Foreclosed')),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Financial details
    principal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(0)]
    )
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12.00)
    processing_fee = models.IntegerField(
        validators=[MinValueValidator(0)],
        default=0,
        help_text="Processing fee amount in whole Rupees"
    )
    distribution_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(0)]
    )
    
    # Important dates
    issue_date = models.DateField()
    due_date = models.DateField()
    grace_period_end = models.DateField()
    
    # Customer verification and photos
    customer_face_capture = models.TextField(blank=True, null=True, help_text="Base64-encoded customer photo")
    item_photos = models.JSONField(default=list, blank=True, help_text="List of photo URLs or base64 data")
    
    # Loan documents with custom naming
    loan_document = models.FileField(
        upload_to=loan_document_path,
        blank=True,
        null=True,
        help_text="Upload loan agreement or related documents. File will be named using customer and item names."
    )
    is_first_month_interest_paid = models.BooleanField(
        default=False,
        verbose_name=_("Is first month interest paid?"),
        help_text=_("Check if first month interest is paid/collected upfront")
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='loans_created'
    )
    
    class Meta:
        verbose_name = _('loan')
        verbose_name_plural = _('loans')
        ordering = ['-created_at']
        permissions = [
            ("can_approve_loan", "Can approve loan"),
            ("can_extend_loan", "Can extend loan"),
            ("can_foreclose_loan", "Can foreclose loan"),
        ]

    def __str__(self):
        return f"Loan #{self.loan_number} - {self.customer.full_name}"
    
    @property
    def monthly_interest(self):
        """Calculate monthly interest details for the loan.
        
        Returns a dictionary with monthly interest rate, amount, and per thousand rate
        """
        from decimal import Decimal
        
        # Calculate monthly interest rate (annual rate / 12)
        if self.scheme and self.scheme.interest_rate_structure:
            # Use the lowest/first tier rate (interest rate for 30 days)
            annual_rate = Decimal(str(self.scheme.get_interest_rate_for_days(30)))
            monthly_rate = annual_rate / Decimal('12')
        else:
            monthly_rate = Decimal(self.interest_rate) / Decimal('12')
        
        # Calculate monthly interest amount based on base distribution amount (principal - processing fee)
        base_dist_amount = self.principal_amount - Decimal(str(self.processing_fee))
        monthly_amount = (base_dist_amount * monthly_rate) / Decimal('100')
        
        # Calculate rate per 1000 of distribution amount
        per_thousand = (monthly_rate * Decimal('10')) # per Rs. 1,000
        
        return {
            'rate': round(monthly_rate, 2),
            'amount': round(monthly_amount, 2),
            'per_thousand': round(per_thousand, 2)
        }
    
    @property
    def is_overdue(self):
        # A loan is overdue if the due date has passed and it's still active
        return self.status == 'active' and self.due_date < timezone.now().date()
    
    @property
    def days_since_issue(self):
        # Number of days since the loan was issued
        return (timezone.now().date() - self.issue_date).days
    
    @property
    def days_remaining(self):
        # Number of days remaining until the due date
        if self.due_date >= timezone.now().date():
            return (self.due_date - timezone.now().date()).days
        return 0

    @property
    def original_distribution_amount(self):
        """Returns the original distribution amount (principal - processing fee) before any upfront interest deductions"""
        from decimal import Decimal
        return self.principal_amount - Decimal(str(self.processing_fee or 0))

    def save(self, *args, **kwargs):
        # Check if this is a creation
        is_create = self.pk is None
        
        # Generate loan number if not provided
        if not self.loan_number:
            self.loan_number = self.generate_loan_number()
        
        # Ensure item_photos is stored as JSON in database
        if isinstance(self.item_photos, list):
            try:
                self.item_photos = json.dumps(self.item_photos)
            except Exception as e:
                print(f"Error converting item_photos to JSON: {e}")
                self.item_photos = "[]"  # Default to empty JSON array
        
        # Ensure item_photos is a valid JSON string if it's a string
        if isinstance(self.item_photos, str) and not self.item_photos.startswith('data:image/') and not self.item_photos.startswith('['):
            try:
                # Validate JSON format
                json.loads(self.item_photos)
            except json.JSONDecodeError:
                # If not valid JSON, reset to empty array
                print("Invalid JSON in item_photos, resetting to empty array")
                self.item_photos = "[]"
        
        # If item_photos is a base64 string, convert to JSON array
        if isinstance(self.item_photos, str) and self.item_photos.startswith('data:image/'):
            self.item_photos = json.dumps([self.item_photos])
        
        super().save(*args, **kwargs)
        
        # Delay email until after the full DB transaction commits (including LoanItem rows)
        # so the PDF always reflects the latest gold item details.
        loan_id = self.pk
        _is_create = is_create
        
        def _send_notification():
            try:
                from transactions.models import Loan
                loan = Loan.objects.get(pk=loan_id)
                loan.send_loan_notification_email(_is_create)
            except Exception as e:
                import traceback
                print(f"Error sending loan email notification: {str(e)}")
                traceback.print_exc()
        
        from django.db import transaction
        transaction.on_commit(_send_notification)

    def send_loan_notification_email(self, is_create):
        """Send email notification on loan creation or edit to firstmoneygold@gmail.com and hariswealthway@gmail.com"""
        from django.core.mail import EmailMessage
        from django.conf import settings

        action = "Created" if is_create else "Edited"
        subject = f"Loan {action}: {self.loan_number} - {self.customer.first_name} {self.customer.last_name}"
        recipients = ["firstmoneygold@gmail.com", "hariswealthway@gmail.com"]
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@myapp.com')

        body = (
            f"Dear Team,\n\n"
            f"A loan has been {action.lower()} with the following details:\n\n"
            f"Loan Number: {self.loan_number}\n"
            f"Customer Name: {self.customer.first_name} {self.customer.last_name}\n"
            f"Branch: {self.branch.name if self.branch else 'N/A'}\n"
            f"Scheme: {self.scheme.name if self.scheme else 'N/A'}\n"
            f"Principal Amount: Rs. {self.principal_amount}\n"
            f"Interest Rate: {self.interest_rate}%\n"
            f"Status: {self.get_status_display()}\n"
            f"Issue Date: {self.issue_date}\n"
            f"Due Date: {self.due_date}\n"
            f"Created/Modified At: {self.updated_at or self.created_at or 'N/A'}\n\n"
            f"Please find the loan agreement PDF attached.\n\n"
            f"Best regards,\n"
            f"Pawnshop Management System"
        )

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=recipients,
        )

        # Attach the loan agreement PDF if it can be generated
        try:
            pdf_bytes, pdf_filename = self.generate_loan_pdf_bytes()
            if pdf_bytes:
                email.attach(pdf_filename, pdf_bytes, 'application/pdf')
        except Exception as e:
            print(f"Could not attach PDF to loan notification email: {e}")

        email.send(fail_silently=False)

    def generate_loan_pdf_bytes(self):
        """Generate loan agreement PDF bytes using headless Chromium (with xhtml2pdf fallback).
        Returns a tuple of (pdf_bytes, filename)."""
        import os
        import re
        import shutil
        import subprocess
        import tempfile
        from django.template.loader import get_template
        from django.conf import settings
        from django.utils.text import slugify

        loan_items = self.loanitem_set.all()

        # Build filename
        customer_name = ""
        if self.customer:
            customer_name = slugify(f"{self.customer.first_name}_{self.customer.last_name}").replace('-', '_')
        item_names = [slugify(li.item.name).replace('-', '_') for li in loan_items if li.item and li.item.name] or ['gold_item']
        items_part = '_'.join(item_names[:2])
        if customer_name and items_part:
            filename_base = f"{customer_name}_{items_part}_{self.loan_number}_agreement"
        elif customer_name:
            filename_base = f"{customer_name}_{self.loan_number}_agreement"
        else:
            filename_base = f"loan_{self.loan_number}_agreement"
        filename_base = re.sub(r'[^a-zA-Z0-9_-]', '_', filename_base)[:200]
        pdf_filename = f"{filename_base}.pdf"

        # Build template context — inline photo processing to avoid circular model→views import
        raw_photos = self.item_photos
        if not raw_photos:
            processed_photos = []
        elif isinstance(raw_photos, str) and raw_photos.startswith('data:image/'):
            processed_photos = [raw_photos]
        elif isinstance(raw_photos, str) and raw_photos.startswith('['):
            try:
                processed_photos = json.loads(raw_photos)
            except Exception:
                processed_photos = []
        elif isinstance(raw_photos, list):
            processed_photos = raw_photos
        else:
            processed_photos = []
        item_photos = []
        for photo in processed_photos:
            if photo.startswith('data:image/'):
                item_photos.append(photo.split(',')[1] if ',' in photo else photo)
            else:
                item_photos.append(photo)

        customer_photo = None
        if self.customer_face_capture:
            customer_photo = (self.customer_face_capture.split(',')[1]
                              if self.customer_face_capture.startswith('data:image/')
                              else self.customer_face_capture)

        context = {
            'loan': self,
            'loan_items': loan_items,
            'item_photos': item_photos,
            'customer_photo': customer_photo,
            'tamil_font_file_uri': f"file:///{str((settings.BASE_DIR / 'static' / 'fonts' / 'NotoSansTamil-Regular.ttf')).replace(os.sep, '/')}",
            'pdf_renderer': 'browser',
        }

        # Merge language-specific labels (lazy import to avoid circular dependency)
        try:
            from transactions.views import build_loan_pdf_language_context
            language_context = build_loan_pdf_language_context(self, 'en')
            context.update(language_context)
        except Exception as e:
            print(f"Could not build PDF language context: {e}")

        template = get_template('transactions/loan_document_pdf.html')
        html = template.render(context)

        # Try headless Chromium first
        browser = None
        for candidate in [
            shutil.which('chrome'),
            shutil.which('msedge'),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]:
            if candidate and os.path.exists(candidate):
                browser = candidate
                break

        if browser:
            tmp_dir = tempfile.mkdtemp(prefix='loan_pdf_email_')
            try:
                html_path = os.path.join(tmp_dir, 'loan_document.html')
                pdf_path = os.path.join(tmp_dir, 'loan_document.pdf')
                profile_dir = os.path.join(tmp_dir, 'profile')
                os.makedirs(profile_dir, exist_ok=True)
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                cmd = [
                    browser,
                    "--headless=new", "--disable-gpu", "--no-sandbox",
                    f"--user-data-dir={profile_dir}",
                    "--allow-file-access-from-files", "--disable-web-security",
                    "--print-to-pdf-no-header",
                    f"--print-to-pdf={pdf_path}",
                    f"file:///{html_path.replace(os.sep, '/')}",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                if result.returncode == 0 and os.path.exists(pdf_path):
                    with open(pdf_path, 'rb') as f:
                        pdf_bytes = f.read()
                    if pdf_bytes:
                        return pdf_bytes, pdf_filename
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        # Fallback: xhtml2pdf
        from io import BytesIO
        try:
            from xhtml2pdf import pisa
            buffer = BytesIO()
            pisa.CreatePDF(html, dest=buffer)
            pdf_bytes = buffer.getvalue()
            if pdf_bytes:
                return pdf_bytes, pdf_filename
        except ImportError:
            pass

        return None, pdf_filename

    def generate_loan_number(self):
        """Generate a unique loan number"""
        import random
        import string
        from django.utils import timezone
        
        # Get current date components
        now = timezone.now()
        year = now.year
        month = now.month
        day = now.day
        
        # Get branch code (first 3 letters of branch name, or 'DEF' if no branch)
        branch_code = 'DEF'
        if self.branch and self.branch.name:
            branch_code = ''.join([c.upper() for c in self.branch.name if c.isalpha()])[:3]
            if len(branch_code) < 3:
                branch_code = (branch_code + 'DEF')[:3]
        
        # Format: BRANCH-YYYYMMDD-XXXX (where XXXX is a 4-digit sequential number)
        date_str = f"{year:04d}{month:02d}{day:02d}"
        base_number = f"{branch_code}-{date_str}"
        
        # Find the highest existing loan number for today
        existing_loans = Loan.objects.filter(
            loan_number__startswith=base_number,
            created_at__date=now.date()
        ).order_by('-loan_number')
        
        # Generate sequential number
        if existing_loans.exists():
            last_loan_number = existing_loans.first().loan_number
            try:
                # Extract the last 4 digits and increment
                last_sequence = int(last_loan_number.split('-')[-1])
                new_sequence = last_sequence + 1
            except (ValueError, IndexError):
                new_sequence = 1
        else:
            new_sequence = 1
        
        # Format the final loan number
        final_loan_number = f"{base_number}-{new_sequence:04d}"
        
        # Double-check uniqueness (in case of race conditions)
        while Loan.objects.filter(loan_number=final_loan_number).exists():
            new_sequence += 1
            final_loan_number = f"{base_number}-{new_sequence:04d}"
        
        return final_loan_number

    @property
    def amount_paid(self):
        """Calculate total amount paid on this loan"""
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    @property
    def remaining_balance(self):
        """Calculate remaining balance including interest"""
        return max(Decimal('0.00'), self.total_payable_mature - self.amount_paid)

    def calculate_months_date_to_date(self, target_date=None):
        """
        Calculates month date-to-date count relative to issue_date.
        For example: if loan issue_date is 20th of July:
        - July 20 to August 20 is Month 1.
        - Crossing August 20 enters Month 2 cycle.
        """
        if not self.issue_date:
            return 1
            
        if target_date is None:
            target_date = timezone.now().date()
            
        if target_date <= self.issue_date:
            return 1
            
        months_diff = (target_date.year - self.issue_date.year) * 12 + (target_date.month - self.issue_date.month)
        
        if target_date.day > self.issue_date.day:
            months_count = months_diff + 1
        elif target_date.day == self.issue_date.day:
            months_count = max(1, months_diff)
        else:
            months_count = max(1, months_diff)
            
        return max(1, months_count)

    @property
    def net_payable_still_due(self):
        """Calculate net payable (still due) - what customer owes right now including minimum interest"""
        if self.status != 'active' or not self.scheme:
            return max(Decimal('0.00'), self.principal_amount - self.amount_paid)
        
        principal = self.principal_amount
        monthly_info = self.monthly_interest
        monthly_amount = Decimal(str(monthly_info['amount']))
        
        months_count = Decimal(str(self.calculate_months_date_to_date()))
        
        # Calculate total interest
        if self.is_first_month_interest_paid:
            months_count = max(Decimal('0'), months_count - Decimal('1'))
            
        total_interest = monthly_amount * months_count
        
        # Total payable is principal + interest till date
        total_payable = principal + total_interest
        
        # Net payable is what's still due after payments
        return max(Decimal('0.00'), total_payable - self.amount_paid)
    
    @property
    def days_since_issue(self):
        """Calculate number of days since loan was issued"""
        if not self.issue_date:
            return 0
        return (timezone.now().date() - self.issue_date).days

    @property
    def days_remaining(self):
        """Calculate number of days remaining until due date"""
        if not self.due_date:
            return 0
        remaining = (self.due_date - timezone.now().date()).days
        return max(0, remaining)

    @property
    def is_overdue(self):
        """Check if loan is overdue"""
        if not self.due_date:
            return False
        return timezone.now().date() > self.due_date and self.status == 'active'

    @property
    def total_payable_till_date(self):
        """Calculate total amount payable including interest till today"""
        if self.status != 'active':
            return Decimal('0.00')
        
        principal_amount = self.principal_amount
        
        # Get scheme details from the scheme model
        if not self.scheme:
            return principal_amount
            
        # For schemes with no_interest_period_days, check if we're still in that period
        if self.scheme.no_interest_period_days and self.days_since_issue <= self.scheme.no_interest_period_days:
            return principal_amount
            
        # Use monthly interest calculation instead of daily
        return principal_amount + self.monthly_interest_till_date()

    @property
    def total_payable_mature(self):
        """Calculate total amount payable at maturity using date-to-date month cycle"""
        if not self.due_date or self.status != 'active' or not self.scheme:
            return Decimal('0.00')
        
        principal_amount = self.principal_amount
        
        # For schemes with no_interest_period_days, check if loan duration is within that period
        if self.scheme.no_interest_period_days and (self.due_date - self.issue_date).days <= self.scheme.no_interest_period_days:
            return principal_amount
            
        months = self.calculate_months_date_to_date(self.due_date)
            
        # Adjust for first month interest paid upfront
        if self.is_first_month_interest_paid:
            months = max(0, months - 1)
            
        # Calculate interest using monthly rate
        monthly_info = self.monthly_interest
        monthly_amount = monthly_info['amount']
        total_interest = monthly_amount * Decimal(str(months))
        
        return principal_amount + total_interest
    
    def calculate_interest(self):
        """Calculate interest on loan"""
        if not self.due_date or self.status != 'active' or not self.scheme:
            return Decimal('0.00')
        
        # Use the transaction date for calculating days elapsed
        current_date = timezone.now().date()
        days_elapsed = (current_date - self.issue_date).days
        
        # Adjust for first month interest paid upfront (approx. 30 days)
        if self.is_first_month_interest_paid:
            days_elapsed = max(0, days_elapsed - 30)
            
        # Calculate interest based on scheme interest rate on base distribution amount (principal - processing fee)
        base_dist_amount = self.principal_amount - Decimal(str(self.processing_fee))
        
        # For schemes with no_interest_period_days, check if we're still in that period
        if self.scheme.no_interest_period_days and days_elapsed <= self.scheme.no_interest_period_days:
            return Decimal('0.00')
            
        # Calculate interest based on scheme interest rate on base distribution amount
        daily_rate = self.scheme.interest_rate / Decimal('36500')  # Convert annual rate to daily rate
        interest = base_dist_amount * daily_rate * days_elapsed
        
        return interest
        
    @property
    def monthly_interest(self):
        """Calculate monthly interest rate and amount for the loan"""
        if not self.distribution_amount:
            return {
                'rate': Decimal('0.00'),
                'amount': Decimal('0.00'),
                'per_thousand': Decimal('0.00'),
                'annual_rate': Decimal('0.00')
            }
        
        # Get interest rate from scheme or default
        if not self.scheme:
            annual_rate = Decimal(str(self.interest_rate))
        elif self.issue_date:
            today = timezone.now().date()
            if self.scheme.is_days_based:
                days_elapsed = (today - self.issue_date).days
                annual_rate = self.scheme.get_interest_rate_for_days(days_elapsed)
            else:
                months_elapsed = ((today.year - self.issue_date.year) * 12 + 
                                today.month - self.issue_date.month)
                # Get tiered interest rate based on tenure
                annual_rate = self.scheme.get_interest_rate_for_tenure(months_elapsed)
        else:
            annual_rate = self.scheme.interest_rate
        
        # Calculate monthly interest rate
        monthly_rate = annual_rate / Decimal('12')
        
        # Calculate monthly interest amount based on base distribution amount (principal - processing fee)
        base_dist_amount = self.principal_amount - Decimal(str(self.processing_fee))
        monthly_interest_amount = (base_dist_amount * monthly_rate) / Decimal('100')
        
        # Calculate per thousand rate (how much interest per 1000 of distribution amount)
        per_thousand = (monthly_rate / Decimal('100')) * Decimal('1000')
        
        return {
            'rate': monthly_rate.quantize(Decimal('0.01')),
            'amount': monthly_interest_amount.quantize(Decimal('0.01')),
            'per_thousand': per_thousand.quantize(Decimal('0.01')),
            'annual_rate': annual_rate.quantize(Decimal('0.01'))
        }

    @property
    def daily_interest_amount(self):
        """Calculate daily interest amount for the loan (per single day)"""
        if not self.distribution_amount:
            return Decimal('0.00')
        
        # Get interest rate from scheme or default
        if not self.scheme:
            annual_rate = Decimal(str(self.interest_rate))
        elif self.issue_date:
            today = timezone.now().date()
            if self.scheme.is_days_based:
                days_elapsed = (today - self.issue_date).days
                annual_rate = self.scheme.get_interest_rate_for_days(days_elapsed)
            else:
                months_elapsed = ((today.year - self.issue_date.year) * 12 + 
                                today.month - self.issue_date.month)
                annual_rate = self.scheme.get_interest_rate_for_tenure(months_elapsed)
        else:
            annual_rate = self.scheme.interest_rate
            
        base_dist_amount = self.principal_amount - Decimal(str(self.processing_fee))
        daily_amount = base_dist_amount * (annual_rate / Decimal('36500'))
        return daily_amount.quantize(Decimal('0.01'))

    @property
    def interest_till_date_daily_basis(self):
        """Calculate interest accrued till date calculated on a daily day-by-day basis"""
        if not self.issue_date or not self.scheme:
            return Decimal('0.00')
            
        current_date = timezone.now().date()
        days_elapsed = (current_date - self.issue_date).days
        
        if self.is_first_month_interest_paid:
            days_elapsed = max(0, days_elapsed - 30)
            
        base_dist_amount = self.principal_amount - Decimal(str(self.processing_fee))
        
        if getattr(self.scheme, 'no_interest_period_days', 0) and days_elapsed <= self.scheme.no_interest_period_days:
            return Decimal('0.00')
            
        annual_rate = self.scheme.get_interest_rate_for_days((current_date - self.issue_date).days)
        daily_rate = annual_rate / Decimal('36500')
        interest = base_dist_amount * daily_rate * Decimal(str(days_elapsed))
        return interest.quantize(Decimal('0.01'))

    @property
    def interest_till_date_monthly_basis(self):
        """Calculate interest accrued till date calculated on a monthly cycle-by-cycle basis"""
        if not self.issue_date or not self.scheme:
            return Decimal('0.00')
            
        current_date = timezone.now().date()
        months_elapsed = self.calculate_months_date_to_date(current_date)
        
        if self.is_first_month_interest_paid:
            months_elapsed = max(0, months_elapsed - 1)
            
        monthly_info = self.monthly_interest
        monthly_amount = monthly_info['amount']
        base_interest = monthly_amount * Decimal(str(months_elapsed))
        
        # Add late payment interest if applicable
        if self.is_overdue and self.scheme.late_payment_interest:
            overdue_months = ((current_date.year - self.due_date.year) * 12 + 
                             current_date.month - self.due_date.month)
            if current_date.day > self.due_date.day:
                overdue_months += 1
            if overdue_months > 0:
                extra_interest_rate = self.scheme.late_payment_interest / Decimal('100')
                extra_interest = self.distribution_amount * extra_interest_rate * Decimal(str(overdue_months))
                base_interest += extra_interest
                
        return base_interest.quantize(Decimal('0.01'))
    
    def monthly_interest_till_date(self):
        """Calculate total monthly interest accumulated till date including current month for active loans"""
        if not self.issue_date or not self.scheme:
            return Decimal('0.00')
        
        current_date = timezone.now().date()
        
        if self.scheme.is_days_based:
            # Days-based calculation
            days_elapsed = (current_date - self.issue_date).days
            # Adjust for first month interest paid upfront (approx. 30 days)
            if self.is_first_month_interest_paid:
                days_elapsed = max(0, days_elapsed - 30)
                
            base_dist_amount = self.principal_amount - Decimal(str(self.processing_fee))
            
            # For schemes with no_interest_period_days, check if we're still in that period
            if getattr(self.scheme, 'no_interest_period_days', 0) and days_elapsed <= self.scheme.no_interest_period_days:
                return Decimal('0.00')
                
            # Get tiered interest rate based on days elapsed
            annual_rate = self.scheme.get_interest_rate_for_days((current_date - self.issue_date).days)
            daily_rate = annual_rate / Decimal('36500')
            interest = base_dist_amount * daily_rate * Decimal(str(days_elapsed))
            return interest.quantize(Decimal('0.01'))
            
        else:
            # Months-based calculation using date-to-date monthly cycle
            months_elapsed = self.calculate_months_date_to_date(current_date)
                
            # Adjust for first month interest paid upfront
            if self.is_first_month_interest_paid:
                months_elapsed = max(0, months_elapsed - 1)
                
            # Get monthly interest rate and amount
            monthly_info = self.monthly_interest
            monthly_amount = monthly_info['amount']
            
            # Calculate base interest
            base_interest = monthly_amount * Decimal(str(months_elapsed))
            
            # Add extra interest per 100 rupees if loan due date is crossed
            if self.is_overdue and self.scheme.late_payment_interest:
                # Calculate how many months have passed since due date
                overdue_months = ((current_date.year - self.due_date.year) * 12 + 
                               current_date.month - self.due_date.month)
                
                # Add one for partial months
                if current_date.day > self.due_date.day:
                    overdue_months += 1
                    
                if overdue_months > 0:
                    # Get late payment interest rate from the scheme
                    extra_interest_rate = self.scheme.late_payment_interest / Decimal('100')  # Convert to decimal percentage
                    # Apply late payment interest on distribution amount (amount customer received)
                    extra_interest = self.distribution_amount * extra_interest_rate * Decimal(str(overdue_months))
            return base_interest

    def get_tiered_rate_structure_display(self):
        """Returns structured tier list with Level, From Date, and To Date for displaying scheme rate tiers."""
        if not self.scheme:
            return []
        
        tiers = []
        import datetime
        issue_dt = self.issue_date or timezone.now().date()
        
        if self.scheme.interest_rate_structure:
            is_days = self.scheme.is_days_based
            
            level_idx = 1
            for key, rate in self.scheme.interest_rate_structure.items():
                if '-' in key:
                    start_val, end_val = key.split('-')
                    start_num = int(start_val.strip())
                    end_num = int(end_val.strip())
                    
                    if is_days:
                        from_date = issue_dt + datetime.timedelta(days=start_num)
                        to_date = issue_dt + datetime.timedelta(days=end_num)
                        from_date_str = from_date.strftime('%d %b, %Y')
                        to_date_str = to_date.strftime('%d %b, %Y')
                    else:
                        from_date_str = f"Month {start_num}"
                        to_date_str = f"Month {end_num}"
                elif key.endswith('+'):
                    start_num = int(key[:-1].strip())
                    if is_days:
                        from_date = issue_dt + datetime.timedelta(days=start_num)
                        from_date_str = from_date.strftime('%d %b, %Y')
                        to_date_str = "No Limit (Beyond)"
                    else:
                        from_date_str = f"Month {start_num}+"
                        to_date_str = "No Limit"
                else:
                    start_num = 0
                    end_num = int(key.strip()) if key.isdigit() else 30
                    if is_days:
                        from_date = issue_dt + datetime.timedelta(days=start_num)
                        to_date = issue_dt + datetime.timedelta(days=end_num)
                        from_date_str = from_date.strftime('%d %b, %Y')
                        to_date_str = to_date.strftime('%d %b, %Y')
                    else:
                        from_date_str = "Month 0"
                        to_date_str = f"Month {end_num}"

                annual = Decimal(str(rate))
                monthly = (annual / Decimal('12')).quantize(Decimal('0.01'))
                
                level_name = f"Level {level_idx}"
                if key.endswith('+') or level_idx == 5:
                    level_name = f"Level {level_idx} (Default/Late)"
                    
                tiers.append({
                    'level': level_name,
                    'from': from_date_str,
                    'to': to_date_str,
                    'range': f"{from_date_str} to {to_date_str}",
                    'annual_rate': annual,
                    'monthly_rate': monthly
                })
                level_idx += 1
        else:
            annual = Decimal(str(self.scheme.interest_rate or self.interest_rate or 0))
            monthly = (annual / Decimal('12')).quantize(Decimal('0.01'))
            is_days = self.scheme.is_days_based
            duration = self.scheme.loan_duration if is_days else (self.scheme.expiry_period or 12)
            
            from_date_str = issue_dt.strftime('%d %b, %Y')
            if is_days:
                to_date_str = (issue_dt + datetime.timedelta(days=duration)).strftime('%d %b, %Y')
            else:
                to_date_str = f"{duration} Months"
                
            tiers.append({
                'level': 'Level 1',
                'from': from_date_str,
                'to': to_date_str,
                'range': f"{from_date_str} to {to_date_str}",
                'annual_rate': annual,
                'monthly_rate': monthly
            })
            
        return tiers

    def get_tiered_schedule(self):
        """
        Returns a dictionary containing:
        - schedule: List of month breakdown comparing Disciplined Monthly Payments vs Delayed Bullet Payment
        - disciplined_rate: Lowest tier annual rate for monthly payers
        - disciplined_total: Total interest under monthly payment discipline
        - delayed_total: Total interest under delayed bullet payment
        - financial_impact_difference: Total savings of paying monthly vs delayed bullet payment
        """
        if not self.scheme:
            return {'schedule': [], 'disciplined_total': Decimal('0.00'), 'delayed_total': Decimal('0.00'), 'financial_impact_difference': Decimal('0.00')}
        
        base_dist_amount = self.principal_amount - Decimal(str(self.processing_fee or 0))
        principal = self.principal_amount
        
        # Disciplined Rate is the lowest tier rate (30 days rate)
        disciplined_annual_rate = Decimal(str(self.scheme.get_interest_rate_for_days(30)))
        disciplined_monthly_rate = (disciplined_annual_rate / Decimal('12')).quantize(Decimal('0.01'))

        # If first month interest was collected upfront, pre-calculate that paid amount
        # so we can deduct it from both closing columns (the customer already paid it at disbursement)
        if self.is_first_month_interest_paid:
            first_month_interest_paid = (
                base_dist_amount * (disciplined_annual_rate / Decimal('36000')) * Decimal('30')
            ).quantize(Decimal('0.01'))
        else:
            first_month_interest_paid = Decimal('0.00')
        
        if self.issue_date and self.due_date:
            term_days = (self.due_date - self.issue_date).days
            months_total = max(1, int(round(term_days / 30)))
        else:
            duration_days = self.scheme.loan_duration or (self.scheme.expiry_period * 30 if self.scheme.expiry_period else 180)
            months_total = max(1, int(round(duration_days / 30)))
        
        issue_dt = self.issue_date or datetime.date.today()
        
        schedule = []
        disciplined_cum_interest = Decimal('0.00')
        delayed_cum_interest = Decimal('0.00')
        
        for m in range(1, months_total + 1):
            days = m * 30
            from_dt = issue_dt + datetime.timedelta(days=(m-1)*30)
            to_dt = issue_dt + datetime.timedelta(days=m*30)
            from_date_str = from_dt.strftime('%b %d, %Y')
            to_date_str = to_dt.strftime('%b %d, %Y')
            
            # Disciplined Path: Month m interest — 360-day year basis (12 months × 30 days)
            m_disc_interest = (base_dist_amount * (disciplined_annual_rate / Decimal('36000')) * Decimal('30')).quantize(Decimal('0.01'))
            disciplined_cum_interest += m_disc_interest
            
            # Delayed Path: Dynamic rate escalates based on total unpaid days elapsed
            delayed_annual_rate = Decimal(str(self.scheme.get_interest_rate_for_days(days)))
            delayed_monthly_rate = (delayed_annual_rate / Decimal('12')).quantize(Decimal('0.01'))
            
            eff_days = days
            # Delayed Path: cumulative interest — 360-day year basis (12 months × 30 days)
            delayed_cum_interest = (base_dist_amount * (delayed_annual_rate / Decimal('36000')) * Decimal(str(eff_days))).quantize(Decimal('0.01'))
            
            diff_cum = max(Decimal('0.00'), delayed_cum_interest - disciplined_cum_interest)
            
            schedule.append({
                'month': m,
                'days': days,
                'from_date': from_date_str,
                'to_date': to_date_str,
                'annual_rate': delayed_annual_rate,
                'monthly_rate': delayed_monthly_rate,
                'disciplined_rate': disciplined_annual_rate,
                'disciplined_monthly_rate': disciplined_monthly_rate,
                'disciplined_monthly_interest': m_disc_interest,
                'disciplined_cum_interest': disciplined_cum_interest,
                'disciplined_closing': (principal + disciplined_cum_interest).quantize(Decimal('0.01')),
                'delayed_rate': delayed_annual_rate,
                'delayed_monthly_rate': delayed_monthly_rate,
                'delayed_cum_interest': delayed_cum_interest,
                'delayed_closing': (principal + delayed_cum_interest).quantize(Decimal('0.01')),
                'cumulative_interest': delayed_cum_interest,
                'closing_amount': (principal + delayed_cum_interest).quantize(Decimal('0.01')),
                'period_interest': m_disc_interest,
                'savings': diff_cum,
            })
            
        diff_total = max(Decimal('0.00'), delayed_cum_interest - disciplined_cum_interest)
        
        return {
            'schedule': schedule,
            'disciplined_rate': disciplined_annual_rate,
            'disciplined_total': disciplined_cum_interest,
            'delayed_total': delayed_cum_interest,
            'financial_impact_difference': diff_total
        }

    @property
    def customer_photo(self):
        if self.customer_face_capture and self.customer_face_capture.strip():
            return self.customer_face_capture
        from utils.default_photos import get_default_person_photo
        return get_default_person_photo()

    @property
    def item_photo_list(self):
        import json
        from utils.default_photos import get_default_item_photo
        if isinstance(self.item_photos, str):
            try:
                photos = json.loads(self.item_photos)
                if photos and len(photos) > 0 and all(p.strip() for p in photos):
                    return photos
            except Exception:
                pass
        return [get_default_item_photo(item.category) for item in self.items.all()]

class LoanItem(models.Model):
    """Model to track items in a loan with their gold details"""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
    item = models.ForeignKey('inventory.Item', on_delete=models.CASCADE)
    
    # Quantity of items (default 1)
    quantity = models.PositiveIntegerField(default=1, help_text="Number of items")
    
    # Gold ornament details
    gold_karat = models.DecimalField(max_digits=4, decimal_places=2, help_text="Purity of gold in karats")
    gross_weight = models.DecimalField(max_digits=7, decimal_places=3, help_text="Total weight of the ornament in grams")
    net_weight = models.DecimalField(max_digits=7, decimal_places=3, help_text="Weight of pure gold content in grams")
    stone_weight = models.DecimalField(max_digits=7, decimal_places=3, help_text="Weight of stones if any in grams", null=True, blank=True)
    market_price_22k = models.DecimalField(max_digits=10, decimal_places=2, help_text="Market price of 22K gold per gram at the time of loan")
    
    class Meta:
        unique_together = ['loan', 'item']  # An item can only be used once in a loan
        
    def __str__(self):
        return f"{self.item.name} in {self.loan}"

class Payment(models.Model):
    """Payment model for tracking loan payments"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('online', 'Online Payment'),
        ('other', 'Other'),
    ]
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference_number = models.CharField(max_length=255, blank=True, null=True)  # Increased from 100 to 255
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                  null=True, related_name='payments_received')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('payment')
        verbose_name_plural = _('payments')
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment of Rs: {self.amount} for {self.loan}"


class LoanExtension(models.Model):
    """Model to track loan extensions/renewals"""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='extensions')
    extension_date = models.DateField()
    previous_due_date = models.DateField()
    new_due_date = models.DateField()
    fee = models.DecimalField(max_digits=10, decimal_places=2)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                  null=True, related_name='extensions_approved')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('loan extension')
        verbose_name_plural = _('loan extensions')
        ordering = ['-extension_date']
    
    def __str__(self):
        return f"Extension for {self.loan} - {self.extension_date}"


class Sale(models.Model):
    """Model for sale transactions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    
    transaction_number = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases')
    item = models.ForeignKey('inventory.Item', on_delete=models.CASCADE, related_name='sales')
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='sales')
    
    # Financial information
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # GST fields
    gst_rate = models.ForeignKey('gst.GSTRate', on_delete=models.PROTECT, null=True, blank=True, 
                               related_name='sales', help_text="GST rate applied to this sale")
    is_interstate = models.BooleanField(default=False, help_text="Whether it's an interstate sale (IGST) or intrastate (CGST+SGST)")
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="CGST rate in percentage")
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="SGST rate in percentage")
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="IGST rate in percentage")
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="CGST amount")
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="SGST amount")
    igst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="IGST amount")
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Total tax amount")
    
    # For GST reporting
    place_of_supply = models.CharField(max_length=50, blank=True, null=True, help_text="State code or name for GST reporting")
    place_of_supply_tamil = models.CharField(max_length=100, blank=True, null=True, help_text="Tamil place of supply")
    customer_gstin = models.CharField(max_length=15, blank=True, null=True, help_text="Customer's GSTIN if registered")
    hsn_code = models.CharField(max_length=20, blank=True, null=True, help_text="HSN code for the item")
    
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment
    payment_method = models.CharField(max_length=20, choices=Payment.PAYMENT_METHOD_CHOICES)
    reference_number = models.CharField(max_length=255, blank=True, null=True)  # Increased from 100 to 255
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sale_date = models.DateField()
    
    # Management
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                              null=True, related_name='sales_processed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('sale')
        verbose_name_plural = _('sales')
        ordering = ['-sale_date']
    
    def __str__(self):
        return f"Sale #{self.transaction_number} - Rs: {self.total_amount}"
    
    def save(self, *args, **kwargs):
        """Override save to calculate GST if not already calculated"""
        # Calculate tax amounts if a GST rate is provided and taxes aren't already set
        if self.gst_rate and self.tax == 0:
            self.calculate_gst()
            
        # Calculate total amount if not already set
        if not self.total_amount:
            self.total_amount = self.calculate_total()
            
        super().save(*args, **kwargs)
        
        # Create GST transaction record for reporting
        self.create_gst_transaction()
    
    def calculate_gst(self):
        """Calculate GST based on selling price and GST rate"""
        if not self.gst_rate:
            return
            
        # Set rates from GST rate object
        self.cgst_rate = self.gst_rate.cgst_rate
        self.sgst_rate = self.gst_rate.sgst_rate
        self.igst_rate = self.gst_rate.igst_rate
        
        # Calculate taxable value (after discount)
        taxable_value = self.selling_price - self.discount
        
        # Calculate tax amounts based on interstate status
        if self.is_interstate:
            self.igst_amount = (taxable_value * self.igst_rate) / Decimal('100')
            self.cgst_amount = Decimal('0')
            self.sgst_amount = Decimal('0')
        else:
            self.cgst_amount = (taxable_value * self.cgst_rate) / Decimal('100')
            self.sgst_amount = (taxable_value * self.sgst_rate) / Decimal('100')
            self.igst_amount = Decimal('0')
            
        # Calculate total tax
        self.tax = self.cgst_amount + self.sgst_amount + self.igst_amount
        
        return self.tax
    
    def calculate_total(self):
        """Calculate total amount including tax"""
        # Calculate total (selling price - discount + tax)
        return self.selling_price - self.discount + self.tax
    
    def create_gst_transaction(self):
        """Create a GST transaction record for this sale for reporting purposes"""
        from django.contrib.contenttypes.models import ContentType
        from gst.models import GSTTransaction
        
        # Only create transaction if this is a completed sale with GST
        if self.status != 'completed' or not self.gst_rate:
            return
            
        # Get or create GST transaction for this sale
        sale_content_type = ContentType.objects.get_for_model(Sale)
        
        # Check if transaction already exists
        try:
            transaction = GSTTransaction.objects.get(
                content_type=sale_content_type,
                object_id=self.id
            )
        except GSTTransaction.DoesNotExist:
            # Create new transaction
            transaction = GSTTransaction(
                transaction_date=self.sale_date,
                transaction_type='SALE',
                invoice_number=self.transaction_number,
                gst_rate=self.gst_rate,
                party_name=self.customer.full_name if self.customer else "Walk-in Customer",
                party_gstin=self.customer_gstin,
                is_registered_dealer=bool(self.customer_gstin),
                place_of_supply=self.place_of_supply or self.branch.state,
                is_interstate=self.is_interstate,
                taxable_value=self.selling_price - self.discount,
                cgst_amount=self.cgst_amount,
                sgst_amount=self.sgst_amount,
                igst_amount=self.igst_amount,
                total_tax=self.tax,
                total_amount=self.total_amount,
                content_type=sale_content_type,
                object_id=self.id,
                notes=f"Sale of {self.item.name}"
            )
            transaction.save()
        else:
            # Update existing transaction
            transaction.transaction_date = self.sale_date
            transaction.party_name = self.customer.full_name if self.customer else "Walk-in Customer"
            transaction.party_gstin = self.customer_gstin
            transaction.is_registered_dealer = bool(self.customer_gstin)
            transaction.place_of_supply = self.place_of_supply or self.branch.state
            transaction.is_interstate = self.is_interstate
            transaction.taxable_value = self.selling_price - self.discount
            transaction.cgst_amount = self.cgst_amount
            transaction.sgst_amount = self.sgst_amount
            transaction.igst_amount = self.igst_amount
            transaction.total_tax = self.tax
            transaction.total_amount = self.total_amount
            transaction.save()
