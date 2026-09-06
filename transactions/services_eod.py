import logging
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum

from .models import Loan, Payment, InterestAccrualLog, EODBatchExecutionLog
from branches.models import Branch
from accounting.services import post_daily_accrual_journal

logger = logging.getLogger(__name__)


def compute_daily_loan_interest(loan, as_of_date=None):
    """
    Computes exact daily mathematical interest for a loan:
    Formula: (Principal Outstanding * Annual Rate) / (365 * 100)
    Handles dynamic scheme rate tiers and rebate discounts if applicable.
    """
    if as_of_date is None:
        as_of_date = timezone.now().date()

    principal = Decimal(str(loan.principal_amount or 0))
    if principal <= Decimal('0.00'):
        return Decimal('0.00'), Decimal('0.00')

    annual_rate = Decimal(str(loan.interest_rate or 12.00))

    # Scheme Tiered Rate / Rebate Check
    if loan.scheme:
        days_active = max(1, (as_of_date - loan.issue_date).days)
        try:
            # If scheme has dynamic rate tiers
            if hasattr(loan.scheme, 'get_interest_rate_for_days'):
                tier_rate = loan.scheme.get_interest_rate_for_days(days_active)
                if tier_rate:
                    annual_rate = Decimal(str(tier_rate))
        except Exception:
            pass

    # Exact daily interest = (Principal * Annual Rate) / (365 * 100)
    daily_accrual = (principal * annual_rate) / (Decimal('365') * Decimal('100'))
    daily_accrual = daily_accrual.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return daily_accrual, annual_rate


def classify_loan_irac(loan, as_of_date=None):
    """
    Classifies loan under RBI IRAC (Income Recognition & Asset Classification) Prudential Norms:
    - Standard Asset: 0 Overdue Days (0.25% provisioning)
    - SMA-0: 1 - 30 Overdue Days (0.25% provisioning)
    - SMA-1: 31 - 60 Overdue Days (0.25% provisioning)
    - SMA-2: 61 - 90 Overdue Days (0.25% provisioning)
    - NPA Substandard: 91 - 180 Overdue Days (10.00% secured provisioning)
    - NPA Doubtful: 181 - 365 Overdue Days (25.00% provisioning)
    - NPA Loss: > 365 Overdue Days (100.00% provisioning)
    """
    if as_of_date is None:
        as_of_date = timezone.now().date()

    # Determine reference overdue baseline (grace period end or due date)
    ref_date = loan.grace_period_end or loan.due_date
    if not ref_date or as_of_date <= ref_date:
        overdue_days = 0
    else:
        overdue_days = (as_of_date - ref_date).days

    if overdue_days <= 0:
        return 'STANDARD', 0, Decimal('0.25'), None
    elif overdue_days <= 30:
        return 'SMA_0', overdue_days, Decimal('0.25'), None
    elif overdue_days <= 60:
        return 'SMA_1', overdue_days, Decimal('0.25'), None
    elif overdue_days <= 90:
        return 'SMA_2', overdue_days, Decimal('0.25'), None
    elif overdue_days <= 180:
        npa_date = loan.npa_date or as_of_date
        return 'NPA_SUBSTANDARD', overdue_days, Decimal('10.00'), npa_date
    elif overdue_days <= 365:
        npa_date = loan.npa_date or as_of_date
        return 'NPA_DOUBTFUL', overdue_days, Decimal('25.00'), npa_date
    else:
        npa_date = loan.npa_date or as_of_date
        return 'NPA_LOSS', overdue_days, Decimal('100.00'), npa_date


