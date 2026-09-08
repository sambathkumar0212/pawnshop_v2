from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from .models import AccountHead, AccountCategory, JournalEntry, JournalItem, JournalEntryType


def ensure_default_chart_of_accounts(branch=None):
    """
    Initializes and ensures standard Indian NBFC / Pawnshop Chart of Accounts exists.
    Can be called enterprise-wide (branch=None) or tailored for a specific branch.
    """
    standard_accounts = [
        # Assets (1000s)
        ('1010', 'Cash in Hand (Drawer & Counter Till)', AccountCategory.ASSET, 'Primary physical cash balance at branch drawer'),
        ('1020', 'Bank Current Account (Main Operational)', AccountCategory.ASSET, 'Branch main current account for transfers & RTGS/NEFT/IMPS'),
        ('1050', 'Gold Loan Portfolio Asset (Principal Outstanding)', AccountCategory.ASSET, 'Pawn loan principal receivables secured against pledged gold items'),
        ('1060', 'Interest Accrued Receivable (Asset)', AccountCategory.ASSET, 'Cumulative daily interest accrued on active gold loans prior to payment realization'),
        ('1070', 'Purchased Gold & Scrap Inventory Asset', AccountCategory.ASSET, 'Outright purchased gold ornaments and melted scrap bullion inventory asset'),
        
        # Liabilities (2000s)
        ('2010', 'Customer Advances & Excess Funds Payable', AccountCategory.LIABILITY, 'Unadjusted customer payments or advance interest funds'),
        ('2020', 'Statutory Dues & GST Payable', AccountCategory.LIABILITY, 'Output GST and statutory deductions payable to government'),

        # Equity / Capital (3000s)
        ('3010', 'Share Capital & Head Office Funds', AccountCategory.EQUITY, 'Capital infused and Head Office operational allocation'),
        ('3020', 'Retained Earnings / Operational Reserves', AccountCategory.EQUITY, 'Cumulative operating surplus and reserves'),

        # Income / Revenue (4000s)
        ('4010', 'Gold Loan Interest Income', AccountCategory.INCOME, 'Interest earnings collected on gold loans'),
        ('4020', 'Loan Processing & Appraisal Fee Income', AccountCategory.INCOME, 'Upfront processing fees and gold purity appraisal charges'),
        ('4030', 'Penal Interest & Notice Charges Income', AccountCategory.INCOME, 'Overdue penalty interest and auction notice recovery fees'),

        # Expenses (5000s)
        ('5010', 'Branch Premises Rent & Utilities', AccountCategory.EXPENSE, 'Monthly branch lease rental, electricity, and internet'),
        ('5020', 'Staff Salaries, Wages & Allowances', AccountCategory.EXPENSE, 'Branch staff remuneration and appraiser allowances'),
        ('5030', 'Gold Vault Custody & Insurance', AccountCategory.EXPENSE, 'Vault physical security maintenance, surveillance and bullion transit insurance'),
        ('5040', 'Printing, Stationery & Office Supplies', AccountCategory.EXPENSE, 'Pawn tickets, billing paper rolls, ledger registers and office consumables'),
        ('5050', 'Bank Service Charges & CIT Courier Fees', AccountCategory.EXPENSE, 'Banking transaction charges, CMS charges, and cash-in-transit courier fees'),
    ]

    created_accounts = {}
    for code, name, category, desc in standard_accounts:
        acc, created = AccountHead.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'category': category,
                'description': desc,
                'branch': branch,
                'is_active': True
            }
        )
        created_accounts[code] = acc

    return created_accounts


def get_account_head(code, branch=None):
    """Fetches AccountHead by code, falling back to organization-wide head if branch-specific is not present."""
    acc = AccountHead.objects.filter(code=code, branch=branch).first()
    if not acc:
        acc = AccountHead.objects.filter(code=code, branch__isnull=True).first()
    if not acc:
        ensure_default_chart_of_accounts(branch)
        acc = AccountHead.objects.filter(code=code).first()
    return acc


def generate_entry_number(prefix, date=None):
    """Generates unique Journal Entry reference number"""
    d = date or timezone.now().date()
    datestr = d.strftime('%Y%m%d')
    count = JournalEntry.objects.filter(date=d).count() + 1
    return f"{prefix}-{datestr}-{count:04d}"


