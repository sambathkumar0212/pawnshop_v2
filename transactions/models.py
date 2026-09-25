from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from accounts.models import Customer  # Import Customer from accounts app
from schemes.models import Scheme  # Changed from content_manager.models to schemes.models
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
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
        ('draft', _('Draft')),
        ('pending_approval', _('Pending Approval')),
        ('approved', _('Approved (Ready for Disbursal)')),
        ('rejected', _('Rejected')),
        ('active', _('Active')),
        ('repaid', _('Repaid')),
        ('defaulted', _('Defaulted')),
        ('extended', _('Extended')),
        ('foreclosed', _('Foreclosed')),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    
    # Tiered Maker-Checker Approvals (Task 2.1)
    APPROVAL_TIER_CHOICES = (
        (1, _('Tier 1 (Principal <= ₹2,00,000) [BM]')),
        (2, _('Tier 2 (Principal ₹2,00,001 - ₹10,00,000) [BM + RO]')),
        (3, _('Tier 3 (Principal > ₹10,00,000) [BM + RO + HO]')),
    )
    approval_tier = models.PositiveSmallIntegerField(choices=APPROVAL_TIER_CHOICES, default=1, db_index=True)
    maker = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='loans_initiated',
        help_text=_("Appraiser / Maker who initiated the loan")
    )
    checker_bm = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='loans_approved_bm',
        help_text=_("Branch Manager who granted Tier 1 Approval")
    )
    checker_bm_at = models.DateTimeField(null=True, blank=True)
    checker_ro = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='loans_approved_ro',
        help_text=_("Regional Manager who granted Tier 2 Approval")
    )
    checker_ro_at = models.DateTimeField(null=True, blank=True)
    checker_ho = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='loans_approved_ho',
        help_text=_("Head Office Credit Committee who granted Tier 3 Approval")
    )
    checker_ho_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    reappraisal_notes = models.TextField(blank=True, null=True)

    # Customer Identity OTP Verification
    otp_code = models.CharField(
        max_length=6, blank=True, null=True,
        help_text=_("6-digit OTP code sent to customer mobile for identity confirmation")
    )
    otp_created_at = models.DateTimeField(null=True, blank=True, help_text=_("Timestamp when OTP was generated"))
    otp_attempts = models.PositiveSmallIntegerField(default=0, help_text=_("Count of invalid OTP verification attempts"))
    is_otp_verified = models.BooleanField(default=False, db_index=True, help_text=_("Whether customer identity has been verified via OTP"))
    otp_verified_at = models.DateTimeField(null=True, blank=True, help_text=_("Timestamp when customer OTP was successfully verified"))
    otp_verified_by = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='loans_otp_verified',
        help_text=_("User / Officer who verified the customer OTP")
    )
    
    # RBI IRAC Asset Classification & Provisioning (Task 2.2)
    IRAC_STATUS_CHOICES = (
        ('STANDARD', _('Standard Asset (0 Overdue Days)')),
        ('SMA_0', _('SMA-0 (1 to 30 Overdue Days)')),
        ('SMA_1', _('SMA-1 (31 to 60 Overdue Days)')),
        ('SMA_2', _('SMA-2 (61 to 90 Overdue Days)')),
        ('NPA_SUBSTANDARD', _('NPA - Substandard (>90 Days Overdue)')),
        ('NPA_DOUBTFUL', _('NPA - Doubtful (>180 Days Overdue)')),
        ('NPA_LOSS', _('NPA - Loss Asset')),
    )
    irac_status = models.CharField(
        max_length=20, choices=IRAC_STATUS_CHOICES, default='STANDARD', db_index=True,
        help_text=_("RBI IRAC Asset Classification Status")
    )
    overdue_days = models.PositiveIntegerField(default=0, db_index=True, help_text=_("Number of overdue days past grace period"))
    npa_date = models.DateField(null=True, blank=True, help_text=_("Date when loan was classified as NPA"))
    provisioning_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.25'),
        help_text=_("Regulatory Loan Provisioning Percentage")
    )
    accrued_interest = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text=_("Total cumulative daily interest accrued")
    )
    last_accrual_date = models.DateField(null=True, blank=True, help_text=_("Date of latest daily interest accrual"))
    
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
    issue_date = models.DateField(db_index=True)
    due_date = models.DateField(db_index=True)
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
        verbose_name=_("Is first month interest paid?")
    )
    is_processing_fee_paid = models.BooleanField(
        default=False,
        verbose_name=_("Is processing fees paid?")
    )
    gold_location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Gold Location"),
        help_text=_("Locker/Location where the gold is stored")
    )
    repledge_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Repledge Date"),
        help_text=_("Date of the repledge")
    )
    repledge_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Repledge Amount"),
        help_text=_("Amount if repledged")
    )
    gold_status_others = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Gold Status Others"),
        help_text=_("Any other notes or details about the gold status")
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
        indexes = [
            # Dashboard: active_loans count
            models.Index(fields=['status'], name='loan_status_idx'),
            # Dashboard: overdue_loans = active + due_date < today
            models.Index(fields=['status', 'due_date'], name='loan_status_due_idx'),
            # List view default sort
            models.Index(fields=['-issue_date'], name='loan_issue_date_idx'),
            # Branch filtering (applied on every request for non-superusers)
            models.Index(fields=['branch', 'status'], name='loan_branch_status_idx'),
        ]

    def __str__(self):
        return f"Loan #{self.loan_number} - {self.customer.full_name}"

    def determine_approval_tier(self):
        """Determine required approval tier based on principal loan amount"""
        amt = Decimal(str(self.principal_amount or 0))
        if amt <= 200000:
            return 1
        elif amt <= 1000000:
            return 2
        else:
            return 3

    def save(self, *args, **kwargs):
        if self.principal_amount is not None:
            self.approval_tier = self.determine_approval_tier()
        super().save(*args, **kwargs)

    @property
    def is_approved_for_disbursal(self):
        """Check if all required tiered approvals are granted"""
        if self.status == 'active':
            return True
        if self.status != 'approved':
            return False
        tier = self.determine_approval_tier()
        if tier == 1:
            return bool(self.checker_bm)
        elif tier == 2:
            return bool(self.checker_bm and self.checker_ro)
        elif tier == 3:
            return bool(self.checker_bm and self.checker_ro and self.checker_ho)
        return True

    def generate_otp(self, save=True):
        """Generate a cryptographically secure 6-digit OTP and reset attempt counters."""
        import random
        self.otp_code = f"{random.randint(100000, 999999)}"
        self.otp_created_at = timezone.now()
        self.otp_attempts = 0
        self.is_otp_verified = False
        self.otp_verified_at = None
        self.otp_verified_by = None
        if save and self.pk:
            self.save(update_fields=['otp_code', 'otp_created_at', 'otp_attempts', 'is_otp_verified', 'otp_verified_at', 'otp_verified_by'])
        return self.otp_code

    def is_otp_expired(self, max_minutes=15):
        """Check if generated OTP has exceeded validity window (default 15 minutes)."""
        if not self.otp_created_at:
            return True
        from django.utils import timezone
        diff = timezone.now() - self.otp_created_at
        return diff.total_seconds() > (max_minutes * 60)

    def verify_otp(self, entered_code, user=None):
        """
        Validates entered 6-digit OTP code for customer identity confirmation.
        Returns tuple: (success: bool, message: str)
        """
        if self.is_otp_verified:
            return True, _("Customer identity is already verified via OTP.")

        if not self.otp_code:
            return False, _("No active OTP found. Please request a new OTP.")

        if self.is_otp_expired():
            return False, _("OTP has expired (15-minute window). Please click 'Resend OTP' to generate a fresh code.")

        if self.otp_attempts >= 5:
            return False, _("Maximum invalid OTP attempts exceeded (5). Please request a fresh OTP.")

        entered_clean = str(entered_code or '').strip()
        if entered_clean == str(self.otp_code).strip():
            self.is_otp_verified = True
            self.otp_verified_at = timezone.now()
            self.otp_verified_by = user
            self.save(update_fields=['is_otp_verified', 'otp_verified_at', 'otp_verified_by'])
            try:
                from accounts.models import LoanEditLog
                LoanEditLog.objects.create(
                    loan=self,
                    edited_by=user,
                    change_type='otp_verified',
                    description=f"Customer identity verified via 6-digit OTP by {user.get_full_name() if user else 'System'}."
                )
            except Exception:
                pass
            return True, _("Customer identity confirmed successfully via OTP!")
        else:
            self.otp_attempts += 1
            self.save(update_fields=['otp_attempts'])
            remaining = max(0, 5 - self.otp_attempts)
            return False, _(f"Invalid OTP code entered. {remaining} attempt(s) remaining.")

    def build_otp_whatsapp_message(self, lang='ta') -> str:
        """Constructs bilingual OTP WhatsApp/SMS notification for customer."""
        branch = getattr(self, 'branch', None)
        org_name = 'First Money Gold'
        if branch and getattr(branch, 'organization', None):
            org_name = branch.organization.name or 'First Money Gold'
        elif hasattr(settings, 'ORGANIZATION_NAME'):
            org_name = getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold')

        customer_name = getattr(self.customer, 'full_name', '') or str(self.customer)
        loan_num = self.loan_number or 'N/A'
        principal_fmt = f"Rs. {self.principal_amount:,.0f}" if self.principal_amount else "Rs. 0"
        otp = self.otp_code or '------'
        branch_name = getattr(branch, 'name', '') or org_name
        branch_phone = getattr(branch, 'phone', '') or getattr(settings, 'COMPANY_PHONE', '9876543210')

        if lang == 'en':
            return (
                f"🔐 *{org_name} - Loan Verification OTP*\n\n"
                f"Dear *{customer_name}*,\n"
                f"Your OTP for Gold Loan application *#{loan_num}* (Amount: *{principal_fmt}*) is:\n\n"
                f"👉 *{otp}* 👈\n\n"
                f"⏱️ This OTP is valid for *15 minutes*.\n"
                f"Please share this OTP with the branch officer to confirm your identity.\n"
                f"⚠️ *Never share this code with anyone outside the branch.*\n\n"
                f"📍 Branch: *{branch_name}* | Helpline: *{branch_phone}*"
            )

        # Tamil default
        return (
            f"🔐 *{org_name} - தங்கக் கடன் சரிபார்ப்பு OTP*\n\n"
            f"அன்புள்ள *{customer_name}* அவர்களுக்கு,\n"
            f"தங்களின் புதிய தங்கக் கடன் விண்ணப்பம் *#{loan_num}* (தொகை: *{principal_fmt}*)-க்கான உறுதிப்படுத்தல் OTP:\n\n"
            f"👉 *{otp}* 👈\n\n"
            f"⏱️ இந்த OTP *15 நிமிடங்கள்* மட்டுமே செல்லுபடியாகும்.\n"
            f"தங்களின் அடையாளத்தை உறுதிப்படுத்த இந்த OTP எண்ணை கிளை அதிகாரியிடம் தெரிவிக்கவும்.\n"
            f"⚠️ *இந்த OTP எண்ணை வேறு எவருடனும் பகிர வேண்டாம்.*\n\n"
            f"📍 கிளை: *{branch_name}* | தொடர்பு: *{branch_phone}*"
        )

    def get_otp_whatsapp_link(self) -> str:
        """Returns direct wa.me link for manual WhatsApp OTP dispatch."""
        if not self.customer or not self.customer.phone:
            return ''
        from transactions.services_whatsapp import get_whatsapp_link
        msg = self.build_otp_whatsapp_message(lang='ta')
        return get_whatsapp_link(self.customer.phone, msg)

    def can_user_approve(self, user):
        """Check if the given user is authorized to approve the current pending tier"""
        if not user or not user.is_authenticated:
            return False

        # CRITICAL: OTP must be verified before any manager can approve
        if not self.is_otp_verified:
            return False

        if user.is_superuser:
            return True
        
        role = getattr(user, 'role', None)
        role_type = getattr(role, 'role_type', None) if role else str(getattr(user, 'role', ''))
        tier = self.determine_approval_tier()

        # Step 1: Branch Manager approval (Required for all tiers)
        if not self.checker_bm:
            is_bm = role_type in ['branch_manager', 'regional_manager', 'admin', 'headoffice'] or (self.branch and user == self.branch.manager)
            if is_bm:
                # Ensure BM is for this branch (or higher)
                if role_type in ['regional_manager', 'admin', 'headoffice'] or user.is_superuser:
                    return True
                return getattr(user, 'branch', None) == self.branch or user == self.branch.manager
            return False

        # Step 2: Regional Manager approval (For Tier 2 & Tier 3)
        if tier in [2, 3] and not self.checker_ro:
            is_ro = role_type in ['regional_manager', 'admin', 'headoffice'] or user.is_superuser
            if is_ro:
                # If regional manager, check region scoping
                if user.is_superuser or role_type in ['admin', 'headoffice']:
                    return True
                if hasattr(user, 'regions') and user.regions.exists():
                    return user.regions.filter(branches=self.branch).exists()
                return True
            return False

        # Step 3: Head Office Credit Committee approval (For Tier 3 > 10L)
        if tier == 3 and not self.checker_ho:
            return role_type in ['admin', 'headoffice', 'finance_manager'] or user.is_superuser

        return False

    def approve(self, user, notes=None):
        """Advance approval workflow for current tier"""
        if not self.is_otp_verified:
            from django.core.exceptions import ValidationError
            raise ValidationError(_("Approval Blocked: Customer identity OTP verification is pending. Please verify OTP first."))

        tier = self.determine_approval_tier()
        self.approval_tier = tier

        if not self.checker_bm:
            self.checker_bm = user
            self.checker_bm_at = timezone.now()
            if tier == 1:
                self.status = 'approved'
            else:
                self.status = 'pending_approval'
        elif tier in [2, 3] and not self.checker_ro:
            self.checker_ro = user
            self.checker_ro_at = timezone.now()
            if tier == 2:
                self.status = 'approved'
            else:
                self.status = 'pending_approval'
        elif tier == 3 and not self.checker_ho:
            self.checker_ho = user
            self.checker_ho_at = timezone.now()
            self.status = 'approved'

        self.save()
        return self.status

    def reject(self, user, reason):
        """Reject loan application with mandatory reason"""
        self.status = 'rejected'
        self.rejection_reason = reason
        self.save()
        return self.status

    def request_reappraisal(self, user, notes):
        """Request re-appraisal / physical re-examination"""
        self.status = 'pending_approval'
        self.reappraisal_notes = notes
        # Reset intermediate checkers
        self.checker_bm = None
        self.checker_bm_at = None
        self.checker_ro = None
        self.checker_ro_at = None
        self.checker_ho = None
        self.checker_ho_at = None
        self.save()
        return self.status

    @property
    def maker_name(self):
        if self.maker:
            return self.maker.get_full_name() or self.maker.username
        if self.created_by:
            return self.created_by.get_full_name() or self.created_by.username
        return "Appraiser"

    @property
    def checker_bm_name(self):
        if self.checker_bm:
            return self.checker_bm.get_full_name() or self.checker_bm.username
        return ""

    @property
    def checker_ro_name(self):
        if self.checker_ro:
            return self.checker_ro.get_full_name() or self.checker_ro.username
        return ""

    @property
    def checker_ho_name(self):
        if self.checker_ho:
            return self.checker_ho.get_full_name() or self.checker_ho.username
        return ""

    @property
    def loan_ornaments(self):
        return self.loanitem_set
    
    @property
    def monthly_interest(self):
        """Calculate monthly interest details for the loan.
        
        Returns a dictionary with monthly interest rate, amount, and per thousand rate.
        After part payments, interest is calculated on the current outstanding principal
        (whichever is lower: original distribution_amount or current principal_amount).
        """
        from decimal import Decimal
        
        # Calculate monthly interest rate (annual rate / 12)
        if self.scheme and self.scheme.interest_rate_structure:
            # Use the lowest/first tier rate (interest rate for 30 days)
            annual_rate = Decimal(str(self.scheme.get_interest_rate_for_days(30)))
            monthly_rate = annual_rate / Decimal('12')
        else:
            monthly_rate = Decimal(self.interest_rate) / Decimal('12')
        
        # Base amount for interest = current outstanding principal (reduced after part payments)
        # Use min(distribution_amount, principal_amount) so interest always tracks current principal
        orig_dist = self.distribution_amount if self.distribution_amount is not None \
            else ((self.principal_amount or Decimal('0')) - Decimal(str(self.processing_fee or 0)))
        current_principal = self.principal_amount or Decimal('0')
        base_amount = min(orig_dist, current_principal)
        monthly_amount = (base_amount * monthly_rate) / Decimal('100')
        
        # Calculate rate per 1000 of base amount
        per_thousand = (monthly_rate * Decimal('10'))  # per Rs. 1,000
        
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
        """Returns the current effective distribution amount.
        
        At origination: returns stored distribution_amount (or principal - processing_fee if not set).
        After part payments: tracks current principal (whichever is lower: stored distribution or current principal).
        """
        from decimal import Decimal
        if self.distribution_amount is not None:
            return min(self.distribution_amount, self.principal_amount or Decimal('0'))
        proc_fee = Decimal(str(self.processing_fee or 0))
        return max(Decimal('0'), (self.principal_amount or Decimal('0')) - proc_fee)



    @property
    def distribution_amount_with_deduction(self):
        """Returns Distribution Amount with Deduction.

        Base = original_distribution_amount (current effective distribution: principal - processing_fee).
        Then deduct from that base:
            - processing_fee       if is_processing_fee_paid = True
            - first_month_interest if is_first_month_interest_paid = True

        Formula:
            distribution_with_deduction = distribution_amount
                - (processing_fee        if is_processing_fee_paid)
                - (first_month_interest  if is_first_month_interest_paid)
        """
        from decimal import Decimal
        proc_fee = Decimal(str(self.processing_fee or 0))

        # Use dynamic original_distribution_amount as base
        base = self.original_distribution_amount


        # Deduct processing fee only if paid upfront
        proc_fee_deduction = proc_fee if self.is_processing_fee_paid else Decimal('0')

        # Deduct 1st month interest only if paid upfront
        first_month_interest_deduction = Decimal('0')
        if self.is_first_month_interest_paid:
            annual_rate = Decimal('0')
            if self.scheme and self.scheme.interest_rate_structure:
                annual_rate = Decimal(str(self.scheme.get_interest_rate_for_days(30)))
            elif self.interest_rate:
                annual_rate = Decimal(str(self.interest_rate))
            elif self.scheme and self.scheme.interest_rate:
                annual_rate = Decimal(str(self.scheme.interest_rate))
            else:
                annual_rate = Decimal('12.00')
            monthly_rate = annual_rate / Decimal('12')
            first_month_interest_deduction = round((base * monthly_rate) / Decimal('100'), 2)

        net = base - proc_fee_deduction - first_month_interest_deduction
        return max(Decimal('0'), round(net, 2))

    @property
    def advance_interest_amount(self):
        """Returns the 1st month interest amount paid/deducted upfront if is_first_month_interest_paid is True."""
        if not self.is_first_month_interest_paid:
            return Decimal('0.00')
        from decimal import Decimal
        base = self.original_distribution_amount
        annual_rate = Decimal('0')
        if self.scheme and getattr(self.scheme, 'interest_rate_structure', None):
            annual_rate = Decimal(str(self.scheme.get_interest_rate_for_days(30)))
        elif self.interest_rate:
            annual_rate = Decimal(str(self.interest_rate))
        elif self.scheme and getattr(self.scheme, 'interest_rate', None):
            annual_rate = Decimal(str(self.scheme.interest_rate))
        else:
            annual_rate = Decimal('12.00')
        monthly_rate = annual_rate / Decimal('12')
        return Decimal(str(round((base * monthly_rate) / Decimal('100'), 2)))

    @property
    def effective_principal_amount(self):
        """
        Returns the true net principal liability owed by the customer:
        If first month interest was pre-deducted from loan proceeds (is_first_month_interest_paid = True),
        that pre-paid interest is deducted from principal_amount so the customer is not double-charged on redemption.
        """
        from decimal import Decimal
        principal = self.principal_amount or Decimal('0.00')
        if self.is_first_month_interest_paid:
            return max(Decimal('0.00'), principal - self.advance_interest_amount)
        return principal

    def save(self, *args, **kwargs):
        # Check if this is a creation
        is_create = self.pk is None

        # Ensure distribution_amount has a default of principal - processing_fee
        if self.distribution_amount is None and self.principal_amount is not None:
            proc_fee = self.processing_fee or 0
            from decimal import Decimal
            self.distribution_amount = self.principal_amount - Decimal(str(proc_fee))
        
        # Track changed fields when editing an existing loan
        changes = []
        if not is_create:
            try:
                old_loan = Loan.objects.select_related('customer', 'branch', 'scheme').get(pk=self.pk)
                field_configs = [
                    ('customer_id', 'Customer Name',
                     lambda obj: f"{obj.customer.first_name} {obj.customer.last_name}" if obj.customer else "N/A"),
                    ('branch_id', 'Branch',
                     lambda obj: obj.branch.name if obj.branch else "N/A"),
                    ('scheme_id', 'Scheme',
                     lambda obj: obj.scheme.name if obj.scheme else "N/A"),
                    ('principal_amount', 'Principal Amount',
                     lambda obj: f"Rs. {obj.principal_amount}"),
                    ('interest_rate', 'Interest Rate',
                     lambda obj: f"{obj.interest_rate}%"),
                    ('processing_fee', 'Processing Fee',
                     lambda obj: f"Rs. {obj.processing_fee}"),
                    ('distribution_amount', 'Distribution Amount (No Deductions)',
                     lambda obj: f"Rs. {obj.distribution_amount}"),
                    ('status', 'Status',
                     lambda obj: obj.get_status_display() if hasattr(obj, 'get_status_display') else str(obj.status)),
                    ('issue_date', 'Issue Date',
                     lambda obj: str(obj.issue_date)),
                    ('due_date', 'Due Date',
                     lambda obj: str(obj.due_date)),
                    ('grace_period_end', 'Grace Period End Date',
                     lambda obj: str(obj.grace_period_end)),
                    ('is_first_month_interest_paid', 'First Month Interest Paid Upfront',
                     lambda obj: "Yes" if obj.is_first_month_interest_paid else "No"),
                    ('is_processing_fee_paid', 'Processing Fee Paid Upfront',
                     lambda obj: "Yes" if obj.is_processing_fee_paid else "No"),
                    ('gold_location', 'Gold Location',
                     lambda obj: str(obj.gold_location or "N/A")),
                    ('repledge_date', 'Repledge Date',
                     lambda obj: str(obj.repledge_date or "N/A")),
                    ('repledge_amount', 'Repledge Amount',
                     lambda obj: f"Rs. {obj.repledge_amount}" if obj.repledge_amount is not None else "N/A"),
                    ('gold_status_others', 'Gold Status Notes',
                     lambda obj: str(obj.gold_status_others or "N/A")),
                ]
                for field_name, label, formatter in field_configs:
                    old_raw = getattr(old_loan, field_name, None)
                    new_raw = getattr(self, field_name, None)
                    if str(old_raw or '') != str(new_raw or ''):
                        changes.append({
                            'field': field_name,
                            'label': label,
                            'old': formatter(old_loan),
                            'new': formatter(self),
                        })
            except Exception as e:
                print(f"Error computing loan field changes: {e}")

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
        _changes = changes
        
        def _send_notification():
            try:
                from transactions.models import Loan
                loan = Loan.objects.get(pk=loan_id)
                loan.send_loan_notification_email(_is_create, changes=_changes)
            except Exception as e:
                import traceback
                print(f"Error sending loan email notification: {str(e)}")
                traceback.print_exc()
        
        from django.db import transaction
        transaction.on_commit(_send_notification)

    def send_loan_notification_email(self, is_create, changes=None):
        """Send email notification on loan creation or edit to firstmoneygold@gmail.com and hariswealthway@gmail.com with highlighted changes"""
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings
        from django.template.loader import render_to_string

        changes = changes or []
        changed_fields_map = {c['field']: c for c in changes}

        action = "Created" if is_create else "Edited"
        subject = f"Loan {action}: {self.loan_number} - {self.customer.first_name} {self.customer.last_name}"
        recipients = ["firstmoneygold@gmail.com", "hariswealthway@gmail.com"]
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@myapp.com')

        # Build comprehensive details list for email table
        details_list = [
            {'field': 'loan_number', 'label': 'Loan Number', 'value': self.loan_number, 'is_changed': False, 'old_value': ''},
            {'field': 'customer_id', 'label': 'Customer Name', 'value': f"{self.customer.first_name} {self.customer.last_name}",
             'is_changed': 'customer_id' in changed_fields_map,
             'old_value': changed_fields_map['customer_id']['old'] if 'customer_id' in changed_fields_map else ''},
            {'field': 'branch_id', 'label': 'Branch', 'value': self.branch.name if self.branch else 'N/A',
             'is_changed': 'branch_id' in changed_fields_map,
             'old_value': changed_fields_map['branch_id']['old'] if 'branch_id' in changed_fields_map else ''},
            {'field': 'scheme_id', 'label': 'Scheme', 'value': self.scheme.name if self.scheme else 'N/A',
             'is_changed': 'scheme_id' in changed_fields_map,
             'old_value': changed_fields_map['scheme_id']['old'] if 'scheme_id' in changed_fields_map else ''},
            {'field': 'principal_amount', 'label': 'Principal Amount', 'value': f"Rs. {self.principal_amount}",
             'is_changed': 'principal_amount' in changed_fields_map,
             'old_value': changed_fields_map['principal_amount']['old'] if 'principal_amount' in changed_fields_map else ''},
            {'field': 'interest_rate', 'label': 'Interest Rate', 'value': f"{self.interest_rate}%",
             'is_changed': 'interest_rate' in changed_fields_map,
             'old_value': changed_fields_map['interest_rate']['old'] if 'interest_rate' in changed_fields_map else ''},
            {'field': 'processing_fee', 'label': 'Processing Fee', 'value': f"Rs. {self.processing_fee}",
             'is_changed': 'processing_fee' in changed_fields_map,
             'old_value': changed_fields_map['processing_fee']['old'] if 'processing_fee' in changed_fields_map else ''},
            {'field': 'distribution_amount', 'label': 'Distribution Amount (No Deductions)', 'value': f"Rs. {self.distribution_amount}",
             'is_changed': 'distribution_amount' in changed_fields_map,
             'old_value': changed_fields_map['distribution_amount']['old'] if 'distribution_amount' in changed_fields_map else ''},
            {'field': 'distribution_amount_with_deduction', 'label': 'Distribution Amount with Deduction', 'value': f"Rs. {self.distribution_amount_with_deduction}",
             'is_changed': 'distribution_amount' in changed_fields_map or 'principal_amount' in changed_fields_map or 'processing_fee' in changed_fields_map,
             'old_value': ''},
            {'field': 'status', 'label': 'Status', 'value': self.get_status_display(),
             'is_changed': 'status' in changed_fields_map,
             'old_value': changed_fields_map['status']['old'] if 'status' in changed_fields_map else ''},
            {'field': 'issue_date', 'label': 'Issue Date', 'value': str(self.issue_date),
             'is_changed': 'issue_date' in changed_fields_map,
             'old_value': changed_fields_map['issue_date']['old'] if 'issue_date' in changed_fields_map else ''},
            {'field': 'due_date', 'label': 'Due Date', 'value': str(self.due_date),
             'is_changed': 'due_date' in changed_fields_map,
             'old_value': changed_fields_map['due_date']['old'] if 'due_date' in changed_fields_map else ''},
            {'field': 'grace_period_end', 'label': 'Grace Period End Date', 'value': str(self.grace_period_end),
             'is_changed': 'grace_period_end' in changed_fields_map,
             'old_value': changed_fields_map['grace_period_end']['old'] if 'grace_period_end' in changed_fields_map else ''},
            {'field': 'is_first_month_interest_paid', 'label': '1st Month Interest Paid Upfront', 'value': "Yes" if self.is_first_month_interest_paid else "No",
             'is_changed': 'is_first_month_interest_paid' in changed_fields_map,
             'old_value': changed_fields_map['is_first_month_interest_paid']['old'] if 'is_first_month_interest_paid' in changed_fields_map else ''},
            {'field': 'is_processing_fee_paid', 'label': 'Processing Fee Paid Upfront', 'value': "Yes" if self.is_processing_fee_paid else "No",
             'is_changed': 'is_processing_fee_paid' in changed_fields_map,
             'old_value': changed_fields_map['is_processing_fee_paid']['old'] if 'is_processing_fee_paid' in changed_fields_map else ''},
        ]

        # Add Gold Ornaments Summary
        try:
            loan_items = list(self.loanitem_set.select_related('item').all())
            if loan_items:
                total_gross = sum((li.gross_weight or Decimal('0.00')) for li in loan_items)
                total_net = sum((li.net_weight or Decimal('0.00')) for li in loan_items)
                items_summary = ", ".join(f"{li.item.name} ({li.quantity} pcs)" for li in loan_items if li.item)
                details_list.append({
                    'field': 'items_summary', 'label': 'Pledged Ornaments', 'value': items_summary or f"{len(loan_items)} items",
                    'is_changed': False, 'old_value': ''
                })
                details_list.append({
                    'field': 'total_weight', 'label': 'Total Gross / Net Weight', 'value': f"{total_gross:.2f}g (Gross) / {total_net:.2f}g (Net)",
                    'is_changed': False, 'old_value': ''
                })
        except Exception:
            pass

        if self.gold_location or 'gold_location' in changed_fields_map:
            details_list.append({
                'field': 'gold_location', 'label': 'Gold Location', 'value': self.gold_location or 'N/A',
                'is_changed': 'gold_location' in changed_fields_map,
                'old_value': changed_fields_map['gold_location']['old'] if 'gold_location' in changed_fields_map else ''
            })

        if self.repledge_date or 'repledge_date' in changed_fields_map:
            details_list.append({
                'field': 'repledge_date', 'label': 'Repledge Date', 'value': str(self.repledge_date or 'N/A'),
                'is_changed': 'repledge_date' in changed_fields_map,
                'old_value': changed_fields_map['repledge_date']['old'] if 'repledge_date' in changed_fields_map else ''
            })

        if self.repledge_amount or 'repledge_amount' in changed_fields_map:
            details_list.append({
                'field': 'repledge_amount', 'label': 'Repledge Amount',
                'value': f"Rs. {self.repledge_amount}" if self.repledge_amount is not None else 'N/A',
                'is_changed': 'repledge_amount' in changed_fields_map,
                'old_value': changed_fields_map['repledge_amount']['old'] if 'repledge_amount' in changed_fields_map else ''
            })

        details_list.append({
            'field': 'updated_at', 'label': 'Created/Modified At', 'value': str(self.updated_at or self.created_at or 'N/A'),
            'is_changed': False, 'old_value': ''
        })

        # Construct structured plain-text fallback
        body_lines = [
            "Dear Team,\n",
            f"A loan has been {action.lower()} with the following details:\n"
        ]

        if changes:
            body_lines.append("⚡ MODIFIED / EDITED VALUES:")
            for change in changes:
                body_lines.append(f"  * {change['label']}: {change['old']} -> {change['new']}")
            body_lines.append("\nCOMPLETE LOAN DETAILS:")

        for item in details_list:
            if item['is_changed']:
                body_lines.append(f"[UPDATED] {item['label']}: {item['value']} (Previous: {item['old_value']})")
            else:
                body_lines.append(f"{item['label']}: {item['value']}")

        body_lines.append("\nPlease find the loan agreement PDF attached.\n")
        body_lines.append("Best regards,\nPawnshop Management System")
        plain_body = "\n".join(body_lines)

        # Render HTML template
        html_body = None
        try:
            html_body = render_to_string('transactions/emails/loan_notification_email.html', {
                'loan': self,
                'action': action,
                'is_create': is_create,
                'changes': changes,
                'details_list': details_list,
            })
        except Exception as e:
            print(f"Could not render loan notification email template: {e}")

        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_body,
            from_email=from_email,
            to=recipients,
        )

        if html_body:
            email.attach_alternative(html_body, "text/html")

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
        """Calculate remaining balance including interest due today"""
        if self.status != 'active':
            return Decimal('0.00')
        return self.total_payable_till_date

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
        """Calculate net payable (still due) - what customer owes right now including interest"""
        if self.status != 'active':
            return Decimal('0.00')
        return self.total_payable_till_date
    
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
        
        principal_amount = self.effective_principal_amount
        
        # Get scheme details from the scheme model
        if not self.scheme:
            return principal_amount
            
        # For schemes with no_interest_period_days, check if we're still in that period
        current_date = timezone.now().date()
        if self.scheme.no_interest_period_days and (current_date - self.issue_date).days <= self.scheme.no_interest_period_days:
            return principal_amount
            
        # Use monthly interest calculation instead of daily
        return principal_amount + self.monthly_interest_till_date()

    @property
    def total_payable_mature(self):
        """Calculate total amount payable at maturity using date-to-date month cycle"""
        if not self.due_date or self.status != 'active' or not self.scheme:
            return Decimal('0.00')
        
        principal_amount = self.effective_principal_amount
        
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
    
    @property
    def is_tiered_rate_loan(self):
        """Returns True if the loan's scheme has a tiered interest rate structure."""
        if not self.scheme:
            return False
        if getattr(self.scheme, 'interest_rate_structure', None):
            return len(self.scheme.interest_rate_structure) > 0
        return False

    @property
    def monthly_interest_due_date(self):
        """
        Calculates the monthly interest payment due date for the current cycle.
        Each month on the cycle day (issue_date.day or scheme.payment_due_day), interest is due.
        If is_first_month_interest_paid is True, month 1 was prepaid at origination.
        Payments made towards interest advance the paid cycles.
        """
        if not self.issue_date:
            return None
            
        import datetime
        from decimal import Decimal
        import calendar

        issue_dt = self.issue_date

        # Base annual rate for disciplined tier (30-day rate)
        if self.scheme and getattr(self.scheme, 'interest_rate_structure', None):
            base_annual_rate = Decimal(str(self.scheme.get_interest_rate_for_days(30)))
        elif self.scheme and getattr(self.scheme, 'interest_rate', None):
            base_annual_rate = Decimal(str(self.scheme.interest_rate))
        else:
            base_annual_rate = Decimal(str(self.interest_rate or 12))

        monthly_rate = base_annual_rate / Decimal('12')
        orig_dist = self.distribution_amount if self.distribution_amount is not None \
            else ((self.principal_amount or Decimal('0')) - Decimal(str(self.processing_fee or 0)))
        current_principal = self.principal_amount or Decimal('0')
        base_amount = min(orig_dist, current_principal)
        expected_monthly_interest = (base_amount * monthly_rate) / Decimal('100') if base_amount > 0 else Decimal('1.00')

        # Total interest paid through Payments
        total_interest_paid = Decimal('0.00')
        if self.pk:
            try:
                total_payments = sum([p.amount for p in self.payments.all()]) if hasattr(self, 'payments') else Decimal('0.00')
                total_interest_paid = Decimal(str(total_payments or 0))
            except Exception:
                total_interest_paid = Decimal('0.00')

        # Count months paid
        months_covered = 1 if self.is_first_month_interest_paid else 0
        if expected_monthly_interest > 0 and total_interest_paid > 0:
            months_covered += int(total_interest_paid // expected_monthly_interest)

        target_month_index = months_covered + 1
        
        # Calculate target calendar date by adding target_month_index months to issue_date
        year = issue_dt.year + (issue_dt.month + target_month_index - 1) // 12
        month = (issue_dt.month + target_month_index - 1) % 12 + 1
        day = issue_dt.day
        
        # Adjust day if target month has fewer days
        max_days = calendar.monthrange(year, month)[1]
        day = min(day, max_days)
        
        return datetime.date(year, month, day)

    @property
    def is_monthly_interest_overdue(self):
        """
        Returns True if the loan is active, has a monthly interest due date,
        and today has crossed that monthly pay date.
        """
        if self.status != 'active':
            return False
        due_dt = self.monthly_interest_due_date
        if not due_dt:
            return False
        return timezone.now().date() > due_dt

    @property
    def monthly_interest_overdue_days(self):
        """
        Returns the number of days the monthly interest payment is overdue.
        """
        if not self.is_monthly_interest_overdue:
            return 0
        due_dt = self.monthly_interest_due_date
        return max(0, (timezone.now().date() - due_dt).days)

    @property
    def current_applicable_rate(self):
        """
        Returns the effective annual interest rate (%) taking into account payment discipline:
        - For tiered rate structures:
          - If monthly interest is paid on time (not overdue): retains base/Level 1 tier rate.
          - If monthly interest pay date was missed: escalates to the tiered rate based on elapsed days/tenure.
        - For standard schemes: returns the standard interest rate.
        """
        if not self.scheme:
            return Decimal(str(self.interest_rate or 0))
            
        if not self.is_tiered_rate_loan:
            return Decimal(str(self.scheme.interest_rate or self.interest_rate or 0))

        # If tiered:
        # Check if monthly pay date was missed (overdue)
        if self.is_monthly_interest_overdue:
            # Rate escalates dynamically according to scheme tiered structure!
            today = timezone.now().date()
            if self.scheme.is_days_based:
                days_elapsed = (today - (self.issue_date or today)).days
                return Decimal(str(self.scheme.get_interest_rate_for_days(days_elapsed)))
            else:
                months_elapsed = max(1, ((today.year - self.issue_date.year) * 12 + today.month - self.issue_date.month))
                return Decimal(str(self.scheme.get_interest_rate_for_tenure(months_elapsed)))
        else:
            # Customer paid on time / on track: retains Level 1 base rate (30 days / Month 1)
            return Decimal(str(self.scheme.get_interest_rate_for_days(30)))

    @property
    def tiered_status_summary(self):
        """
        Returns a dictionary summarizing tiered rate status, active rate, next pay date, and discipline status.
        """
        if not self.is_tiered_rate_loan:
            return None

        active_rate = self.current_applicable_rate
        base_rate = Decimal(str(self.scheme.get_interest_rate_for_days(30))) if self.scheme else Decimal('12.00')
        is_escalated = active_rate > base_rate or self.is_monthly_interest_overdue
        due_dt = self.monthly_interest_due_date
        overdue_days = self.monthly_interest_overdue_days
        
        # Determine tier level name
        tier_level = "Tier 1"
        if hasattr(self.scheme, 'interest_rate_structure') and self.scheme.interest_rate_structure:
            idx = 1
            for k, r in self.scheme.interest_rate_structure.items():
                if Decimal(str(r)) == active_rate:
                    tier_level = f"Tier {idx}"
                    break
                idx += 1

        return {
            'is_tiered': True,
            'tier_level': tier_level,
            'active_rate': active_rate,
            'base_rate': base_rate,
            'monthly_pay_date': due_dt,
            'is_overdue': self.is_monthly_interest_overdue,
            'overdue_days': overdue_days,
            'is_escalated': is_escalated,
            'status_label': 'Pay Date Missed (Escalated)' if is_escalated else 'On Track (Base Rate)',
            'badge_class': 'bg-danger text-white' if is_escalated else 'bg-success text-white'
        }
        
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
            
        # Use current outstanding principal to reflect part payments
        orig_dist = self.distribution_amount if self.distribution_amount is not None \
            else ((self.principal_amount or Decimal('0')) - Decimal(str(self.processing_fee or 0)))
        base_dist_amount = min(orig_dist, self.principal_amount or Decimal('0'))
        
        # For schemes with no_interest_period_days, check if we're still in that period
        if self.scheme.no_interest_period_days and days_elapsed <= self.scheme.no_interest_period_days:
            return Decimal('0.00')
            
        # Calculate interest based on current applicable rate (base tier if on time, escalated if pay date missed)
        eff_rate = self.current_applicable_rate if self.is_tiered_rate_loan else self.scheme.interest_rate
        daily_rate = eff_rate / Decimal('36500')  # Convert annual rate to daily rate
        interest = base_dist_amount * daily_rate * Decimal(str(days_elapsed))
        
        return interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
    @property
    def monthly_interest(self):
        """Calculate monthly interest rate and amount for the loan.
        
        After part payments, interest is always calculated on current outstanding principal
        (whichever is lower: original distribution_amount or current principal_amount).
        """
        if not self.distribution_amount and not self.principal_amount:
            return {
                'rate': Decimal('0.00'),
                'amount': Decimal('0.00'),
                'per_thousand': Decimal('0.00'),
                'annual_rate': Decimal('0.00')
            }
        
        # Get interest rate from scheme or default with tiered pay date escalation
        if not self.scheme:
            annual_rate = Decimal(str(self.interest_rate or 0))
        elif self.is_tiered_rate_loan:
            annual_rate = self.current_applicable_rate
        else:
            annual_rate = Decimal(str(self.scheme.interest_rate or 0))
        
        # Calculate monthly interest rate
        monthly_rate = annual_rate / Decimal('12')
        
        # Base for interest = current outstanding principal (tracks part payments)
        orig_dist = self.distribution_amount if self.distribution_amount is not None \
            else ((self.principal_amount or Decimal('0')) - Decimal(str(self.processing_fee or 0)))
        current_principal = self.principal_amount or Decimal('0')
        base_amount = min(orig_dist, current_principal)
        monthly_interest_amount = (base_amount * monthly_rate) / Decimal('100')
        
        # Calculate per thousand rate (how much interest per 1000 of base amount)
        per_thousand = (monthly_rate / Decimal('100')) * Decimal('1000')
        
        return {
            'rate': monthly_rate.quantize(Decimal('0.01')),
            'amount': monthly_interest_amount.quantize(Decimal('0.01')),
            'per_thousand': per_thousand.quantize(Decimal('0.01')),
            'annual_rate': annual_rate.quantize(Decimal('0.01'))
        }

    @property
    def daily_interest_amount(self):
        """Calculate daily interest amount for the loan (per single day).
        
        After part payments, daily interest is calculated on the current outstanding
        principal (whichever is lower: original distribution_amount or principal_amount).
        """
        if not self.distribution_amount and not self.principal_amount:
            return Decimal('0.00')
        
        # Get interest rate from scheme or default with tiered pay date escalation
        if not self.scheme:
            annual_rate = Decimal(str(self.interest_rate or 0))
        elif self.is_tiered_rate_loan:
            annual_rate = self.current_applicable_rate
        else:
            annual_rate = Decimal(str(self.scheme.interest_rate or 0))
            
        # Use current outstanding principal to reflect part payments
        orig_dist = self.distribution_amount if self.distribution_amount is not None \
            else ((self.principal_amount or Decimal('0')) - Decimal(str(self.processing_fee or 0)))
        current_principal = self.principal_amount or Decimal('0')
        base_amount = min(orig_dist, current_principal)
        daily_amount = base_amount * (annual_rate / Decimal('36500'))
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
            
        # Use current outstanding principal to reflect part payments
        orig_dist = self.distribution_amount if self.distribution_amount is not None \
            else ((self.principal_amount or Decimal('0')) - Decimal(str(self.processing_fee or 0)))
        base_amount = min(orig_dist, self.principal_amount or Decimal('0'))
        
        if getattr(self.scheme, 'no_interest_period_days', 0) and days_elapsed <= self.scheme.no_interest_period_days:
            return Decimal('0.00')
            
        annual_rate = self.current_applicable_rate if self.is_tiered_rate_loan else self.scheme.get_interest_rate_for_days((current_date - self.issue_date).days)
        daily_rate = annual_rate / Decimal('36500')
        interest = base_amount * daily_rate * Decimal(str(days_elapsed))
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
                # Use current outstanding principal for overdue interest too
                orig_dist = self.distribution_amount if self.distribution_amount is not None \
                    else ((self.principal_amount or Decimal('0')) - Decimal(str(self.processing_fee or 0)))
                base_amount = min(orig_dist, self.principal_amount or Decimal('0'))
                extra_interest = base_amount * extra_interest_rate * Decimal(str(overdue_months))
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
                
            # Use current outstanding principal to reflect part payments
            orig_dist = self.distribution_amount if self.distribution_amount is not None \
                else ((self.principal_amount or Decimal('0')) - Decimal(str(self.processing_fee or 0)))
            base_amount = min(orig_dist, self.principal_amount or Decimal('0'))
            
            # For schemes with no_interest_period_days, check if we're still in that period
            if getattr(self.scheme, 'no_interest_period_days', 0) and days_elapsed <= self.scheme.no_interest_period_days:
                return Decimal('0.00')
                
            # Get tiered interest rate based on days elapsed
            annual_rate = self.scheme.get_interest_rate_for_days((current_date - self.issue_date).days)
            daily_rate = annual_rate / Decimal('36500')
            interest = base_amount * daily_rate * Decimal(str(days_elapsed))
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
        
        base_dist_amount = self.distribution_amount if self.distribution_amount is not None \
            else ((self.principal_amount or Decimal('0')) - Decimal(str(self.processing_fee or 0)))
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
    """Model to track items in a loan with their gold details and release status"""
    ITEM_STATUS_CHOICES = [
        ('pledged', _('Pledged (In Custody)')),
        ('released', _('Partially Released')),
        ('redeemed', _('Fully Redeemed')),
    ]
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
    
    # Partial Release Tracking (Task 2.3)
    status = models.CharField(max_length=20, choices=ITEM_STATUS_CHOICES, default='pledged', db_index=True)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='released_loan_items')
    
    class Meta:
        unique_together = ['loan', 'item']  # An item can only be used once in a loan
        
    def __str__(self):
        return f"{self.item.name} in {self.loan} ({self.get_status_display()})"

    @property
    def item_valuation(self):
        """Calculates current gold valuation for this item based on 22K market price"""
        try:
            karat = Decimal(str(self.gold_karat or 22.0))
            net_wt = Decimal(str(self.net_weight or 0.0))
            rate_22k = Decimal(str(self.market_price_22k or 0.0))
            if rate_22k <= Decimal('0.00'):
                from schemes.models import DailyGoldRate
                latest_rate = DailyGoldRate.objects.order_by('-date', '-id').first()
                if latest_rate:
                    rate_22k = latest_rate.rate_22k_per_gram
            val = (net_wt * (karat / Decimal('22.0')) * rate_22k)
            return val.quantize(Decimal('0.01'))
        except Exception:
            return Decimal('0.00')

