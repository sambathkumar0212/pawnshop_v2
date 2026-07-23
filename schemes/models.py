from django.db import models
from django.utils import timezone
from branches.models import Branch
from accounts.models import CustomUser
from django.urls import reverse

class Scheme(models.Model):
    """
    Model to store scheme details that can be managed by branch managers or regional managers.
    """
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('upcoming', 'Upcoming'),
        ('expired', 'Expired'),
    )

    name = models.CharField(max_length=100, help_text="Name of the scheme")
    description = models.TextField(help_text="Detailed description of the scheme")
    
    # Flag for default schemes that are available to all organizations
    is_default = models.BooleanField(default=False, help_text="If true, this scheme is available to all organizations")
    
    # Gold scheme specific fields
    is_gold_scheme = models.BooleanField(default=False, help_text="Whether this is a gold loan scheme")
    gold_interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Interest rate for gold loans (Rupees per 100 Rupees per month)"
    )
    expiry_period = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Expiry period for gold loans in months"
    )
    minimum_duration = models.PositiveIntegerField(
        null=True, blank=True, default=0,
        help_text="Minimum duration for gold loans in days"
    )
    late_payment_interest = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Additional interest for late payment (Rupees per 100 Rupees per month)"
    )
    payment_due_day = models.PositiveSmallIntegerField(
        null=True, blank=True, default=5,
        help_text="Day of month when payment is due"
    )
    special_conditions = models.TextField(
        null=True, blank=True,
        help_text="Special conditions for gold loans"
    )
    is_fixed_interest = models.BooleanField(
        default=False,
        help_text="Whether the interest rate is fixed (no additional charges)"
    )
    auction_on_expiry = models.BooleanField(
        default=False,
        help_text="Whether the gold will be auctioned if not redeemed by expiry"
    )
    
    # Tiered Interest Rate System fields
    early_period_months = models.PositiveIntegerField(
        null=True, blank=True, default=1,
        help_text="Duration of early period in months (for reduced interest rate)"
    )
    early_period_interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Reduced interest rate for early repayment (Rupees per 100 Rupees per month)"
    )
    standard_period_months = models.PositiveIntegerField(
        null=True, blank=True, default=2,
        help_text="Duration of standard period in months (for normal interest rate)"
    )
    late_period_interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Increased interest rate for late period (Rupees per 100 Rupees per month)"
    )
    processing_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, default=1.0,
        help_text="Processing fee as percentage of loan amount"
    )
    
    # Organization for multi-tenancy
    organization = models.ForeignKey(
        'accounts.Organization', on_delete=models.CASCADE, null=True, blank=True,
        related_name='schemes',
        help_text="Organization this scheme belongs to (null for default schemes)"
    )
    
    # Conditions
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, 
                                       help_text="Interest rate for the scheme (Yearly in %, Eg: 12%)")
    # Dynamic interest rate structure based on loan tenure
    interest_rate_structure = models.JSONField(null=True, blank=True, 
                                            help_text="Dynamic interest rates based on tenure in JSON format. Example: {'0-1': 12, '1-3': 18, '3-6': 24, '6+': 36}")
    loan_duration = models.PositiveIntegerField(
        help_text="Standard loan duration in days")
    minimum_amount = models.DecimalField(max_digits=10, decimal_places=2, 
                                       help_text="Minimum loan amount")
    maximum_amount = models.DecimalField(max_digits=10, decimal_places=2, 
                                       help_text="Maximum loan amount")
    
    # Additional conditions - can be stored as JSON
    additional_conditions = models.JSONField(null=True, blank=True, 
                                           help_text="Additional conditions in JSON format")
    
    # Dates
    start_date = models.DateField(help_text="Date when the scheme becomes active")
    end_date = models.DateField(null=True, blank=True, 
                               help_text="Date when the scheme expires (leave blank for ongoing)")
    
    # Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, 
        related_name='created_schemes'
    )
    updated_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, 
        related_name='updated_schemes'
    )
    
    # Branch association (can be null for global schemes)
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, null=True, blank=True,
        related_name='loan_schemes',
        help_text="Branch the scheme is associated with (leave empty for global schemes)"
    )

    class Meta:
        ordering = ['-created_at']
        permissions = [
            ("view_all_schemes", "Can view all schemes including from other branches"),
            ("manage_global_schemes", "Can manage schemes that apply globally"),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['start_date']),
            models.Index(fields=['branch']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('scheme_detail', kwargs={'pk': self.pk})
    
    @property
    def is_active(self):
        today = timezone.now().date()
        return (self.status == 'active' and 
                self.start_date <= today and 
                (not self.end_date or self.end_date >= today))
    
    @property
    def no_interest_period_days(self):
        """Returns the no_interest_period_days from additional_conditions if present"""
        if self.additional_conditions and 'no_interest_period_days' in self.additional_conditions:
            return self.additional_conditions['no_interest_period_days']
        return None
        
    def get_interest_rate_for_tenure(self, tenure_months):
        """
        Returns the appropriate interest rate based on the loan tenure in months.
        If interest_rate_structure is not defined, falls back to the default interest_rate.
        """
        from decimal import Decimal
        
        if not self.interest_rate_structure:
            return self.interest_rate
            
        if self.is_days_based:
            return self.get_interest_rate_for_days(int(tenure_months) * 30)
            
        tenure = Decimal(str(tenure_months))
        
        for range_key, rate in self.interest_rate_structure.items():
            if '-' in range_key:
                start, end = range_key.split('-')
                if start and end:
                    if Decimal(start) <= tenure <= Decimal(end):
                        return Decimal(str(rate))
                elif start:
                    if Decimal(start) <= tenure:
                        return Decimal(str(rate))
            elif range_key.endswith('+'):
                min_value = Decimal(range_key.rstrip('+'))
                if tenure >= min_value:
                    return Decimal(str(rate))
            elif range_key == str(int(tenure)):
                return Decimal(str(rate))
                
        return self.interest_rate

    @property
    def is_days_based(self):
        """Returns True if the tiered rate structure is days-based"""
        if not self.interest_rate_structure:
            return False
        for key in self.interest_rate_structure.keys():
            clean_key = key.replace('+', '')
            parts = clean_key.split('-')
            for part in parts:
                if part.strip().isdigit() and int(part.strip()) > 12:
                    return True
        return False

    def get_interest_rate_for_days(self, days_elapsed):
        """
        Returns the appropriate interest rate based on the loan tenure in days.
        If interest_rate_structure is not defined, falls back to the default interest_rate.
        """
        from decimal import Decimal
        
        if not self.interest_rate_structure:
            return self.interest_rate
            
        if not self.is_days_based:
            months = max(1, int(days_elapsed // 30))
            return self.get_interest_rate_for_tenure(months)
            
        days = Decimal(str(days_elapsed))
        
        # Sort key ranges to check from smallest to largest end bounds
        sorted_keys = []
        for range_key, rate in self.interest_rate_structure.items():
            if '-' in range_key:
                start, end = range_key.split('-')
                if start and end:
                    sorted_keys.append((Decimal(start), Decimal(end), range_key, Decimal(str(rate))))
                elif start:
                    sorted_keys.append((Decimal(start), Decimal('999999'), range_key, Decimal(str(rate))))
            elif range_key.endswith('+'):
                min_val = Decimal(range_key.rstrip('+'))
                sorted_keys.append((min_val, Decimal('999999'), range_key, Decimal(str(rate))))
            elif range_key.isdigit():
                val = Decimal(range_key)
                sorted_keys.append((val, val, range_key, Decimal(str(rate))))
        
        # Sort primarily by lower bound, then upper bound
        sorted_keys.sort()
        
        for start, end, range_key, rate in sorted_keys:
            if start <= days <= end:
                return rate
                
        # If no matching range found, return default
        return self.interest_rate
    
    def get_tiered_rate_structure_display(self):
        """
        Returns structured list of tiers matching Scheme Form creation for display in scheme templates.
        """
        from decimal import Decimal
        tiers = []
        is_days = self.is_days_based
        unit = "Days" if is_days else "Months"
        
        if self.interest_rate_structure:
            idx = 1
            total_items = len(self.interest_rate_structure)
            for range_key, rate in self.interest_rate_structure.items():
                level_label = f"Level {idx}"
                if idx == total_items:
                    level_label += " (Default/Late)"
                    
                if '-' in range_key:
                    start, end = range_key.split('-')
                    from_str = f"{start}"
                    to_str = f"{end}"
                    range_label = f"{start} to {end} {unit}"
                elif range_key.endswith('+'):
                    start = range_key.rstrip('+')
                    from_str = f"{start}"
                    to_str = "∞ (No Limit)"
                    range_label = f"Above {start} {unit}"
                else:
                    from_str = "0"
                    to_str = f"{range_key}"
                    range_label = f"{range_key} {unit}"
                    
                annual = Decimal(str(rate))
                monthly = (annual / Decimal('12')).quantize(Decimal('0.01'))
                per_hundred = monthly
                
                tiers.append({
                    'level': level_label,
                    'from': from_str,
                    'to': to_str,
                    'range': range_label,
                    'annual_rate': annual,
                    'monthly_rate': monthly,
                    'per_hundred': per_hundred
                })
                idx += 1
        elif self.early_period_months or self.early_period_interest_rate:
            m1 = self.early_period_months or 1
            r1_monthly = Decimal(str(self.early_period_interest_rate or 0))
            r1_annual = r1_monthly * Decimal('12')
            
            m2 = self.standard_period_months or 2
            r2_monthly = Decimal(str(self.gold_interest_rate or 0))
            r2_annual = r2_monthly * Decimal('12')
            
            r3_monthly = Decimal(str(self.late_period_interest_rate or self.gold_interest_rate or 0))
            r3_annual = r3_monthly * Decimal('12')
            
            tiers.append({
                'level': 'Level 1 (Early)',
                'from': '0',
                'to': f'{m1}',
                'range': f'0 to {m1} Months',
                'annual_rate': r1_annual.quantize(Decimal('0.01')),
                'monthly_rate': r1_monthly.quantize(Decimal('0.01')),
                'per_hundred': r1_monthly.quantize(Decimal('0.01'))
            })
            tiers.append({
                'level': 'Level 2 (Standard)',
                'from': f'{m1}',
                'to': f'{m1 + m2}',
                'range': f'{m1} to {m1 + m2} Months',
                'annual_rate': r2_annual.quantize(Decimal('0.01')),
                'monthly_rate': r2_monthly.quantize(Decimal('0.01')),
                'per_hundred': r2_monthly.quantize(Decimal('0.01'))
            })
            tiers.append({
                'level': 'Level 3 (Late)',
                'from': f'{m1 + m2}+',
                'to': '∞ (No Limit)',
                'range': f'Above {m1 + m2} Months',
                'annual_rate': r3_annual.quantize(Decimal('0.01')),
                'monthly_rate': r3_monthly.quantize(Decimal('0.01')),
                'per_hundred': r3_monthly.quantize(Decimal('0.01'))
            })
        else:
            annual = Decimal(str(self.interest_rate or 0))
            monthly = (annual / Decimal('12')).quantize(Decimal('0.01'))
            duration = self.loan_duration or (self.expiry_period * 30 if self.expiry_period else 365)
            tiers.append({
                'level': 'Level 1 (Standard)',
                'from': '0',
                'to': f'{duration}',
                'range': f'0 to {duration} {unit}',
                'annual_rate': annual.quantize(Decimal('0.01')),
                'monthly_rate': monthly,
                'per_hundred': monthly
            })
            
        return tiers

    def update_status(self):
        """
        Update the status of the scheme based on current date and start/end dates
        """
        today = timezone.now().date()
        
        if self.status == 'inactive':
            # Don't change inactive status automatically
            return
            
        if self.start_date > today:
            self.status = 'upcoming'
        elif self.end_date and self.end_date < today:
            self.status = 'expired'
        else:
            self.status = 'active'
        
        self.save(update_fields=['status'])


class SchemeAuditLog(models.Model):
    """
    Model to keep track of all changes made to schemes
    """
    scheme = models.ForeignKey(Scheme, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20)  # created, updated, deleted
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    changes = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.action} on {self.scheme.name} by {self.user.username}"