@transaction.atomic
def post_loan_disbursal_journal(loan, payment_mode='CASH', user=None, bank_ref=None):
    """
    Automated Double-Entry Journal for Gold Loan Disbursal.
    Accounting Rule:
      Debit:  Gold Loan Portfolio Asset (Principal Amount)
      Credit: Loan Processing Fee Income (Processing Fee, if any)
      Credit: Cash in Hand / Bank Account (Disbursed Distribution Amount)
    Equilibrium: Total Debits == Total Credits
    """
    # Ensure COA exists
    ensure_default_chart_of_accounts(loan.branch)
    
    asset_acc = get_account_head('1050', loan.branch)
    fee_acc = get_account_head('4020', loan.branch)
    credit_acc = get_account_head('1010' if str(payment_mode).upper() == 'CASH' else '1020', loan.branch)

    # Check if already posted
    existing = JournalEntry.objects.filter(reference_type=JournalEntryType.LOAN_DISBURSAL, reference_id=loan.loan_number).first()
    if existing:
        return existing

    principal = Decimal(str(loan.principal_amount))
    fee = Decimal(str(getattr(loan, 'processing_fee', 0) or 0))
    distribution = Decimal(str(getattr(loan, 'distribution_amount', principal - fee)))

    # Fallback to ensure distribution + fee = principal
    if (distribution + fee) != principal:
        distribution = principal - fee

    entry_num = generate_entry_number(f"JE-DISB-{loan.branch.id if loan.branch else '1'}", loan.issue_date or timezone.now().date())
    mode_str = "Cash" if str(payment_mode).upper() == 'CASH' else f"Bank Transfer ({bank_ref or 'NEFT/RTGS'})"
    
    entry = JournalEntry.objects.create(
        entry_number=entry_num,
        date=loan.issue_date or timezone.now().date(),
        branch=loan.branch,
        reference_type=JournalEntryType.LOAN_DISBURSAL,
        reference_id=loan.loan_number,
        narration=f"Disbursement of Gold Loan #{loan.loan_number} to {loan.customer.full_name} via {mode_str}. Principal: ₹{principal:,.2f}, Processing Fee: ₹{fee:,.2f}, Net Disbursed: ₹{distribution:,.2f}.",
        created_by=user
    )

    # 1. Debit Gold Loan Principal Asset
    JournalItem.objects.create(
        entry=entry,
        account=asset_acc,
        debit=principal,
        credit=Decimal('0.00'),
        narration=f"Principal asset recognized for Loan #{loan.loan_number}"
    )

    # 2. Credit Processing Fee Income (if fee > 0)
    if fee > 0:
        JournalItem.objects.create(
            entry=entry,
            account=fee_acc,
            debit=Decimal('0.00'),
            credit=fee,
            narration=f"Upfront processing fee on Loan #{loan.loan_number}"
        )

    # 3. Credit Cash in Hand / Bank Account for net payout
    JournalItem.objects.create(
        entry=entry,
        account=credit_acc,
        debit=Decimal('0.00'),
        credit=distribution,
        narration=f"Disbursement payout via {mode_str} for Loan #{loan.loan_number}"
    )

    return entry


@transaction.atomic
def post_loan_repayment_journal(payment, user=None):
    """
    Automated Double-Entry Journal for Gold Loan Repayments.
    Accounting Rule:
      Debit:  Cash in Hand / Bank Account (Payment Amount)
      Credit: Gold Loan Interest Income (Interest component)
      Credit: Gold Loan Portfolio Asset (Principal component)
    Equilibrium: Total Debits == Total Credits
    """
    loan = payment.loan
    branch = loan.branch
    ensure_default_chart_of_accounts(branch)

    debit_acc = get_account_head('1010' if str(payment.payment_method).lower() == 'cash' else '1020', branch)
    interest_acc = get_account_head('4010', branch)
    asset_acc = get_account_head('1050', branch)

    # Check if already posted
    existing = JournalEntry.objects.filter(reference_type=JournalEntryType.LOAN_REPAYMENT, reference_id=str(payment.pk)).first()
    if existing:
        return existing

    amount = Decimal(str(payment.amount))
    
    # Calculate interest vs principal reduction
    interest_paid = Decimal('0.00')
    if hasattr(payment, 'interest_amount') and payment.interest_amount:
        interest_paid = Decimal(str(payment.interest_amount))
    elif hasattr(payment, 'loan') and payment.loan:
        # If not broken down on payment model, check outstanding interest
        accrued = getattr(payment.loan, 'interest_accrued', None)
        if accrued and accrued > 0:
            interest_paid = min(amount, Decimal(str(accrued)))
    
    # Bound interest_paid between 0 and payment amount
    interest_paid = max(Decimal('0.00'), min(interest_paid, amount))
    principal_paid = amount - interest_paid

    entry_num = generate_entry_number(f"JE-REPAY-{branch.id if branch else '1'}", payment.payment_date or timezone.now().date())
    mode_str = payment.payment_method.capitalize() if payment.payment_method else "Cash"

    entry = JournalEntry.objects.create(
        entry_number=entry_num,
        date=payment.payment_date or timezone.now().date(),
        branch=branch,
        reference_type=JournalEntryType.LOAN_REPAYMENT,
        reference_id=str(payment.pk),
        narration=f"Repayment receipt of ₹{amount:,.2f} on Loan #{loan.loan_number} ({loan.customer.full_name}) via {mode_str}. (Interest: ₹{interest_paid:,.2f}, Principal: ₹{principal_paid:,.2f}).",
        created_by=user or getattr(payment, 'received_by', None)
    )

    # 1. Debit Cash in Hand / Bank
    JournalItem.objects.create(
        entry=entry,
        account=debit_acc,
        debit=amount,
        credit=Decimal('0.00'),
        narration=f"Repayment cash received for Loan #{loan.loan_number}"
    )

    # 2. Credit Interest Income (if interest > 0)
    if interest_paid > 0:
        JournalItem.objects.create(
            entry=entry,
            account=interest_acc,
            debit=Decimal('0.00'),
            credit=interest_paid,
            narration=f"Interest income earned on Loan #{loan.loan_number}"
        )

    # 3. Credit Loan Portfolio Asset (Principal reduction)
    if principal_paid > 0:
        JournalItem.objects.create(
            entry=entry,
            account=asset_acc,
            debit=Decimal('0.00'),
            credit=principal_paid,
            narration=f"Principal reduction on Loan #{loan.loan_number}"
        )

    return entry


