from django.db import models
from django.utils.translation import gettext_lazy as _


class Zone(models.Model):
    """Macro Geographical Zone (e.g. South Zone, North Zone)"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    zonal_head = models.ForeignKey(
        'accounts.CustomUser', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_zones'
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('zone')
        verbose_name_plural = _('zones')

    def __str__(self):
        return f"{self.name} ({self.code or 'ZONE'})"


class RegionalOffice(models.Model):
    """Regional Administrative Office (e.g. Chennai Region, Salem Region)"""
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='regional_offices', null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    regional_manager = models.ForeignKey(
        'accounts.CustomUser', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_regional_offices'
    )
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('regional office')
        verbose_name_plural = _('regional offices')

    def __str__(self):
        return f"{self.name} ({self.code or 'RO'})"


class BranchCluster(models.Model):
    """Branch Cluster / Area (e.g. Salem Urban Cluster, Coimbatore Rural Cluster)"""
    region = models.ForeignKey(RegionalOffice, on_delete=models.CASCADE, related_name='clusters', null=True, blank=True)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True, null=True)
    area_manager = models.ForeignKey(
        'accounts.CustomUser', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_clusters'
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('branch cluster')
        verbose_name_plural = _('branch clusters')

    def __str__(self):
        return f"{self.name} ({self.code or 'CLUSTER'})"


class Branch(models.Model):
    """Model for pawn shop branches/locations"""
    name = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, 
                                    related_name='branches', null=True)
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='branches')
    regional_office = models.ForeignKey(RegionalOffice, on_delete=models.SET_NULL, null=True, blank=True, related_name='branches')
    cluster = models.ForeignKey(BranchCluster, on_delete=models.SET_NULL, null=True, blank=True, related_name='branches')
    region = models.ForeignKey('accounts.Region', on_delete=models.SET_NULL, 
                              null=True, blank=True, related_name='branches')
    manager = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, 
                               null=True, blank=True, related_name='managed_branches')
    is_active = models.BooleanField(default=True)
    opening_time = models.TimeField(default='09:00')
    closing_time = models.TimeField(default='18:00')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('branch')
        verbose_name_plural = _('branches')
        ordering = ['name']
        
    def __str__(self):
        return self.name
        
    @property
    def staff_count(self):
        # Fix the reference to staff members
        from accounts.models import CustomUser
        return CustomUser.objects.filter(branch=self).count()
        # Alternative if there's a related_name on the CustomUser model:
        # return self.staff_members.count()  # Assuming related_name is 'staff_members'

    @staff_count.setter
    def staff_count(self, value):
        # This is a computed property, so we ignore attempts to set it directly
        pass
        
    @property
    def active_loans(self):
        return self.loans.filter(status='active').count()
        
    @property
    def inventory_count(self):
        # Handle missing inventory model with a default value
        try:
            # Try to get the appropriate inventory model
            from inventory.models import Item  # Trying a different name
            return Item.objects.filter(branch=self).count()
        except (ImportError, AttributeError):
            try:
                # Try another common name
                from inventory.models import Inventory
                return Inventory.objects.filter(branch=self).count()
            except (ImportError, AttributeError):
                # Return 0 if we can't find the right model
                return 0


class BranchSettings(models.Model):
    """Settings specific to a branch"""
    branch = models.OneToOneField(Branch, on_delete=models.CASCADE, related_name='settings')
    max_loan_amount = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)
    default_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    loan_duration_days = models.IntegerField(default=30)
    grace_period_days = models.IntegerField(default=15)
    allow_online_payments = models.BooleanField(default=True)
    require_id_verification = models.BooleanField(default=True)
    enable_face_recognition = models.BooleanField(default=False)
    enable_email_notifications = models.BooleanField(default=True)
    enable_sms_notifications = models.BooleanField(default=False)
    auction_delay_days = models.IntegerField(default=7)
    bill_header_mobile_numbers = models.TextField(blank=True, null=True, help_text="Enter multiple mobile numbers (40+ characters). Separated by comma, semicolon, slash, or newline. These will be displayed in bill headers.")
    personal_mobile_number = models.CharField(max_length=15, blank=True, null=True, help_text="Personal mobile number of branch manager or staff (10-15 characters).")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('branch settings')
        verbose_name_plural = _('branch settings')
        
    def __str__(self):
        return f"{self.branch.name} Settings"


class CashTill(models.Model):
    """
    Branch Cash Counter & Till (Cash Scroll) for Daily Cash Management & EOD Reconciliation.
    """
    STATUS_CHOICES = [
        ('open', _('Open (Active)')),
        ('reconciled', _('Reconciled (Pending Manager Sign-off)')),
        ('closed', _('Closed (Verified by Manager)')),
        ('mismatched', _('Discrepancy / Mismatch')),
    ]

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='cash_tills')
    cashier = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='cash_tills')
    date = models.DateField()
    
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text=_("Opening cash in drawer at BOD"))
    cash_inwards = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text=_("Total cash receipts (repayments, fees, etc.)"))
    cash_outwards = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text=_("Total cash payments (disbursements, expenses, etc.)"))
    cash_to_bank = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text=_("Cash transferred to Bank/CIT during day"))
    
    closing_balance_system = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text=_("Computed closing balance"))
    closing_balance_physical = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text=_("Actual physical count of notes/coins at EOD"))
    
    denomination_breakdown = models.JSONField(default=dict, blank=True, help_text=_("Breakdown of notes (500, 200, 100, 50, 20, 10) and coins"))
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    discrepancy_reason = models.TextField(blank=True, null=True, help_text=_("Explanation if physical cash differs from system balance"))
    
    verified_by_manager = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_cash_tills')
    reconciled_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Cash Till')
        verbose_name_plural = _('Cash Tills')
        unique_together = ['branch', 'cashier', 'date']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.branch.name} Till - {self.date} ({self.cashier.get_full_name() or self.cashier.username})"

    @property
    def variance(self):
        """Variance between physical cash and computed system balance"""
        if self.closing_balance_physical is not None:
            return self.closing_balance_physical - self.closing_balance_system
        return 0.00

    def compute_denomination_total(self):
        """Calculate total amount from stored denomination dictionary"""
        if not self.denomination_breakdown or not isinstance(self.denomination_breakdown, dict):
            return 0.00
        
        rates = {
            '500': 500, '200': 200, '100': 100, '50': 50,
            '20': 20, '10': 10, '5': 5, '2': 2, '1': 1, 'coins': 1
        }
        total = 0.00
        for key, count in self.denomination_breakdown.items():
            try:
                cnt = int(count) if count else 0
                mult = rates.get(str(key).lower(), 0)
                total += cnt * mult
            except (ValueError, TypeError):
                continue
        return total

    def sync_live_transactions(self):
        """
        Synchronously compute live cash receipts and disbursements for this branch & date.
        """
        from decimal import Decimal
        from django.db.models import Sum
        from transactions.models import Payment, Loan, DisbursementTransaction

        # 1. Cash Inwards from Loan Repayments
        repayments_cash = Payment.objects.filter(
            loan__branch=self.branch,
            payment_date=self.date,
            payment_method__iexact='cash'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # 2. Cash Inwards from manual scroll entries (e.g. cash additions)
        manual_in = self.entries.filter(direction='IN').exclude(entry_type='OPENING').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        self.cash_inwards = Decimal(str(repayments_cash)) + Decimal(str(manual_in))

        # 3. Cash Outwards from Loan Disbursements (Cash mode)
        disbursements_cash = DisbursementTransaction.objects.filter(
            loan__branch=self.branch,
            disbursed_at__date=self.date,
            payment_mode='CASH'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Also fallback for loans created without DisbursementTransaction but with distribution_amount <= 19999
        legacy_cash_loans = Loan.objects.filter(
            branch=self.branch,
            issue_date=self.date,
            disbursement_detail__isnull=True,
            principal_amount__lt=Decimal('20000.00')
        ).aggregate(total=Sum('distribution_amount'))['total'] or Decimal('0.00')

        # 4. Cash Outwards from manual scroll entries (e.g. petty cash, expenses)
        manual_out = self.entries.filter(direction='OUT').exclude(entry_type='BANK_DEPOSIT').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        self.cash_outwards = Decimal(str(disbursements_cash)) + Decimal(str(legacy_cash_loans)) + Decimal(str(manual_out))

        # 5. Cash transferred to Bank
        bank_transfers = self.entries.filter(entry_type='BANK_DEPOSIT').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        self.cash_to_bank = Decimal(str(bank_transfers))

        # 6. Compute System Balance
        self.closing_balance_system = (
            Decimal(str(self.opening_balance)) +
            self.cash_inwards -
            self.cash_outwards -
            self.cash_to_bank
        )
        self.save(update_fields=['cash_inwards', 'cash_outwards', 'cash_to_bank', 'closing_balance_system'])
        return self.closing_balance_system


class CashScrollEntry(models.Model):
    """
    Granular Real-Time Cash Scroll Entry (Audit Ledger for Branch Till).
    """
    ENTRY_TYPE_CHOICES = [
        ('OPENING', _('Opening Balance')),
        ('LOAN_DISBURSAL', _('Loan Disbursal (Cash)')),
        ('LOAN_REPAYMENT', _('Loan Repayment (Cash)')),
        ('BANK_DEPOSIT', _('Cash Deposit to Bank / CIT')),
        ('PETTY_CASH', _('Petty Cash / Office Expense')),
        ('ADJUSTMENT', _('Cash Adjustment / Inflow')),
    ]
    DIRECTION_CHOICES = [
        ('IN', _('Cash In (Receipt)')),
        ('OUT', _('Cash Out (Payment)')),
    ]

    till = models.ForeignKey(CashTill, on_delete=models.CASCADE, related_name='entries')
    entry_type = models.CharField(max_length=30, choices=ENTRY_TYPE_CHOICES)
    direction = models.CharField(max_length=5, choices=DIRECTION_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference_id = models.CharField(max_length=100, blank=True, null=True, help_text=_("Loan No, Voucher No, Receipt No, etc."))
    description = models.TextField(help_text=_("Details / Narrative of the cash movement"))
    
    created_by = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='created_cash_entries')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Cash Scroll Entry')
        verbose_name_plural = _('Cash Scroll Entries')
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_direction_display()}] ₹{self.amount:,.2f} - {self.get_entry_type_display()} ({self.reference_id or 'N/A'})"