class Payment(models.Model):
    """Payment model for tracking loan payments"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI QR / Digital'),
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('online', 'Online Payment'),
        ('other', 'Other'),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference_number = models.CharField(max_length=255, blank=True, null=True)  # Increased from 100 to 255
    utr_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        db_index=True, 
        help_text="12-digit Indian UPI / Bank transaction UTR reference number"
    )
    verification_status = models.CharField(
        max_length=20, 
        choices=VERIFICATION_STATUS_CHOICES, 
        default='verified', 
        db_index=True, 
        help_text="Verification status of the payment"
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='verified_payments',
        help_text="Staff or Branch Manager who verified the UTR"
    )
    verified_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when payment was verified")
    rejection_reason = models.TextField(blank=True, null=True, help_text="Reason for rejection if UTR is unverified/invalid")
    
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

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        # Income Tax Section 269ST: Daily cash repayment cap of ₹1,99,999 per customer across all branches
        if self.payment_method and str(self.payment_method).lower() == 'cash' and self.amount and hasattr(self, 'loan') and self.loan and self.payment_date:
            try:
                customer = self.loan.customer
                from django.db.models import Sum
                same_day_cash = Payment.objects.filter(
                    loan__customer=customer,
                    payment_date=self.payment_date,
                    payment_method__iexact='cash'
                )
                if self.pk:
                    same_day_cash = same_day_cash.exclude(pk=self.pk)
                
                existing_cash_total = same_day_cash.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                total_proposed = existing_cash_total + Decimal(str(self.amount))
                
                if total_proposed >= Decimal('200000.00'):
                    max_allowed = max(Decimal('0.00'), Decimal('199999.00') - existing_cash_total)
                    raise ValidationError(
                        f"Section 269ST Violation: Total daily cash repayments from a customer across all branches cannot reach or exceed ₹2,00,000 (Maximum cash allowed per day is ₹1,99,999). "
                        f"Today's existing cash repayments for {customer.full_name}: ₹{existing_cash_total:,.2f}. "
                        f"Maximum cash remaining for today: ₹{max_allowed:,.2f}. "
                        f"Please select a digital mode (Bank Transfer, UPI, Cheque, or NetBanking)."
                    )
            except Exception:
                pass

        # Prevent excess payment over outstanding balance
        if self.amount and hasattr(self, 'loan') and self.loan:
            try:
                rem_balance = max(Decimal('0.00'), self.loan.total_payable_till_date)
                if self.pk:
                    old_payment = Payment.objects.filter(pk=self.pk).first()
                    if old_payment:
                        rem_balance += old_payment.amount
                
                if Decimal(str(self.amount)) > rem_balance:
                    raise ValidationError({
                        'amount': f"Payment amount of ₹{Decimal(str(self.amount)):,.2f} exceeds the outstanding balance of ₹{rem_balance:,.2f}. Maximum payable amount is ₹{rem_balance:,.2f}."
                    })
            except ValidationError:
                raise
            except Exception:
                pass

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Send customer receipt email after DB commit (fail silently)
        try:
            payment_pk = self.pk
            def _send_receipt():
                try:
                    from transactions.services_email import send_customer_payment_email
                    from transactions.models import Payment as _Payment
                    p = _Payment.objects.select_related('loan__customer', 'loan__branch').get(pk=payment_pk)
                    send_customer_payment_email(p)
                except Exception as _exc:
                    import logging as _logging
                    _logging.getLogger(__name__).warning(
                        "Payment receipt email failed for pk=%s: %s", payment_pk, _exc
                    )
            from django.db import transaction as _transaction
            _transaction.on_commit(_send_receipt)
        except Exception:
            pass


class DisbursementTransaction(models.Model):
    """
    Model for recording loan disbursals with statutory Income Tax Sec 269SS/269T compliance.
    Disbursals >= ₹20,000 must be made via electronic clearing/bank transfer/UPI/Cheque.
    """
    DISBURSEMENT_MODE_CHOICES = [
        ('CASH', _('Cash')),
        ('BANK_TRANSFER', _('Bank Transfer (NEFT/RTGS/IMPS)')),
        ('UPI', _('UPI')),
        ('CHEQUE', _('Cheque / DD')),
    ]
    BANK_STATUS_CHOICES = [
        ('PENDING', _('Pending')),
        ('PROCESSED', _('Processed / Success')),
        ('FAILED', _('Failed')),
    ]

    loan = models.OneToOneField(Loan, on_delete=models.CASCADE, related_name='disbursement_detail')
    payment_mode = models.CharField(max_length=30, choices=DISBURSEMENT_MODE_CHOICES, default='CASH')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    utr_number = models.CharField(max_length=100, blank=True, null=True, help_text=_("Bank UTR / Transaction Reference"))
    transaction_reference = models.CharField(max_length=100, blank=True, null=True)

    # Customer Bank Account Details for Payout
    account_number = models.CharField(max_length=50, blank=True, null=True, help_text=_("Beneficiary Account Number"))
    ifsc_code = models.CharField(max_length=20, blank=True, null=True, help_text=_("Bank IFSC Code"))
    bank_name = models.CharField(max_length=100, blank=True, null=True, help_text=_("Bank Name"))
    beneficiary_name = models.CharField(max_length=150, blank=True, null=True, help_text=_("Beneficiary Name"))

    bank_status = models.CharField(max_length=20, choices=BANK_STATUS_CHOICES, default='PROCESSED')
    disbursed_at = models.DateTimeField(default=timezone.now)
    disbursed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='disbursements_made')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('disbursement transaction')
        verbose_name_plural = _('disbursement transactions')
        ordering = ['-disbursed_at']

    def __str__(self):
        return f"Disbursement for {self.loan} - ₹{self.amount} ({self.payment_mode})"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        # Tiered Approval Enforcer: Loan must not be in draft, pending_approval, or rejected for processed disbursals
        if hasattr(self, 'loan') and self.loan:
            if self.bank_status == 'PROCESSED' and self.loan.status in ['pending_approval', 'rejected', 'draft']:
                raise ValidationError(
                    _(f"Disbursal Blocked: Loan #{self.loan.loan_number} is currently '{self.loan.get_status_display()}'. "
                      f"Customer identity OTP verification and Manager Approval must be completed before money disbursal.")
                )
        # Sec 269SS Enforcer: >= ₹20,000 cannot be in Cash
        if self.payment_mode == 'CASH' and self.amount and Decimal(str(self.amount)) >= Decimal('20000.00'):
            raise ValidationError(
                _("Under Section 269SS of the Income Tax Act, loan disbursements of ₹20,000 or more cannot be paid in Cash. "
                  "Please select Bank Transfer, NEFT, IMPS, RTGS, UPI, or Cheque.")
            )
        if self.payment_mode in ['BANK_TRANSFER', 'NEFT', 'IMPS', 'RTGS'] and not self.account_number:
            raise ValidationError({'account_number': _("Bank account number is required for bank disbursements.")})
        if self.payment_mode in ['BANK_TRANSFER', 'NEFT', 'IMPS', 'RTGS'] and not self.ifsc_code:
            raise ValidationError({'ifsc_code': _("Bank IFSC code is required for bank disbursements.")})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Transition loan from approved to active upon successful disbursal
        if self.loan and self.loan.status == 'approved':
            self.loan.status = 'active'
            self.loan.save(update_fields=['status'])


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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    sale_date = models.DateField(db_index=True)
    
    # Management
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                              null=True, related_name='sales_processed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('sale')
        verbose_name_plural = _('sales')
        ordering = ['-sale_date']
        indexes = [
            # Dashboard: today's revenue = sale_date filter + SUM(total_amount)
            models.Index(fields=['sale_date'], name='sale_date_idx'),
            # Branch filtering on sale list
            models.Index(fields=['branch', 'status'], name='sale_branch_status_idx'),
        ]
    
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


class InterestAccrualLog(models.Model):
    """
    Log of Daily Mathematical Interest Accrued per Loan during EOD Batch.
    Formula: (Principal Outstanding * Annual Interest Rate) / (365 * 100)
    """
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='accrual_logs')
    date = models.DateField(db_index=True)
    principal_outstanding = models.DecimalField(max_digits=12, decimal_places=2)
    annual_rate = models.DecimalField(max_digits=5, decimal_places=2)
    daily_interest_accrued = models.DecimalField(max_digits=10, decimal_places=2)
    cumulative_interest = models.DecimalField(max_digits=12, decimal_places=2)
    irac_status = models.CharField(max_length=20, default='STANDARD')
    is_posted_to_gl = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('interest accrual log')
        verbose_name_plural = _('interest accrual logs')
        ordering = ['-date']
        unique_together = ('loan', 'date')

    def __str__(self):
        return f"Accrual for Loan #{self.loan.loan_number} on {self.date}: ₹{self.daily_interest_accrued}"


class EODBatchExecutionLog(models.Model):
    """
    Audit log of End-of-Day (EOD) Batch Processing Runs across branches.
    """
    STATUS_CHOICES = [
        ('IN_PROGRESS', _('In Progress')),
        ('COMPLETED', _('Completed')),
        ('FAILED', _('Failed')),
    ]
    execution_date = models.DateField(db_index=True)
    branch = models.ForeignKey('branches.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='eod_runs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED')
    total_loans_processed = models.IntegerField(default=0)
    total_daily_interest_accrued = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    standard_count = models.IntegerField(default=0)
    sma0_count = models.IntegerField(default=0)
    sma1_count = models.IntegerField(default=0)
    sma2_count = models.IntegerField(default=0)
    npa_count = models.IntegerField(default=0)
    gl_journal_entry = models.ForeignKey('accounting.JournalEntry', on_delete=models.SET_NULL, null=True, blank=True, related_name='eod_runs')
    executed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    logs = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _('EOD batch execution log')
        verbose_name_plural = _('EOD batch execution logs')
        ordering = ['-execution_date', '-started_at']

    def __str__(self):
        branch_name = self.branch.name if self.branch else "Consolidated"
        return f"EOD Batch {self.execution_date} ({branch_name}) - ₹{self.total_daily_interest_accrued} Accrued"


class PartialReleaseRecord(models.Model):
    """
    Model for tracking Partial Ornament Releases and Part-Payments.
    Enforces maximum 75% LTV on remaining pledged ornaments.
    """
    release_number = models.CharField(max_length=50, unique=True, db_index=True)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='partial_releases')
    payment = models.ForeignKey('transactions.Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='partial_releases')
    released_items = models.ManyToManyField(LoanItem, related_name='partial_release_records')
    release_date = models.DateField(default=timezone.now, db_index=True)
    
    # Financial reconciliation
    principal_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    interest_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    previous_outstanding_principal = models.DecimalField(max_digits=12, decimal_places=2)
    new_outstanding_principal = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Collateral LTV metrics
    remaining_gold_value = models.DecimalField(max_digits=12, decimal_places=2, help_text="Market value of retained items")
    new_ltv_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="New LTV % after partial release (must be <= 75%)")
    
    # Sign-off & audit
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_partial_releases')
    customer_signature_data = models.TextField(blank=True, null=True, help_text="Base64 encoded customer signature")
    witness_name = models.CharField(max_length=150, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('partial release record')
        verbose_name_plural = _('partial release records')
        ordering = ['-release_date', '-created_at']

    def __str__(self):
        return f"Partial Release #{self.release_number} for Loan #{self.loan.loan_number}"


class MarketingCampaignTemplate(models.Model):
    """
    Stores built-in and user-customized WhatsApp & Digital Marketing Campaign Templates.
    Allows saving Gemini AI generated templates as new presets or overwriting existing templates.
    """
    key = models.CharField(max_length=100, unique=True, db_index=True)
    title_en = models.CharField(max_length=255)
    title_ta = models.CharField(max_length=255)
    category = models.CharField(max_length=100, default='Custom')
    badge = models.CharField(max_length=50, default='Custom')
    body_en = models.TextField(blank=True, default='')
    body_ta = models.TextField(blank=True, default='')
    is_custom = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_marketing_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Marketing Campaign Template')
        verbose_name_plural = _('Marketing Campaign Templates')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title_en} ({self.key})"


class MarketingGroup(models.Model):
    """
    Stores named marketing groups (e.g. 'Diwali Mela 2026', 'VIP Buyers')
    for targeted WhatsApp broadcasts and bulk campaigns.
    """
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True, null=True)
    branch = models.ForeignKey('branches.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='marketing_groups')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Marketing Group')
        verbose_name_plural = _('Marketing Groups')
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class MarketingLead(models.Model):
    """
    Stores external prospect leads (imported via CSV or added manually)
    who are not yet registered customers, for WhatsApp broadcasts & marketing campaigns.
    """
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=25)
    norm_phone = models.CharField(max_length=25, blank=True, db_index=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    group = models.ForeignKey(MarketingGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='leads')
    branch = models.ForeignKey('branches.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='marketing_leads')
    notes = models.CharField(max_length=255, blank=True, null=True)
    source = models.CharField(max_length=50, default='csv_import')  # 'csv_import', 'manual_entry'
    is_contacted = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Marketing Lead')
        verbose_name_plural = _('Marketing Leads')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.phone})"


class MarketingCampaignLog(models.Model):
    """
    Audit log of all marketing broadcasts and campaign dispatches across WhatsApp, SMS, and PyWhatKit.
    """
    CHANNEL_CHOICES = (
        ('whatsapp_web', _('WhatsApp Web (Direct Link)')),
        ('pywhatkit', _('PyWhatKit Auto-Blast')),
        ('sms', _('SMS Gateway')),
        ('api', _('Cloud API')),
    )
    STATUS_CHOICES = (
        ('sent', _('Sent')),
        ('queued', _('Queued')),
        ('failed', _('Failed')),
    )

    template_key = models.CharField(max_length=100, blank=True, default='')
    campaign_name = models.CharField(max_length=255, blank=True, default='Broadcast')
    recipient_name = models.CharField(max_length=150)
    recipient_phone = models.CharField(max_length=25)
    recipient_type = models.CharField(max_length=30, default='customer')  # 'customer', 'lead'
    group = models.ForeignKey(MarketingGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaign_logs')
    branch = models.ForeignKey('branches.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='campaign_logs')
    channel = models.CharField(max_length=50, choices=CHANNEL_CHOICES, default='whatsapp_web')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='sent')
    message_snippet = models.TextField(blank=True, default='')
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_campaign_logs')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('Marketing Campaign Log')
        verbose_name_plural = _('Marketing Campaign Logs')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.campaign_name} to {self.recipient_name} ({self.recipient_phone}) - {self.status}"


class IRACAlertLog(models.Model):
    """
    Tracks all automated and manual regulatory IRAC overdue alerts, pre-NPA warnings,
    and statutory auction notices dispatched to borrowers.
    """
    BUCKET_CHOICES = (
        ('SMA_0', _('SMA-0 (1-30 Days Overdue)')),
        ('SMA_1', _('SMA-1 (31-60 Days Overdue)')),
        ('SMA_2', _('SMA-2 (61-90 Days Overdue / Pre-NPA)')),
        ('NPA_SUBSTANDARD', _('NPA Substandard (91-180 Days)')),
        ('NPA_DOUBTFUL', _('NPA Doubtful (181-365 Days)')),
        ('NPA_LOSS', _('NPA Loss (>365 Days / Auction Stage)')),
    )
    CHANNEL_CHOICES = (
        ('whatsapp_web', _('WhatsApp Web')),
        ('pywhatkit', _('PyWhatKit Auto-Blast')),
        ('sms', _('SMS Gateway')),
        ('letter', _('Formal Letter / Notice')),
    )
    STATUS_CHOICES = (
        ('sent', _('Sent')),
        ('failed', _('Failed')),
        ('delivered', _('Delivered')),
    )

    loan = models.ForeignKey('transactions.Loan', on_delete=models.CASCADE, related_name='irac_alert_logs')
    customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE, related_name='irac_alert_logs')
    irac_bucket = models.CharField(max_length=30, choices=BUCKET_CHOICES, db_index=True)
    overdue_days = models.IntegerField(default=0)
    overdue_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, default='whatsapp_web')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    message_sent = models.TextField(blank=True, default='')
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatched_irac_alerts')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('IRAC Alert Log')
        verbose_name_plural = _('IRAC Alert Logs')
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.irac_bucket}] Alert for Loan #{self.loan.loan_number} - {self.customer} ({self.created_at.strftime('%d-%b-%Y')})"


class LoanWhatsAppLog(models.Model):
    """
    Tracks complete WhatsApp notification dispatch history for a Loan,
    recording status (sent/failed), message short info, failure error details,
    channel, recipient phone, and dispatcher.
    """
    STATUS_CHOICES = (
        ('sent', _('Sent')),
        ('failed', _('Failed')),
        ('delivered', _('Delivered')),
        ('pending', _('Pending')),
    )
    CHANNEL_CHOICES = (
        ('automated_browser', _('Playwright Automated Web')),
        ('pywhatkit', _('PyWhatKit Automation')),
        ('direct_link', _('WhatsApp Direct URL')),
        ('eod_cron', _('EOD Scheduled Dispatch')),
        ('manual', _('Manual Staff Dispatch')),
    )

    loan = models.ForeignKey('transactions.Loan', on_delete=models.CASCADE, related_name='whatsapp_logs')
    customer = models.ForeignKey('accounts.Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='loan_whatsapp_logs')
    recipient_phone = models.CharField(max_length=30, blank=True, default='')
    notification_type = models.CharField(max_length=60, default='reminder')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent', db_index=True)
    message_content = models.TextField(blank=True, default='')
    error_message = models.TextField(blank=True, default='')
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, default='automated_browser')
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='loan_dispatched_whatsapp_logs')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('Loan WhatsApp Log')
        verbose_name_plural = _('Loan WhatsApp Logs')
        ordering = ['-created_at']

    def __str__(self):
        return f"WhatsApp [{self.status.upper()}] Loan #{self.loan.loan_number} to {self.recipient_phone} ({self.created_at.strftime('%d-%b-%Y %H:%M')})"

    @property
    def short_message(self):
        """Returns clean short snippet of the message content"""
        if not self.message_content:
            return ""
        clean = " ".join(self.message_content.split())
        if len(clean) > 85:
            return clean[:85] + "..."
        return clean

    @property
    def notification_label(self):
        labels = {
            'overdue': _('Overdue Reminder'),
            'reminder': _('Due Date Reminder'),
            'monthly_interest': _('Tiered Rate Monthly Interest Notice'),
            'demand_notice': _('Statutory Demand Notice'),
            'auction_notice': _('Gold Auction Warning'),
            'loan_created': _('Loan Creation Welcome'),
            'payment_receipt': _('Payment Receipt Acknowledgement'),
            'custom': _('Custom Message'),
        }
        return labels.get(self.notification_type, self.notification_type.replace('_', ' ').title())


class GoldPurchase(models.Model):
    """
    Model for Outright Used / Old Gold Purchase transactions directly from customers.
    """
    PAYMENT_METHOD_CHOICES = (
        ('cash', _('Cash')),
        ('bank_transfer', _('Bank Transfer (NEFT/RTGS/IMPS)')),
        ('upi', _('UPI / Digital')),
        ('cheque', _('Cheque')),
    )

    STATUS_CHOICES = (
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    )

    ID_PROOF_CHOICES = (
        ('aadhaar', _('Aadhaar Card')),
        ('pan', _('PAN Card')),
        ('voter_id', _('Voter ID')),
        ('driving_license', _('Driving License')),
        ('passport', _('Passport')),
        ('other', _('Other Official ID')),
    )

    purchase_number = models.CharField(max_length=50, unique=True, db_index=True)
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='gold_purchases')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='gold_purchases')
    purchase_date = models.DateField(default=timezone.now, db_index=True)

    # Weights
    total_gross_weight = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0.000'), help_text="Total gross weight in grams")
    total_stone_weight = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0.000'), help_text="Total stone deduction in grams")
    total_net_weight = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0.000'), help_text="Total net weight in grams")
    total_payable_weight = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0.000'), help_text="Total payable net weight in grams")
    total_fine_gold_weight = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0.000'), help_text="24K pure gold equivalent in grams")

    # Financials
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    melting_deduction_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_payable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Final amount paid to customer")

    # Payment & KYC
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    reference_number = models.CharField(max_length=255, blank=True, null=True, help_text="Bank UTR / Cheque / Transaction ref")
    id_proof_type = models.CharField(max_length=30, choices=ID_PROOF_CHOICES, default='aadhaar', blank=True)
    id_proof_number = models.CharField(max_length=100, blank=True, null=True)
    customer_photo = models.TextField(blank=True, null=True, help_text="Base64-encoded customer face photo")
    kyc_document = models.ImageField(upload_to='gold_purchases/kyc/', blank=True, null=True, help_text="Uploaded KYC document image")
    kyc_document_data = models.TextField(blank=True, null=True, help_text="Base64-encoded KYC document file data")
    item_photos = models.TextField(blank=True, null=True, help_text="JSON array of base64 photos for gold items")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed', db_index=True)
    notes = models.TextField(blank=True, null=True)
    
    # Audit
    purchased_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='gold_purchases_handled')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Gold Purchase')
        verbose_name_plural = _('Gold Purchases')
        ordering = ['-purchase_date', '-id']

    def __str__(self):
        return f"Purchase #{self.purchase_number} - {self.customer} (Rs. {self.net_payable_amount})"

    @classmethod
    def generate_purchase_number(cls, branch=None):
        now = timezone.now()
        b_code = 'DEF'
        if branch and branch.name:
            b_code = ''.join([c.upper() for c in branch.name if c.isalpha()])[:3]
            if len(b_code) < 3:
                b_code = (b_code + 'DEF')[:3]
        date_str = now.strftime('%Y%m%d')
        base_prefix = f"BUY-{b_code}-{date_str}"
        last_obj = cls.objects.filter(purchase_number__startswith=base_prefix).order_by('-purchase_number').first()
        if last_obj:
            try:
                seq = int(last_obj.purchase_number.split('-')[-1]) + 1
            except Exception:
                seq = 1
        else:
            seq = 1
        return f"{base_prefix}-{seq:04d}"


class GoldPurchaseItem(models.Model):
    """
    Individual gold item / ornament in a GoldPurchase transaction.
    """
    PURITY_CHOICES = (
        ('24K', '24K (99.9% Pure Gold)'),
        ('22K', '22K (91.6% Standard Gold / 916 Hallmark)'),
        ('20K', '20K (83.3% Gold)'),
        ('18K', '18K (75.0% Gold)'),
        ('14K', '14K (58.5% Gold)'),
        ('scrap', 'Scrap / Mixed Gold / Melted Bar'),
    )

    purchase = models.ForeignKey(GoldPurchase, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=200, help_text="e.g. 22K Gold Chain, Ring, Bangles, Scrap Bar")
    purity_karat = models.CharField(max_length=10, choices=PURITY_CHOICES, default='22K')
    purity_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('91.60'))
    
    gross_weight = models.DecimalField(max_digits=10, decimal_places=3, help_text="Gross weight in grams")
    stone_weight = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('0.000'), help_text="Stone deduction in grams")
    net_weight = models.DecimalField(max_digits=10, decimal_places=3, help_text="Net gold weight in grams")
    
    melting_loss_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Melting / assay loss %")
    payable_net_weight = models.DecimalField(max_digits=10, decimal_places=3, help_text="Payable net weight after melting loss")
    
    rate_per_gram = models.DecimalField(max_digits=10, decimal_places=2, help_text="Buying rate applied per gram")
    item_total_value = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total value for this item")
    
    inventory_item = models.ForeignKey('inventory.Item', on_delete=models.SET_NULL, null=True, blank=True, related_name='gold_purchase_source')

    class Meta:
        verbose_name = _('Gold Purchase Item')
        verbose_name_plural = _('Gold Purchase Items')

    def __str__(self):
        return f"{self.item_name} ({self.purity_karat} - {self.gross_weight}g)"


class AutopilotConfig(models.Model):
    """
    Centralized Configuration & State for the 24/7 Autopilot Automation System.
    Stores toggles and parameters for Pillars 2, 3, 4, and 5 (Excludes Pillar 1).
    """
    # Master switch
    is_enabled = models.BooleanField(default=False, verbose_name=_('Autopilot Master Switch'), help_text=_('Enable 24/7 automated background execution.'))

    # Pillar 2: Automated WhatsApp Collections & Delinquency Dispatch
    enable_due_date_reminders = models.BooleanField(default=True, verbose_name=_('Due-Date Reminders'))
    due_reminder_days = models.CharField(max_length=50, default='7,3,1', help_text=_('Comma-separated days before due date (e.g. 7,3,1)'))
    enable_monthly_interest_reminders = models.BooleanField(default=True, verbose_name=_('Monthly Interest Reminders (Tiered Loans)'))
    enable_irac_delinquency_alerts = models.BooleanField(default=True, verbose_name=_('RBI IRAC Delinquency Warnings (SMA-0/1/2)'))
    enable_expiry_auction_notices = models.BooleanField(default=True, verbose_name=_('Demand & Auction Notices (NPA / 90+ Days)'))
    whatsapp_dispatch_time = models.TimeField(default='10:00:00', verbose_name=_('Daily WhatsApp Dispatch Time'))
    dispatch_channel = models.CharField(
        max_length=30,
        choices=(('headless_automated', _('Automated Headless Web')), ('pywhatkit', _('PyWhatKit Automation'))),
        default='headless_automated'
    )

    # Pillar 3: Automated Gold Price & LTV Risk Surveillance
    enable_ltv_surveillance = models.BooleanField(default=True, verbose_name=_('LTV Risk Surveillance'))
    ltv_warning_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('75.00'), verbose_name=_('LTV Warning Threshold (%)'))
    ltv_critical_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('85.00'), verbose_name=_('LTV Critical Margin Call Threshold (%)'))
    ltv_check_time = models.TimeField(default='11:00:00', verbose_name=_('Daily LTV Check Time'))

    # Pillar 4: Automated Customer Retention & Marketing
    enable_repledge_retention = models.BooleanField(default=True, verbose_name=_('Closed Loan Re-Pledge Promos'))
    repledge_cooldown_days = models.IntegerField(default=30, verbose_name=_('Closed Loan Cooldown (Days)'))
    enable_birthday_greetings = models.BooleanField(default=True, verbose_name=_('Birthday Greetings'))
    enable_anniversary_greetings = models.BooleanField(default=True, verbose_name=_('Wedding Anniversary Greetings'))
    marketing_dispatch_time = models.TimeField(default='15:00:00', verbose_name=_('Marketing Dispatch Time'))

    # Pillar 5: Automated Executive Daily Digest to Owner
    enable_owner_digest = models.BooleanField(default=True, verbose_name=_('Owner Nightly WhatsApp Digest'))
    owner_phone = models.CharField(max_length=25, blank=True, default='', verbose_name=_('Owner WhatsApp Phone (with Country Code)'))
    owner_email = models.EmailField(blank=True, default='', verbose_name=_('Owner Email (Optional)'))
    digest_time = models.TimeField(default='20:30:00', verbose_name=_('Nightly Digest Time'))

    # Safety & Compliance Guardrails (TRAI Safe Windows & Anti-Spam)
    safe_window_start = models.TimeField(default='09:00:00', verbose_name=_('Safe Window Start (TRAI)'))
    safe_window_end = models.TimeField(default='19:30:00', verbose_name=_('Safe Window End (TRAI)'))
    max_daily_messages = models.IntegerField(default=150, verbose_name=_('Max WhatsApp Messages / Day'))
    min_days_between_reminders = models.IntegerField(default=5, verbose_name=_('Anti-Spam Cooldown (Days per Loan)'))

    # Health State & Circuit Breakers
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=20, default='idle')
    last_log_summary = models.TextField(blank=True, default='')
    consecutive_failures = models.IntegerField(default=0)
    is_paused_by_circuit_breaker = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Autopilot Configuration')
        verbose_name_plural = _('Autopilot Configurations')

    def __str__(self):
        status_str = "ACTIVE (ON)" if self.is_enabled else "PAUSED (OFF)"
        return f"Autopilot Engine [{status_str}]"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class AutopilotLog(models.Model):
    """
    Execution & Activity Audit Log for all Autopilot Operations.
    """
    PILLAR_CHOICES = (
        ('pillar_2', _('Pillar 2: WhatsApp Collections & Reminders')),
        ('pillar_3', _('Pillar 3: LTV Risk Surveillance')),
        ('pillar_4', _('Pillar 4: Retention & Marketing')),
        ('pillar_5', _('Pillar 5: Owner Daily Digest')),
        ('system', _('System / Engine Lifecycle')),
    )
    STATUS_CHOICES = (
        ('success', _('Success')),
        ('partial', _('Partial Success')),
        ('failed', _('Failed')),
        ('skipped', _('Skipped / Out of Safe Window')),
    )

    pillar = models.CharField(max_length=30, choices=PILLAR_CHOICES, db_index=True)
    action_name = models.CharField(max_length=100)
    target_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    summary = models.TextField(blank=True, default='')
    error_details = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    executed_by = models.CharField(max_length=50, default='Autopilot Daemon')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('Autopilot Activity Log')
        verbose_name_plural = _('Autopilot Activity Logs')
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_pillar_display()}] {self.action_name} - {self.status.upper()} ({self.created_at.strftime('%d-%b %H:%M')})"



