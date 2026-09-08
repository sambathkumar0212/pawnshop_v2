from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal


class AccountCategory(models.TextChoices):
    ASSET = 'ASSET', _('Asset')
    LIABILITY = 'LIABILITY', _('Liability')
    EQUITY = 'EQUITY', _('Equity / Capital')
    INCOME = 'INCOME', _('Income / Revenue')
    EXPENSE = 'EXPENSE', _('Expense')


class AccountHead(models.Model):
    """
    General Ledger Chart of Accounts (COA) Model.
    Supports hierarchical tree structure and branch-level or enterprise-wide scoping.
    """
    code = models.CharField(max_length=30, unique=True, db_index=True, help_text=_("Standard GL Account Code e.g. 1010, 2010, 4010"))
    name = models.CharField(max_length=150, help_text=_("Account Title e.g. Cash in Hand, Interest Income"))
    category = models.CharField(max_length=20, choices=AccountCategory.choices, db_index=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    branch = models.ForeignKey(
        'branches.Branch', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='account_heads',
        help_text=_("Leave blank for Organization-Wide Standard Chart of Accounts")
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']
        verbose_name = _("Account Head")
        verbose_name_plural = _("Chart of Accounts")

    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_category_display()})"

    @property
    def is_debit_nature(self):
        """Assets and Expenses increase with Debits (Debit nature)"""
        return self.category in [AccountCategory.ASSET, AccountCategory.EXPENSE]

    def get_balance(self, start_date=None, end_date=None, branch=None):
        """
        Calculates the net balance for this account head.
        For Asset & Expense: Balance = Total Debits - Total Credits
        For Liability, Equity & Income: Balance = Total Credits - Total Debits
        """
        items = self.journal_items.select_related('entry')
        if branch:
            items = items.filter(entry__branch=branch)
        if start_date:
            items = items.filter(entry__date__gte=start_date)
        if end_date:
            items = items.filter(entry__date__lte=end_date)

        aggregates = items.aggregate(
            total_debit=models.Sum('debit'),
            total_credit=models.Sum('credit')
        )
        total_debit = aggregates['total_debit'] or Decimal('0.00')
        total_credit = aggregates['total_credit'] or Decimal('0.00')

        if self.is_debit_nature:
            return total_debit - total_credit
        else:
            return total_credit - total_debit


class JournalEntryType(models.TextChoices):
    LOAN_DISBURSAL = 'LOAN_DISBURSAL', _('Loan Disbursal')
    LOAN_REPAYMENT = 'LOAN_REPAYMENT', _('Loan Repayment')
    BANK_TRANSFER = 'BANK_TRANSFER', _('Bank / CIT Remittance')
    EXPENSE = 'EXPENSE', _('Operating Expense')
    MANUAL_ADJUSTMENT = 'MANUAL_ADJUSTMENT', _('Manual Journal Voucher')
    CASH_DRAWER = 'CASH_DRAWER', _('Cash Drawer Adjustment')
    FEE_INCOME = 'FEE_INCOME', _('Fee / Charges Income')
    GOLD_PURCHASE = 'GOLD_PURCHASE', _('Gold Purchase')


class JournalEntry(models.Model):
    """
    Double-entry Journal Voucher / Transaction Header.
    Enforces Total Debits == Total Credits equilibrium.
    """
    entry_number = models.CharField(max_length=50, unique=True, db_index=True, help_text=_("e.g. JE-20260829-0001"))
    date = models.DateField(default=timezone.now, db_index=True)
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT, related_name='journal_entries')
    reference_type = models.CharField(max_length=30, choices=JournalEntryType.choices, default=JournalEntryType.MANUAL_ADJUSTMENT, db_index=True)
    reference_id = models.CharField(max_length=100, blank=True, db_index=True, help_text=_("Associated Loan/Payment ID or Receipt #"))
    narration = models.TextField(help_text=_("Description of transaction"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_journal_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = _("Journal Entry")
        verbose_name_plural = _("Journal Entries")

    def __str__(self):
        return f"{self.entry_number} ({self.date}) - {self.branch.name} [₹{self.total_debit:,.2f}]"

    @property
    def total_debit(self):
        return self.items.aggregate(total=models.Sum('debit'))['total'] or Decimal('0.00')

    @property
    def total_credit(self):
        return self.items.aggregate(total=models.Sum('credit'))['total'] or Decimal('0.00')

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit and self.total_debit > 0

    @property
    def variance(self):
        return self.total_debit - self.total_credit

    def clean(self):
        super().clean()
        if self.pk:
            if self.items.exists():
                if self.total_debit != self.total_credit:
                    raise ValidationError(_(f"Double-entry out of balance! Total Debits (₹{self.total_debit:,.2f}) must equal Total Credits (₹{self.total_credit:,.2f})."))


class JournalItem(models.Model):
    """
    Individual Debit or Credit line item within a Journal Entry.
    """
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='items')
    account = models.ForeignKey(AccountHead, on_delete=models.PROTECT, related_name='journal_items')
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    narration = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _("Journal Line Item")
        verbose_name_plural = _("Journal Line Items")

    def __str__(self):
        return f"{self.account.code} - {self.account.name} | Dr: ₹{self.debit:,.2f} | Cr: ₹{self.credit:,.2f}"

    def clean(self):
        super().clean()
        if self.debit < 0 or self.credit < 0:
            raise ValidationError(_("Debit and Credit amounts must be non-negative."))
        if self.debit > 0 and self.credit > 0:
            raise ValidationError(_("A single line item cannot have both Debit and Credit amounts."))
        if self.debit == 0 and self.credit == 0:
            raise ValidationError(_("Either Debit or Credit must be greater than zero."))