@transaction.atomic
def post_bank_deposit_journal(scroll_entry, user=None):
    """
    Automated Journal for Till Cash remitted to Bank / CIT.
    Accounting Rule:
      Debit:  Bank Current Account (1020)
      Credit: Cash in Hand (1010)
    """
    branch = scroll_entry.till.branch
    ensure_default_chart_of_accounts(branch)

    bank_acc = get_account_head('1020', branch)
    cash_acc = get_account_head('1010', branch)

    existing = JournalEntry.objects.filter(reference_type=JournalEntryType.BANK_TRANSFER, reference_id=str(scroll_entry.pk)).first()
    if existing:
        return existing

    amount = Decimal(str(scroll_entry.amount))
    entry_num = generate_entry_number(f"JE-BANKDEP-{branch.id}", scroll_entry.till.date)

    entry = JournalEntry.objects.create(
        entry_number=entry_num,
        date=scroll_entry.till.date,
        branch=branch,
        reference_type=JournalEntryType.BANK_TRANSFER,
        reference_id=str(scroll_entry.pk),
        narration=f"Cash remitted to Bank / CIT from {branch.name} cash drawer. Ref/Challan: {scroll_entry.reference_id or 'N/A'}. {scroll_entry.description}",
        created_by=user or scroll_entry.created_by
    )

    # Debit Bank
    JournalItem.objects.create(
        entry=entry,
        account=bank_acc,
        debit=amount,
        credit=Decimal('0.00'),
        narration=f"Deposit into current bank account"
    )

    # Credit Cash
    JournalItem.objects.create(
        entry=entry,
        account=cash_acc,
        debit=Decimal('0.00'),
        credit=amount,
        narration=f"Cash drawer deduction for bank deposit"
    )

    return entry


@transaction.atomic
def post_manual_expense_journal(branch, expense_head, amount, payment_mode='CASH', narration='', user=None):
    """
    Automated Journal for Operational Expenses.
    Accounting Rule:
      Debit:  Expense Account Head (5000s)
      Credit: Cash in Hand / Bank (1010 / 1020)
    """
    ensure_default_chart_of_accounts(branch)
    credit_acc = get_account_head('1010' if str(payment_mode).upper() == 'CASH' else '1020', branch)

    amount_dec = Decimal(str(amount))
    entry_num = generate_entry_number(f"JE-EXP-{branch.id}", timezone.now().date())

    entry = JournalEntry.objects.create(
        entry_number=entry_num,
        date=timezone.now().date(),
        branch=branch,
        reference_type=JournalEntryType.EXPENSE,
        narration=narration or f"Operational expense incurred at {branch.name} for {expense_head.name}.",
        created_by=user
    )

    # Debit Expense Head
    JournalItem.objects.create(
        entry=entry,
        account=expense_head,
        debit=amount_dec,
        credit=Decimal('0.00'),
        narration=narration
    )

    # Credit Cash / Bank
    JournalItem.objects.create(
        entry=entry,
        account=credit_acc,
        debit=Decimal('0.00'),
        credit=amount_dec,
        narration=f"Paid via {payment_mode}"
    )

    return entry