def run_daily_eod_batch(date=None, branch=None, user=None, post_gl=True):
    """
    Executes automated End-of-Day (EOD) batch processing:
    1. Daily Mathematical Interest Accrual per loan.
    2. RBI IRAC Asset Classification & NPA Tagging.
    3. General Ledger Journal Entry (Dr Accrued Interest Receivable / Cr Interest Income).
    4. Audit Log in EODBatchExecutionLog.
    """
    if date is None:
        date = timezone.now().date()

    logs_list = []
    logs_list.append(f"Starting EOD Batch Processing for date {date.strftime('%d-%b-%Y')}")

    # Build loan queryset
    loans_qs = Loan.objects.filter(status__in=['active', 'approved'])
    if branch:
        loans_qs = loans_qs.filter(branch=branch)
        logs_list.append(f"Scope: Single Branch [{branch.name}]")
    else:
        logs_list.append("Scope: Enterprise-Wide (All Branches)")

    loans_qs = loans_qs.select_related('scheme', 'branch', 'customer')

    total_processed = 0
    total_daily_accrued = Decimal('0.00')
    standard_count = 0
    sma0_count = 0
    sma1_count = 0
    sma2_count = 0
    npa_count = 0

    branch_accruals = {}

    with transaction.atomic():
        for loan in loans_qs:
            total_processed += 1

            # 1. Compute Daily Accrual
            daily_accrual, annual_rate = compute_daily_loan_interest(loan, as_of_date=date)
            total_daily_accrued += daily_accrual

            # 2. RBI IRAC Classification
            irac_status, overdue_days, prov_pct, npa_date = classify_loan_irac(loan, as_of_date=date)

            if irac_status == 'STANDARD':
                standard_count += 1
            elif irac_status == 'SMA_0':
                sma0_count += 1
            elif irac_status == 'SMA_1':
                sma1_count += 1
            elif irac_status == 'SMA_2':
                sma2_count += 1
            else:
                npa_count += 1

            # Update Loan fields
            loan.irac_status = irac_status
            loan.overdue_days = overdue_days
            loan.provisioning_percentage = prov_pct
            if npa_date:
                loan.npa_date = npa_date

            # Calculate cumulative interest
            prior_accrual = InterestAccrualLog.objects.filter(
                loan=loan,
                date__lt=date
            ).aggregate(total=Sum('daily_interest_accrued'))['total'] or Decimal('0.00')

            new_cumulative = prior_accrual + daily_accrual
            loan.accrued_interest = new_cumulative
            loan.last_accrual_date = date
            loan.save(update_fields=[
                'irac_status', 'overdue_days', 'provisioning_percentage',
                'npa_date', 'accrued_interest', 'last_accrual_date'
            ])

            # 3. Create or Update InterestAccrualLog (Idempotent)
            InterestAccrualLog.objects.update_or_create(
                loan=loan,
                date=date,
                defaults={
                    'principal_outstanding': loan.principal_amount,
                    'annual_rate': annual_rate,
                    'daily_interest_accrued': daily_accrual,
                    'cumulative_interest': new_cumulative,
                    'irac_status': irac_status,
                    'is_posted_to_gl': post_gl
                }
            )

            # Aggregate for branch-level GL posting
            b_key = loan.branch
            branch_accruals[b_key] = branch_accruals.get(b_key, Decimal('0.00')) + daily_accrual

        # 4. General Ledger Postings
        primary_je = None
        if post_gl:
            for br, amt in branch_accruals.items():
                if amt > Decimal('0.00') and br:
                    je = post_daily_accrual_journal(branch=br, date=date, total_accrual=amt, user=user)
                    if je and not primary_je:
                        primary_je = je
                    logs_list.append(f"GL Journal #{je.entry_number if je else 'N/A'} posted for Branch {br.name}: ₹{amt:,.2f}")

        # 5. Create EOD Batch Execution Log
        logs_list.append(f"EOD Batch Completed: {total_processed} loans processed. Total Accrual: ₹{total_daily_accrued:,.2f}")
        logs_list.append(f"Asset Health: Standard: {standard_count}, SMA-0: {sma0_count}, SMA-1: {sma1_count}, SMA-2: {sma2_count}, NPA: {npa_count}")

        exec_log = EODBatchExecutionLog.objects.create(
            execution_date=date,
            branch=branch,
            status='COMPLETED',
            total_loans_processed=total_processed,
            total_daily_interest_accrued=total_daily_accrued,
            standard_count=standard_count,
            sma0_count=sma0_count,
            sma1_count=sma1_count,
            sma2_count=sma2_count,
            npa_count=npa_count,
            gl_journal_entry=primary_je,
            executed_by=user,
            completed_at=timezone.now(),
            logs="\n".join(logs_list)
        )

    # -----------------------------------------------------------------
    # Post-EOD: Send 3-day due-date reminder emails (non-blocking)
    # -----------------------------------------------------------------
    try:
        from datetime import timedelta
        from transactions.services_email import send_due_date_reminder_email
        reminder_target = date + timedelta(days=3)
        reminder_qs = Loan.objects.filter(
            status='active', due_date=reminder_target
        ).select_related('customer', 'branch')
        if branch:
            reminder_qs = reminder_qs.filter(branch=branch)
        reminder_sent = 0
        for _loan in reminder_qs:
            if getattr(_loan.customer, 'email', None):
                send_due_date_reminder_email(_loan)  # auto-computes days_left
                reminder_sent += 1
        if reminder_sent:
            logger.info("EOD: Sent %d due-date reminder email(s) for %s.", reminder_sent, date)
    except Exception as _e:
        logger.warning("EOD due-date reminder emails failed: %s", _e)

    return exec_log