@transaction.atomic
def post_daily_accrual_journal(branch, date, total_accrual, user=None):
    """
    Automated EOD Daily Interest Accrual Posting:
      Debit:  1060 Interest Accrued Receivable (Asset)
      Credit: 4010 Gold Loan Interest Income (Income)
    """
    if not total_accrual or Decimal(str(total_accrual)) <= Decimal('0.00'):
        return None

    ensure_default_chart_of_accounts(branch)
    accrued_asset_acc = get_account_head('1060', branch)
    interest_income_acc = get_account_head('4010', branch)

    accrual_dec = Decimal(str(total_accrual)).quantize(Decimal('0.01'))
    ref_id = f"EOD-ACCR-{branch.id if branch else 'ALL'}-{date.strftime('%Y%m%d')}"

    # Check if entry already exists for idempotency
    existing = JournalEntry.objects.filter(
        reference_type=JournalEntryType.FEE_INCOME,
        reference_id=ref_id,
        branch=branch
    ).first()
    if existing:
        return existing

    entry_num = generate_entry_number(f"JE-ACCR-{branch.id if branch else 'HQ'}", date)
    branch_name = branch.name if branch else "All Branches"

    entry = JournalEntry.objects.create(
        entry_number=entry_num,
        date=date,
        branch=branch,
        reference_type=JournalEntryType.FEE_INCOME,
        reference_id=ref_id,
        narration=f"EOD Daily Interest Accrual for {date.strftime('%d-%b-%Y')} ({branch_name}).",
        created_by=user
    )

    # Debit 1060
    JournalItem.objects.create(
        entry=entry,
        account=accrued_asset_acc,
        debit=accrual_dec,
        credit=Decimal('0.00'),
        narration=f"Daily interest accrued on active gold loan portfolio"
    )

    # Credit 4010
    JournalItem.objects.create(
        entry=entry,
        account=interest_income_acc,
        debit=Decimal('0.00'),
        credit=accrual_dec,
        narration=f"Daily interest revenue recognized for {date.strftime('%d-%b-%Y')}"
    )

    return entry


@transaction.atomic
def post_gold_purchase_journal(gold_purchase, user=None):
    """
    Creates double-entry journal voucher for an outright gold purchase from customer.
    Debit 1070: Purchased Gold & Scrap Inventory Asset
    Credit 1010/1020: Cash in Hand or Bank Account
    """
    branch = getattr(gold_purchase, 'branch', None)
    ensure_default_chart_of_accounts(branch)
    gold_asset_acc = get_account_head('1070', branch)
    
    pay_mode = (gold_purchase.payment_method or 'cash').lower()
    if pay_mode in ['bank_transfer', 'cheque', 'upi']:
        payment_acc = get_account_head('1020', branch)
        cr_desc = f"Bank payment for gold purchase #{gold_purchase.purchase_number}"
    else:
        payment_acc = get_account_head('1010', branch)
        cr_desc = f"Cash paid at counter for gold purchase #{gold_purchase.purchase_number}"

    amount = Decimal(str(gold_purchase.net_payable_amount or '0.00')).quantize(Decimal('0.01'))
    if amount <= Decimal('0.00'):
        return None

    ref_id = f"BUY-{gold_purchase.id}"
    ref_type = getattr(JournalEntryType, 'GOLD_PURCHASE', 'MANUAL_ADJUSTMENT')
    existing = JournalEntry.objects.filter(
        reference_type=ref_type,
        reference_id=ref_id,
        branch=branch
    ).first()
    if existing:
        return existing

    entry_num = generate_entry_number(f"JE-BUY-{branch.id if branch else 'HQ'}", gold_purchase.purchase_date)
    customer_name = gold_purchase.customer.full_name if hasattr(gold_purchase.customer, 'full_name') else str(gold_purchase.customer)
    
    entry = JournalEntry.objects.create(
        entry_number=entry_num,
        date=gold_purchase.purchase_date,
        branch=branch,
        reference_type=ref_type,
        reference_id=ref_id,
        narration=f"Gold Purchase #{gold_purchase.purchase_number} from {customer_name} - {gold_purchase.total_net_weight}g net wt.",
        created_by=user or gold_purchase.purchased_by
    )

    # Debit 1070 (Inventory Asset)
    JournalItem.objects.create(
        entry=entry,
        account=gold_asset_acc,
        debit=amount,
        credit=Decimal('0.00'),
        narration=f"Purchased gold inventory asset ({gold_purchase.total_net_weight}g net wt)"
    )

    # Credit 1010/1020 (Cash / Bank)
    JournalItem.objects.create(
        entry=entry,
        account=payment_acc,
        debit=Decimal('0.00'),
        credit=amount,
        narration=cr_desc
    )

    return entry

