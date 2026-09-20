"""
24/7 Autopilot Automation Service & Background Engine for Pawnshop Management.
Implements:
  - Pillar 2: Automated WhatsApp Collections & Delinquency Dispatch
  - Pillar 3: Automated Gold Price & LTV Risk Surveillance
  - Pillar 4: Automated Customer Retention & Re-Pledge Marketing
  - Pillar 5: Automated Executive Daily Digest to Business Owner
  (Pillar 1 Automated EOD is excluded per user configuration)
"""

import logging
import threading
import time
from datetime import datetime, time as dtime
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Q, Count
from django.conf import settings

logger = logging.getLogger(__name__)

# Global singleton background scheduler state
_AUTOPILOT_THREAD = None
_AUTOPILOT_STOP_EVENT = threading.Event()
_LAST_DISPATCH_RECORD = {
    'pillar_2_date': None,
    'pillar_3_date': None,
    'pillar_4_date': None,
    'pillar_4_wishes_date': None,
    'pillar_5_date': None,
}


def get_or_create_autopilot_config():
    """Returns singleton AutopilotConfig instance."""
    from transactions.models import AutopilotConfig
    return AutopilotConfig.get_solo()


def _parse_time(val, default_time):
    """Safely converts string or time object into datetime.time."""
    if isinstance(val, dtime):
        return val
    if isinstance(val, str) and val.strip():
        try:
            parts = val.strip().split(':')
            return dtime(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
        except Exception:
            pass
    return default_time


def is_within_safe_window(config, current_time=None) -> bool:
    """Checks if current time falls within TRAI safe communication window."""
    if not current_time:
        current_time = timezone.localtime().time()
    start = _parse_time(config.safe_window_start, dtime(9, 0))
    end = _parse_time(config.safe_window_end, dtime(19, 30))
    return start <= current_time <= end


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 2: Automated WhatsApp Collections & Delinquency Dispatch
# ═══════════════════════════════════════════════════════════════════════════════

def run_pillar_2_whatsapp_collections(config=None, dry_run=False, forced=False) -> dict:
    """
    Executes automated collections scan & WhatsApp dispatches:
      1. Due-date reminders (e.g. 7, 3, 1 days before due)
      2. Monthly interest payment reminders for tiered schemes
      3. Regulatory IRAC Delinquency Warnings (SMA-0, SMA-1, SMA-2)
      4. Overdue Demand / Auction notices for NPA 90+ days
    """
    if not config:
        config = get_or_create_autopilot_config()

    if not config.is_enabled and not forced:
        return {'status': 'skipped', 'reason': 'Autopilot is disabled'}

    now = timezone.localtime()
    if not is_within_safe_window(config, now.time()) and not forced:
        logger.info("[Autopilot Pillar 2] Current time %s is outside safe window. Skipped.", now.time())
        return {'status': 'skipped', 'reason': 'Outside TRAI safe hours (09:00 - 19:30)'}

    from transactions.models import Loan, LoanWhatsAppLog, AutopilotLog
    from transactions.services_whatsapp import normalize_phone_number
    from transactions.services_whatsapp_automator import send_batch_loans_whatsapp_automated, is_whatsapp_paired

    today = now.date()
    target_loans = []
    reasons = {}

    # Parse reminder days from config (e.g. "7,3,1")
    reminder_days = []
    for d_str in (config.due_reminder_days or '7,3,1').split(','):
        try:
            reminder_days.append(int(d_str.strip()))
        except ValueError:
            pass

    cooldown_cutoff = now - timezone.timedelta(days=config.min_days_between_reminders or 5)

    active_loans = Loan.objects.filter(status__in=['active', 'approved']).select_related('customer', 'branch', 'scheme')

    for loan in active_loans:
        cust = loan.customer
        raw_phone = getattr(cust, 'phone', '') or ''
        norm_phone = normalize_phone_number(raw_phone)
        if not norm_phone:
            continue

        # Check anti-spam cooldown
        recent_log = loan.whatsapp_logs.filter(created_at__gte=cooldown_cutoff, status='sent').exists()
        if recent_log and not forced:
            continue

        ref_due = loan.due_date
        if not ref_due:
            continue

        days_to_due = (ref_due - today).days

        # Rule A: Due-date reminders (7, 3, 1 days)
        if config.enable_due_date_reminders and days_to_due in reminder_days:
            target_loans.append(loan)
            reasons[loan.id] = f"due_in_{days_to_due}_days"
            continue

        # Rule B: Tiered loans monthly interest reminder
        is_tiered = bool(loan.scheme and (getattr(loan.scheme, 'enable_tiered_rates', False) or getattr(loan.scheme, 'period1_days', None) or (getattr(loan.scheme, 'interest_rate_structure', None) and len(loan.scheme.interest_rate_structure) > 0)))
        if config.enable_monthly_interest_reminders and is_tiered:
            if days_to_due > 30 and (today.day == ref_due.day or (ref_due.day > 28 and today.day == 28)):
                target_loans.append(loan)
                reasons[loan.id] = "monthly_interest_due"
                continue

        # Rule C: Delinquency IRAC & NPA Notices
        if days_to_due < 0:
            overdue_days = abs(days_to_due)
            if config.enable_expiry_auction_notices and overdue_days >= 90:
                target_loans.append(loan)
                reasons[loan.id] = "demand_auction_notice"
            elif config.enable_irac_delinquency_alerts and overdue_days >= 1:
                target_loans.append(loan)
                reasons[loan.id] = f"overdue_{overdue_days}_days_irac"

    target_count = len(target_loans)
    if dry_run or not target_loans:
        summary_msg = f"Identified {target_count} borrower(s) eligible for automated WhatsApp collections."
        if not dry_run:
            AutopilotLog.objects.create(
                pillar='pillar_2',
                action_name='Automated WhatsApp Collections Scan',
                target_count=target_count,
                success_count=0,
                failed_count=0,
                summary=summary_msg,
                status='success'
            )
        return {'status': 'success', 'target_count': target_count, 'loans': [l.loan_number for l in target_loans], 'message': summary_msg}

    # Execute batch dispatch
    channel = config.dispatch_channel or 'headless_automated'
    success_count = 0
    failed_count = 0
    error_summary = []

    if channel == 'headless_automated':
        paired = is_whatsapp_paired()
        if not paired:
            msg = "WhatsApp session is not paired. Automated headless dispatch skipped."
            AutopilotLog.objects.create(
                pillar='pillar_2',
                action_name='Automated WhatsApp Collections Dispatch',
                target_count=target_count,
                success_count=0,
                failed_count=target_count,
                summary=msg,
                error_details="Unpaired WhatsApp Session",
                status='failed'
            )
            return {'status': 'failed', 'target_count': target_count, 'error': msg}

        res = send_batch_loans_whatsapp_automated(
            loans=target_loans,
            notification_type='auto',
            user=None,
            lang='ta',
            delay_between_seconds=3,
            headless=True
        )
        success_count = res.get('sent', 0)
        failed_count = res.get('failed', 0)
        if res.get('error'):
            error_summary.append(str(res['error']))

    else:
        # PyWhatKit Mode
        from transactions.services_whatsapp import build_smart_loan_whatsapp_message, send_pywhatkit_async
        for l in target_loans:
            norm_p = normalize_phone_number(getattr(l.customer, 'phone', ''))
            msg = build_smart_loan_whatsapp_message(loan=l, notification_type=reasons.get(l.id, 'auto'), lang='ta')
            if norm_p:
                send_pywhatkit_async(norm_p, msg)
                LoanWhatsAppLog.objects.create(
                    loan=l,
                    customer=l.customer,
                    recipient_phone=norm_p,
                    notification_type='autopilot_collection',
                    status='sent',
                    message_content=msg,
                    channel='pywhatkit',
                    sent_by=None
                )
                success_count += 1
            else:
                failed_count += 1

    status_str = 'success' if failed_count == 0 else ('partial' if success_count > 0 else 'failed')
    summary_text = f"Pillar 2 Autopilot: Dispatched {success_count} notices ({failed_count} failed) across {target_count} queued loans."

    AutopilotLog.objects.create(
        pillar='pillar_2',
        action_name='Automated WhatsApp Collections Dispatch',
        target_count=target_count,
        success_count=success_count,
        failed_count=failed_count,
        summary=summary_text,
        error_details="; ".join(error_summary),
        status=status_str
    )

    return {
        'status': status_str,
        'target_count': target_count,
        'sent': success_count,
        'failed': failed_count,
        'summary': summary_text
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 3: Automated Gold Price & LTV Risk Surveillance
# ═══════════════════════════════════════════════════════════════════════════════

def run_pillar_3_ltv_surveillance(config=None, dry_run=False, forced=False) -> dict:
    """
    Evaluates in-vault collateral valuation vs current outstanding principal & accrued interest.
    Flags high-risk loans (LTV > 75% warning or > 85% critical margin call).
    """
    if not config:
        config = get_or_create_autopilot_config()

    if not config.is_enabled and not forced:
        return {'status': 'skipped', 'reason': 'Autopilot is disabled'}

    if not config.enable_ltv_surveillance and not forced:
        return {'status': 'skipped', 'reason': 'LTV Risk Surveillance is disabled'}

    from transactions.models import Loan, AutopilotLog
    from transactions.services_partial_release import get_loan_current_interest_due

    warn_threshold = config.ltv_warning_threshold or Decimal('75.00')
    crit_threshold = config.ltv_critical_threshold or Decimal('85.00')

    active_loans = Loan.objects.filter(status__in=['active', 'approved']).prefetch_related('loanitem_set')

    total_scanned = 0
    warning_loans = []
    critical_loans = []

    for loan in active_loans:
        total_scanned += 1
        active_items = [it for it in loan.loanitem_set.all() if it.status != 'released']
        collateral_val = sum(it.item_valuation for it in active_items)

        if collateral_val <= Decimal('0.00'):
            continue

        try:
            today_interest = get_loan_current_interest_due(loan)
        except Exception:
            today_interest = Decimal('0.00')

        total_due = loan.principal_amount + today_interest
        ltv = ((total_due / collateral_val) * Decimal('100')).quantize(Decimal('0.01'))

        # Shortfall amount needed to restore LTV back to safe 75%
        safe_collateral_cap = collateral_val * (warn_threshold / Decimal('100'))
        shortfall = max(Decimal('0.00'), total_due - safe_collateral_cap).quantize(Decimal('0.01'))

        cust_obj = loan.customer
        cust_name = getattr(cust_obj, 'first_name', '') or str(cust_obj)
        cust_phone = getattr(cust_obj, 'phone', '') or ''
        branch_name = loan.branch.name if loan.branch else 'First Money Gold'

        margin_msg = (
            f"⚠️ *தங்கக்கடன் LTV விழிப்புணர்வு அறிவிப்பு (Margin Call)* ⚠️\n\n"
            f"அன்புள்ள *{cust_name}* அவர்களுக்கு,\n"
            f"தங்களின் கடன் எண்: *{loan.loan_number}*\n"
            f"மொத்த நிலுவைத் தொகை: *₹{total_due:,.2f}*\n"
            f"தங்க நகையின் மதிப்பீடு: *₹{collateral_val:,.2f}*\n"
            f"தற்போதைய LTV விகிதம்: *{ltv}%* (அபாய வரம்பு >{crit_threshold}%)\n\n"
            f"தங்களின் தங்கக் கணக்கை பாதுகாப்பாக வைத்திருக்க, உடனடியாக பகுதி அசல் தொகை *₹{shortfall:,.2f}* செலுத்துமாறு அல்லது கூடுதல் தங்கம் இணைக்குமாறு கேட்டுக்கொள்கிறோம்.\n\n"
            f"கிளை: *{branch_name}* | First Money Gold."
        )

        loan_data = {
            'loan_id': loan.id,
            'loan_number': loan.loan_number,
            'customer_name': cust_name,
            'customer_phone': cust_phone,
            'ltv': float(ltv),
            'total_due': float(total_due),
            'collateral_val': float(collateral_val),
            'shortfall': float(shortfall),
            'branch': branch_name,
            'status': 'critical' if ltv >= crit_threshold else 'warning',
            'margin_msg': margin_msg,
        }

        if ltv >= crit_threshold:
            critical_loans.append(loan_data)
        elif ltv >= warn_threshold:
            warning_loans.append(loan_data)

    summary_text = (
        f"LTV Risk Scan Completed: Scanned {total_scanned} loans. "
        f"Critical Breach (>{crit_threshold}%): {len(critical_loans)} | "
        f"Warning (>{warn_threshold}%): {len(warning_loans)}."
    )

    if not dry_run:
        AutopilotLog.objects.create(
            pillar='pillar_3',
            action_name='Automated LTV Risk Surveillance Scan',
            target_count=total_scanned,
            success_count=total_scanned - len(critical_loans),
            failed_count=len(critical_loans),
            summary=summary_text,
            error_details=f"Critical Accounts: {', '.join([c['loan_number'] for c in critical_loans])}" if critical_loans else '',
            status='partial' if critical_loans else 'success'
        )

    return {
        'status': 'success',
        'scanned': total_scanned,
        'critical_count': len(critical_loans),
        'warning_count': len(warning_loans),
        'safe_count': max(0, total_scanned - len(critical_loans) - len(warning_loans)),
        'warn_threshold': float(warn_threshold),
        'crit_threshold': float(crit_threshold),
        'critical_loans': critical_loans,
        'warning_loans': warning_loans,
        'summary': summary_text
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 4: Automated Customer Retention & Marketing
# ═══════════════════════════════════════════════════════════════════════════════

def run_pillar_4_retention_marketing(
    config=None,
    dry_run=False,
    forced=False,
    user=None,
    custom_template: str = None,
    selected_loan_ids: list = None
) -> dict:
    """
    Identifies high-value customers with redeemed/closed loans >= 30 days ago
    who do not have a current active loan and sends preferential re-engagement offers.
    Supports customizable promo message templates and selective customer list dispatch.
    """
    if not config:
        config = get_or_create_autopilot_config()

    if not config.is_enabled and not forced:
        return {'status': 'skipped', 'reason': 'Autopilot is disabled'}

    if not getattr(config, 'enable_repledge_retention', True) and not forced:
        return {'status': 'skipped', 'reason': 'Customer retention promos are disabled in configuration'}

    now = timezone.localtime()
    if not is_within_safe_window(config, now.time()) and not forced:
        return {'status': 'skipped', 'reason': 'Outside TRAI safe communication hours (09:00 AM - 07:30 PM)'}

    from transactions.models import Loan, AutopilotLog, MarketingCampaignLog
    from transactions.services_whatsapp import normalize_phone_number
    from transactions.services_whatsapp_automator import send_batch_retention_promos_automated, is_whatsapp_paired

    cooldown_days = config.repledge_cooldown_days or 30
    cutoff_date = now.date() - timezone.timedelta(days=cooldown_days)

    # Customers whose latest loan is closed / redeemed and closed before cutoff_date
    closed_loans = Loan.objects.filter(status='closed', updated_at__date__lte=cutoff_date).select_related('customer', 'branch').order_by('-updated_at')

    candidates = []
    seen_customers = set()

    for l in closed_loans:
        cust = l.customer
        if not cust or cust.id in seen_customers:
            continue

        # Check if customer currently has any active loan
        has_active = Loan.objects.filter(customer=cust, status__in=['active', 'approved']).exists()
        if has_active:
            continue

        raw_phone = getattr(cust, 'phone', '') or ''
        norm_phone = normalize_phone_number(raw_phone)
        if not norm_phone:
            continue

        # Check if already contacted for marketing in last 30 days
        already_contacted = MarketingCampaignLog.objects.filter(
            recipient_phone__in=[raw_phone, norm_phone],
            created_at__gte=now - timezone.timedelta(days=30)
        ).exists()

        if not already_contacted or forced:
            cust_name = getattr(cust, 'first_name', '') or str(cust)
            branch_name = l.branch.name if l.branch else 'First Money Gold'

            if custom_template and custom_template.strip():
                promo_text = (
                    custom_template.replace('{customer_name}', cust_name)
                    .replace('{name}', cust_name)
                    .replace('{branch_name}', branch_name)
                    .replace('{branch}', branch_name)
                    .replace('{loan_number}', l.loan_number)
                )
            else:
                promo_text = (
                    f"✨ *சிறப்பு தங்கக்கடன் சலுகை - {branch_name}* ✨\n\n"
                    f"அன்புள்ள *{cust_name}* அவர்களுக்கு,\n"
                    f"தாங்கள் எங்களின் நம்பகமான வாடிக்கையாளர்! தங்களின் அவசர பணத் தேவைகளுக்கு உடனடி தங்கக்கடன் மிகக் குறைந்த வட்டியில் (0.99% முதல்) உடனே பெறலாம்.\n\n"
                    f"💎 அதிகபட்ச கடன் தொகை\n"
                    f"⚡ 5 நிமிடங்களில் உடனடி பட்டுவாடா\n"
                    f"🔒 அதிநவீன பாதுகாப்பு பெட்டகம்\n\n"
                    f"இன்றே எங்களின் கிளைக்கு வருகை தரவும்: *{branch_name}*.\n"
                    f"நன்றி! First Money Gold."
                )
            closed_dt_str = l.updated_at.strftime('%d-%b-%Y') if l.updated_at else ''

            candidates.append({
                'loan': l,
                'loan_id': l.id,
                'loan_number': l.loan_number,
                'customer': cust,
                'customer_id': cust.id,
                'name': cust_name,
                'phone': norm_phone,
                'raw_phone': raw_phone,
                'branch': branch_name,
                'closed_date': closed_dt_str,
                'message': promo_text,
            })
            seen_customers.add(cust.id)

    # If selective list provided, filter down to selected candidates
    if selected_loan_ids is not None:
        sel_set = set(str(sid) for sid in selected_loan_ids)
        candidates = [c for c in candidates if str(c['loan_id']) in sel_set]

    target_count = len(candidates)

    if dry_run or not candidates:
        summary_msg = f"Identified {target_count} eligible customer(s) for closed loan re-pledge retention promo."
        if not dry_run:
            AutopilotLog.objects.create(
                pillar='pillar_4',
                action_name='Customer Retention Promo Scan',
                target_count=target_count,
                success_count=0,
                failed_count=0,
                summary=summary_msg,
                status='success'
            )
        return {
            'status': 'success',
            'target_count': target_count,
            'message': summary_msg,
            'customers': [
                {
                    'id': c['customer_id'],
                    'loan_id': c['loan_id'],
                    'loan_number': c['loan_number'],
                    'name': c['name'],
                    'phone': c['phone'],
                    'branch': c['branch'],
                    'closed_date': c['closed_date'],
                    'message': c['message']
                }
                for c in candidates
            ]
        }

    # Dispatch via single-session persistent browser context
    batch_res = send_batch_retention_promos_automated(
        promo_items=candidates[:25],
        delay_between_seconds=3,
        headless=True,
        user=user
    )

    sent_count = batch_res.get('sent', 0)
    failed_count = batch_res.get('failed', 0)
    summary_text = f"Pillar 4 Retention Marketing: Dispatched {sent_count} re-pledge promo offers ({failed_count} failed)."

    AutopilotLog.objects.create(
        pillar='pillar_4',
        action_name='Customer Retention Auto-Blast',
        target_count=target_count,
        success_count=sent_count,
        failed_count=failed_count,
        summary=summary_text,
        status='success' if (failed_count == 0 and sent_count > 0) else ('partial' if sent_count > 0 else 'failed')
    )

    return {
        'status': 'success' if (failed_count == 0 and sent_count > 0) else ('partial' if sent_count > 0 else 'failed'),
        'target_count': target_count,
        'sent': sent_count,
        'failed': failed_count,
        'summary': summary_text,
        'message': summary_text,
        'customers': [
            {
                'id': c['customer_id'],
                'loan_id': c['loan_id'],
                'loan_number': c['loan_number'],
                'name': c['name'],
                'phone': c['phone'],
                'branch': c['branch'],
                'closed_date': c['closed_date'],
                'message': c['message']
            }
            for c in candidates
        ]
    }


def run_special_dates_wishes_dispatch(
    config=None,
    dry_run=False,
    forced=False,
    user=None,
    custom_birthday_template: str = None,
    custom_anniversary_template: str = None,
    selected_customer_ids: list = None
) -> dict:
    """
    Identifies customers who have their Birthday or Wedding Anniversary today
    and dispatches warm, personalized WhatsApp wishes automatically.
    """
    if not config:
        config = get_or_create_autopilot_config()

    if not config.is_enabled and not forced:
        return {'status': 'skipped', 'reason': 'Autopilot is disabled'}

    enable_bday = getattr(config, 'enable_birthday_greetings', True)
    enable_anniv = getattr(config, 'enable_anniversary_greetings', True)

    if not enable_bday and not enable_anniv and not forced:
        return {'status': 'skipped', 'reason': 'Birthday and Anniversary greetings are both disabled in configuration'}

    now = timezone.localtime()
    if not is_within_safe_window(config, now.time()) and not forced:
        return {'status': 'skipped', 'reason': 'Outside TRAI safe communication hours (09:00 AM - 07:30 PM)'}

    from accounts.models import Customer
    from transactions.models import AutopilotLog, MarketingCampaignLog
    from transactions.services_whatsapp import normalize_phone_number
    from transactions.services_whatsapp_automator import send_batch_special_wishes_automated, is_whatsapp_paired

    today = now.date()
    candidates = []
    seen_phone_occasions = set()

    # 1. Birthday Candidates
    if enable_bday or forced:
        bday_customers = Customer.objects.filter(
            date_of_birth__month=today.month,
            date_of_birth__day=today.day
        ).select_related('branch')

        for cust in bday_customers:
            raw_phone = getattr(cust, 'phone', '') or ''
            norm_phone = normalize_phone_number(raw_phone)
            if not norm_phone:
                continue

            # Anti-spam: check if already wished birthday today
            already_wished = MarketingCampaignLog.objects.filter(
                recipient_phone__in=[raw_phone, norm_phone],
                template_key='birthday_wishes',
                created_at__date=today
            ).exists()

            if not already_wished or forced:
                cust_name = cust.full_name or cust.first_name or 'Valued Customer'
                branch_name = cust.branch.name if cust.branch else 'First Money Gold'
                branch_phone = getattr(cust.branch, 'phone', '') or '9876543210'

                if custom_birthday_template and custom_birthday_template.strip():
                    wish_msg = (
                        custom_birthday_template
                        .replace('{customer_name}', cust_name)
                        .replace('{name}', cust_name)
                        .replace('{branch_name}', branch_name)
                        .replace('{branch}', branch_name)
                        .replace('{branch_phone}', branch_phone)
                        .replace('{organization_name}', 'First Money Gold')
                    )
                else:
                    wish_msg = (
                        f"🎂 *இனிய பிறந்தநாள் நல்வாழ்த்துகள்! - {branch_name}* 🎂\n\n"
                        f"அன்புள்ள *{cust_name}* அவர்களுக்கு,\n"
                        f"First Money Gold நிறுவனத்தின் சார்பாக தங்களுக்கு எங்களின் மனமார்ந்த பிறந்தநாள் நல்வாழ்த்துகளை தெரிவித்துக் கொள்கிறோம்! ✨\n\n"
                        f"தாங்கள் எல்லா வளமும், நலமும், நீடித்த ஆயுளும் பெற்று மகிழ்ச்சியோடு வாழ மனதார வாழ்த்துகிறோம்.\n\n"
                        f"🌟 தங்களின் பிறந்தநாள் விசேஷ தினத்திற்கு வாழ்த்துகள்!\n"
                        f"அன்புடன்,\n"
                        f"*First Money Gold - {branch_name}*\n"
                        f"📞 தொடர்பு: {branch_phone}"
                    )

                key = (norm_phone, 'birthday')
                if key not in seen_phone_occasions:
                    seen_phone_occasions.add(key)
                    candidates.append({
                        'customer': cust,
                        'customer_id': cust.id,
                        'name': cust_name,
                        'phone': norm_phone,
                        'raw_phone': raw_phone,
                        'branch': branch_name,
                        'occasion_type': 'birthday',
                        'occasion_label': '🎂 Birthday Today',
                        'date': cust.date_of_birth.strftime('%d-%b') if cust.date_of_birth else '',
                        'message': wish_msg,
                    })

    # 2. Wedding Anniversary Candidates
    if enable_anniv or forced:
        anniv_customers = Customer.objects.filter(
            anniversary_date__month=today.month,
            anniversary_date__day=today.day
        ).select_related('branch')

        for cust in anniv_customers:
            raw_phone = getattr(cust, 'phone', '') or ''
            norm_phone = normalize_phone_number(raw_phone)
            if not norm_phone:
                continue

            # Anti-spam: check if already wished anniversary today
            already_wished = MarketingCampaignLog.objects.filter(
                recipient_phone__in=[raw_phone, norm_phone],
                template_key='anniversary_wishes',
                created_at__date=today
            ).exists()

            if not already_wished or forced:
                cust_name = cust.full_name or cust.first_name or 'Valued Customer'
                branch_name = cust.branch.name if cust.branch else 'First Money Gold'
                branch_phone = getattr(cust.branch, 'phone', '') or '9876543210'

                if custom_anniversary_template and custom_anniversary_template.strip():
                    wish_msg = (
                        custom_anniversary_template
                        .replace('{customer_name}', cust_name)
                        .replace('{name}', cust_name)
                        .replace('{branch_name}', branch_name)
                        .replace('{branch}', branch_name)
                        .replace('{branch_phone}', branch_phone)
                        .replace('{organization_name}', 'First Money Gold')
                    )
                else:
                    wish_msg = (
                        f"💍 *இனிய திருமண நாள் நல்வாழ்த்துகள்! - {branch_name}* 💍\n\n"
                        f"அன்புள்ள *{cust_name}* அவர்களுக்கு,\n"
                        f"First Money Gold குடும்பத்தின் சார்பாக தங்களுக்கு எங்களின் மனமார்ந்த திருமண நாள் நல்வாழ்த்துகளை தெரிவித்துக் கொள்கிறோம்! ✨\n\n"
                        f"தாங்கள் என்றும் இல்லற வாழ்வில் நலமும், வளமும், மகிழ்ச்சியும் பெற்று சீரோடும் சிறப்போடும் வாழ வாழ்த்துகிறோம்.\n\n"
                        f"💖 தங்களின் சிறப்பு தினத்திற்கு வாழ்த்துகள்!\n"
                        f"அன்புடன்,\n"
                        f"*First Money Gold - {branch_name}*\n"
                        f"📞 தொடர்பு: {branch_phone}"
                    )

                key = (norm_phone, 'anniversary')
                if key not in seen_phone_occasions:
                    seen_phone_occasions.add(key)
                    candidates.append({
                        'customer': cust,
                        'customer_id': cust.id,
                        'name': cust_name,
                        'phone': norm_phone,
                        'raw_phone': raw_phone,
                        'branch': branch_name,
                        'occasion_type': 'anniversary',
                        'occasion_label': '💍 Wedding Anniversary Today',
                        'date': cust.anniversary_date.strftime('%d-%b') if cust.anniversary_date else '',
                        'message': wish_msg,
                    })

    # If selective list provided, filter down
    if selected_customer_ids is not None:
        sel_set = set(str(cid) for cid in selected_customer_ids)
        candidates = [c for c in candidates if str(c['customer_id']) in sel_set]

    target_count = len(candidates)

    if dry_run or not candidates:
        summary_msg = f"Identified {target_count} customer(s) with special occasions (Birthdays & Anniversaries) today."
        if not dry_run:
            AutopilotLog.objects.create(
                pillar='pillar_4',
                action_name='Special Occasions Wishes Scan',
                target_count=target_count,
                success_count=0,
                failed_count=0,
                summary=summary_msg,
                status='success'
            )
        return {
            'status': 'success',
            'target_count': target_count,
            'message': summary_msg,
            'candidates': [
                {
                    'id': c['customer_id'],
                    'name': c['name'],
                    'phone': c['phone'],
                    'branch': c['branch'],
                    'occasion_type': c['occasion_type'],
                    'occasion_label': c['occasion_label'],
                    'date': c['date'],
                    'message': c['message']
                }
                for c in candidates
            ]
        }

    # Dispatch via single-session persistent browser context
    batch_res = send_batch_special_wishes_automated(
        wish_items=candidates,
        delay_between_seconds=3,
        headless=True,
        user=user
    )

    sent_count = batch_res.get('sent', 0)
    failed_count = batch_res.get('failed', 0)
    summary_text = f"Birthday & Anniversary Wishes: Dispatched {sent_count} greetings ({failed_count} failed)."

    AutopilotLog.objects.create(
        pillar='pillar_4',
        action_name='Birthday & Anniversary Wishes Auto-Blast',
        target_count=target_count,
        success_count=sent_count,
        failed_count=failed_count,
        summary=summary_text,
        status='success' if (failed_count == 0 and sent_count > 0) else ('partial' if sent_count > 0 else 'failed')
    )

    return {
        'status': 'success' if (failed_count == 0 and sent_count > 0) else ('partial' if sent_count > 0 else 'failed'),
        'target_count': target_count,
        'sent': sent_count,
        'failed': failed_count,
        'summary': summary_text,
        'message': summary_text,
        'candidates': [
            {
                'id': c['customer_id'],
                'name': c['name'],
                'phone': c['phone'],
                'branch': c['branch'],
                'occasion_type': c['occasion_type'],
                'occasion_label': c['occasion_label'],
                'date': c['date'],
                'message': c['message']
            }
            for c in candidates
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 5: Automated Executive Daily Digest to Admins & Managers
# ═══════════════════════════════════════════════════════════════════════════════

def get_management_stakeholders():
    """
    Discovers all key Admins, Branch Managers, and Regional Managers across the organization
    and analyzes their profile phone numbers and email addresses.
    Returns:
      {
        'stakeholders': list of dicts,
        'warnings': list of prompt strings for missing values,
        'total_count': int,
        'valid_whatsapp_count': int,
        'valid_email_count': int,
        'missing_contacts_count': int
      }
    """
    from accounts.models import CustomUser
    from branches.models import Branch, RegionalOffice
    from transactions.services_whatsapp import normalize_phone_number

    stakeholders = []
    seen_user_ids = set()
    warnings = []

    # 1. Super Admins & Organization Admins
    admin_users = CustomUser.objects.filter(
        Q(is_superuser=True) | Q(is_pawnshop_admin=True) | Q(is_organization_admin=True) |
        Q(role__name__icontains='admin') | Q(role__role_type='it_admin'),
        is_active=True
    ).distinct()

    for u in admin_users:
        if u.id in seen_user_ids:
            continue
        seen_user_ids.add(u.id)

        full_name = u.get_full_name() or u.username
        clean_phone = normalize_phone_number(u.phone) if u.phone else ''
        clean_email = (u.email or '').strip()

        missing_phone = not bool(clean_phone)
        missing_email = not bool(clean_email)

        phone_warn = f"⚠️ [Missing Phone] Admin '{full_name}' (@{u.username}) has no phone number in profile." if missing_phone else ""
        email_warn = f"⚠️ [Missing Email] Admin '{full_name}' (@{u.username}) has no email address in profile." if missing_email else ""

        if missing_phone:
            warnings.append(phone_warn)
        if missing_email:
            warnings.append(email_warn)

        stakeholders.append({
            'user_id': u.id,
            'username': u.username,
            'name': full_name,
            'role_title': 'Super Admin / Org Admin',
            'role_category': 'admin',
            'phone': clean_phone,
            'raw_phone': u.phone or '',
            'email': clean_email,
            'missing_phone': missing_phone,
            'missing_email': missing_email,
            'phone_warn': phone_warn,
            'email_warn': email_warn,
        })

    # 2. Regional Managers
    for ro in RegionalOffice.objects.filter(regional_manager__isnull=False).select_related('regional_manager'):
        u = ro.regional_manager
        if not u or not u.is_active:
            continue
        seen_user_ids.add(u.id)
        full_name = u.get_full_name() or u.username
        clean_phone = normalize_phone_number(u.phone) if u.phone else ''
        clean_email = (u.email or '').strip()

        missing_phone = not bool(clean_phone)
        missing_email = not bool(clean_email)

        phone_warn = f"⚠️ [Missing Phone] Regional Manager '{full_name}' ({ro.name}) has no phone number in profile." if missing_phone else ""
        email_warn = f"⚠️ [Missing Email] Regional Manager '{full_name}' ({ro.name}) has no email address in profile." if missing_email else ""

        if missing_phone:
            warnings.append(phone_warn)
        if missing_email:
            warnings.append(email_warn)

        stakeholders.append({
            'user_id': u.id,
            'username': u.username,
            'name': full_name,
            'role_title': f"Regional Manager ({ro.name})",
            'role_category': 'regional_manager',
            'phone': clean_phone,
            'raw_phone': u.phone or '',
            'email': clean_email,
            'missing_phone': missing_phone,
            'missing_email': missing_email,
            'phone_warn': phone_warn,
            'email_warn': email_warn,
        })

    rm_users = CustomUser.objects.filter(role__role_type='regional_manager', is_active=True).exclude(id__in=seen_user_ids)
    for u in rm_users:
        seen_user_ids.add(u.id)
        full_name = u.get_full_name() or u.username
        clean_phone = normalize_phone_number(u.phone) if u.phone else ''
        clean_email = (u.email or '').strip()
        missing_phone = not bool(clean_phone)
        missing_email = not bool(clean_email)
        phone_warn = f"⚠️ [Missing Phone] Regional Manager '{full_name}' (@{u.username}) has no phone number in profile." if missing_phone else ""
        email_warn = f"⚠️ [Missing Email] Regional Manager '{full_name}' (@{u.username}) has no email address in profile." if missing_email else ""
        if missing_phone:
            warnings.append(phone_warn)
        if missing_email:
            warnings.append(email_warn)
        stakeholders.append({
            'user_id': u.id,
            'username': u.username,
            'name': full_name,
            'role_title': 'Regional Manager',
            'role_category': 'regional_manager',
            'phone': clean_phone,
            'raw_phone': u.phone or '',
            'email': clean_email,
            'missing_phone': missing_phone,
            'missing_email': missing_email,
            'phone_warn': phone_warn,
            'email_warn': email_warn,
        })

    # 3. Branch Managers
    for b in Branch.objects.filter(manager__isnull=False).select_related('manager'):
        u = b.manager
        if not u or not u.is_active:
            continue
        seen_user_ids.add(u.id)
        full_name = u.get_full_name() or u.username
        clean_phone = normalize_phone_number(u.phone) if u.phone else ''
        clean_email = (u.email or '').strip()

        missing_phone = not bool(clean_phone)
        missing_email = not bool(clean_email)

        phone_warn = f"⚠️ [Missing Phone] Branch Manager '{full_name}' ({b.name}) has no phone number in profile." if missing_phone else ""
        email_warn = f"⚠️ [Missing Email] Branch Manager '{full_name}' ({b.name}) has no email address in profile." if missing_email else ""

        if missing_phone:
            warnings.append(phone_warn)
        if missing_email:
            warnings.append(email_warn)

        stakeholders.append({
            'user_id': u.id,
            'username': u.username,
            'name': full_name,
            'role_title': f"Branch Manager ({b.name})",
            'role_category': 'branch_manager',
            'phone': clean_phone,
            'raw_phone': u.phone or '',
            'email': clean_email,
            'missing_phone': missing_phone,
            'missing_email': missing_email,
            'phone_warn': phone_warn,
            'email_warn': email_warn,
        })

    bm_users = CustomUser.objects.filter(role__role_type='branch_manager', is_active=True).exclude(id__in=seen_user_ids)
    for u in bm_users:
        seen_user_ids.add(u.id)
        full_name = u.get_full_name() or u.username
        clean_phone = normalize_phone_number(u.phone) if u.phone else ''
        clean_email = (u.email or '').strip()
        missing_phone = not bool(clean_phone)
        missing_email = not bool(clean_email)
        b_name = u.branch.name if hasattr(u, 'branch') and u.branch else 'General'
        phone_warn = f"⚠️ [Missing Phone] Branch Manager '{full_name}' ({b_name}) has no phone number in profile." if missing_phone else ""
        email_warn = f"⚠️ [Missing Email] Branch Manager '{full_name}' ({b_name}) has no email address in profile." if missing_email else ""
        if missing_phone:
            warnings.append(phone_warn)
        if missing_email:
            warnings.append(email_warn)
        stakeholders.append({
            'user_id': u.id,
            'username': u.username,
            'name': full_name,
            'role_title': f"Branch Manager ({b_name})",
            'role_category': 'branch_manager',
            'phone': clean_phone,
            'raw_phone': u.phone or '',
            'email': clean_email,
            'missing_phone': missing_phone,
            'missing_email': missing_email,
            'phone_warn': phone_warn,
            'email_warn': email_warn,
        })

    valid_wa = sum(1 for s in stakeholders if s['phone'])
    valid_em = sum(1 for s in stakeholders if s['email'])

    return {
        'stakeholders': stakeholders,
        'warnings': warnings,
        'total_count': len(stakeholders),
        'valid_whatsapp_count': valid_wa,
        'valid_email_count': valid_em,
        'missing_contacts_count': len(warnings)
    }


def send_executive_digest_email(recipient_email, recipient_name, role_title, digest_text, stats_dict):
    """
    Dispatches a branded HTML and plain-text Executive Daily Digest email to a manager/admin.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    if not recipient_email:
        return False, "No email address provided"

    subject = f"📊 Daily Executive Digest - {stats_dict['date_str']} | First Money Gold"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border: 1px solid #e2e8f0; }}
            .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 24px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 20px; }}
            .header p {{ margin: 6px 0 0 0; color: #94a3b8; font-size: 13px; }}
            .content {{ padding: 24px; }}
            .greeting {{ font-size: 15px; margin-bottom: 16px; }}
            table.stats-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            table.stats-table td {{ padding: 10px 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px; }}
            table.stats-table tr:nth-child(even) {{ background-color: #f8fafc; }}
            .footer {{ background: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Executive Daily Business Digest</h1>
                <p>Date: {stats_dict['date_str']} | Generated: {stats_dict['time_str']}</p>
            </div>
            <div class="content">
                <p class="greeting">Dear <strong>{recipient_name}</strong> ({role_title}),</p>
                <p>Here is your automated end-of-day portfolio and collections snapshot for <strong>First Money Gold</strong>:</p>

                <table class="stats-table">
                    <tr>
                        <td><strong>💰 Today's Collections:</strong></td>
                        <td align="right"><strong style="color:#16a34a;">₹{stats_dict['collections']:,.2f}</strong> ({stats_dict['payment_count']} receipts)</td>
                    </tr>
                    <tr>
                        <td><strong>🚀 Today's Disbursements:</strong></td>
                        <td align="right"><strong style="color:#2563eb;">₹{stats_dict['disbursed']:,.2f}</strong> ({stats_dict['new_loan_count']} loans)</td>
                    </tr>
                    <tr>
                        <td><strong>💼 Active Book Principal:</strong></td>
                        <td align="right"><strong>₹{stats_dict['active_principal']:,.2f}</strong> ({stats_dict['active_count']} active accounts)</td>
                    </tr>
                    <tr>
                        <td><strong>⚠️ Delinquent / Overdue:</strong></td>
                        <td align="right"><strong style="color:#dc2626;">₹{stats_dict['overdue_principal']:,.2f}</strong> ({stats_dict['overdue_count']} accounts)</td>
                    </tr>
                    <tr>
                        <td><strong>🤖 24/7 Autopilot Hub:</strong></td>
                        <td align="right"><strong>{stats_dict['autopilot_sent_wa']}</strong> automated WhatsApp dispatches today</td>
                    </tr>
                </table>

                <p style="font-size: 13px; color: #64748b; margin-top: 16px;">
                    This digest was automatically generated and delivered by the <strong>Pawnshop Core 24/7 Autopilot System</strong>.
                </p>
            </div>
            <div class="footer">
                &copy; {stats_dict['year']} First Money Gold. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@pawnshop.com')
        msg = EmailMultiAlternatives(subject=subject, body=digest_text, from_email=from_email, to=[recipient_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        return True, "Email sent successfully"
    except Exception as e:
        logger.warning("Failed to send Executive Digest email to %s: %s", recipient_email, e)
        return False, str(e)


def run_pillar_5_owner_digest(config=None, dry_run=False, forced=False) -> dict:
    """
    Compiles full executive business performance for today and dispatches both
    WhatsApp summaries and Email reports directly to all Admins, Branch Managers,
    and Regional Managers automatically using their user profiles.
    Generates explicit warnings/prompts if any manager's phone or email is missing.
    """
    if not config:
        config = get_or_create_autopilot_config()

    if not config.is_enabled and not forced:
        return {'status': 'skipped', 'reason': 'Autopilot is disabled'}

    if not config.enable_owner_digest and not forced:
        return {'status': 'skipped', 'reason': 'Owner Digest is disabled'}

    from transactions.models import Loan, Payment, AutopilotLog
    from transactions.services_whatsapp import normalize_phone_number
    from transactions.services_whatsapp_automator import send_whatsapp_message_headless, is_whatsapp_paired

    now = timezone.localtime()
    today = now.date()

    # Discover all management stakeholders from profiles
    stakeholder_data = get_management_stakeholders()
    stakeholders = list(stakeholder_data['stakeholders'])
    warnings = list(stakeholder_data['warnings'])

    # Also include manual fallback owner phone/email from config if specified
    if config.owner_phone:
        norm_fallback = normalize_phone_number(config.owner_phone)
        if norm_fallback and not any(s.get('phone') == norm_fallback for s in stakeholders):
            stakeholders.append({
                'user_id': None,
                'username': 'config_owner',
                'name': 'Business Owner (Manual Config)',
                'role_title': 'Primary Owner / Executive',
                'role_category': 'owner',
                'phone': norm_fallback,
                'raw_phone': config.owner_phone,
                'email': (config.owner_email or '').strip(),
                'missing_phone': False,
                'missing_email': not bool(config.owner_email),
                'phone_warn': '',
                'email_warn': ''
            })

    if not stakeholders:
        return {
            'status': 'skipped',
            'reason': 'No active Admins, Branch Managers, or Regional Managers found in the system.',
            'warnings': warnings
        }

    # 1. Today's Collections
    try:
        today_payments = Payment.objects.filter(payment_date=today)
    except Exception:
        today_payments = Payment.objects.filter(created_at__date=today)
    total_collections = today_payments.aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')
    payment_count = today_payments.count()

    # 2. Today's New Loans Issued
    new_loans = Loan.objects.filter(issue_date=today)
    total_disbursed = new_loans.aggregate(tot=Sum('principal_amount'))['tot'] or Decimal('0.00')
    new_loan_count = new_loans.count()

    # 3. Active Portfolio Overview
    active_loans = Loan.objects.filter(status__in=['active', 'approved'])
    total_active_principal = active_loans.aggregate(tot=Sum('principal_amount'))['tot'] or Decimal('0.00')
    active_count = active_loans.count()

    # 4. Delinquency (SMA / NPA)
    overdue_loans = [l for l in active_loans if l.is_overdue]
    overdue_count = len(overdue_loans)
    overdue_principal = sum(l.principal_amount for l in overdue_loans)

    # 5. Autopilot Actions Today
    today_autopilot_logs = AutopilotLog.objects.filter(created_at__date=today)
    autopilot_actions_count = today_autopilot_logs.count()
    autopilot_sent_wa = today_autopilot_logs.aggregate(tot=Sum('success_count'))['tot'] or 0

    stats_dict = {
        'date_str': today.strftime('%d-%b-%Y (%A)'),
        'time_str': now.strftime('%I:%M %p'),
        'year': today.year,
        'collections': total_collections,
        'payment_count': payment_count,
        'disbursed': total_disbursed,
        'new_loan_count': new_loan_count,
        'active_principal': total_active_principal,
        'active_count': active_count,
        'overdue_principal': overdue_principal,
        'overdue_count': overdue_count,
        'autopilot_sent_wa': autopilot_sent_wa,
    }

    # Build Executive WhatsApp Message
    digest_message = (
        f"📊 *DAILY EXECUTIVE SNAPSHOT - First Money Gold*\n"
        f"📅 *Date:* {today.strftime('%d-%b-%Y (%A)')}\n"
        f"⏰ *Generated At:* {now.strftime('%I:%M %p')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *1. TODAY'S COLLECTIONS:*\n"
        f"  • Total Received: *₹{total_collections:,.2f}*\n"
        f"  • Payment Receipts: *{payment_count} transactions*\n\n"
        f"🚀 *2. NEW LOANS DISBURSED:*\n"
        f"  • Total Disbursed: *₹{total_disbursed:,.2f}*\n"
        f"  • New Accounts: *{new_loan_count} loans*\n\n"
        f"💼 *3. ACTIVE PORTFOLIO:*\n"
        f"  • Total Active Loans: *{active_count} accounts*\n"
        f"  • Total Principal in Book: *₹{total_active_principal:,.2f}*\n\n"
        f"⚠️ *4. DELINQUENCY WATCHLIST:*\n"
        f"  • Overdue Loans: *{overdue_count} accounts*\n"
        f"  • Overdue Principal: *₹{overdue_principal:,.2f}*\n\n"
        f"🤖 *5. AUTOPILOT 24/7 STATUS:*\n"
        f"  • System State: *ONLINE & ACTIVE*\n"
        f"  • Operations Run Today: *{autopilot_actions_count} cycles*\n"
        f"  • WhatsApp Dispatches: *{autopilot_sent_wa} sent successfully*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔐 *Pawnshop Core Autopilot System*"
    )

    if dry_run:
        return {
            'status': 'dry_run',
            'message': digest_message,
            'recipients_count': len(stakeholders),
            'stakeholders': [
                {
                    'name': s['name'],
                    'role': s['role_title'],
                    'phone': s['phone'] or 'MISSING',
                    'email': s['email'] or 'MISSING'
                } for s in stakeholders
            ],
            'warnings': warnings
        }

    wa_sent_count = 0
    wa_failed_count = 0
    email_sent_count = 0
    email_failed_count = 0
    wa_paired = is_whatsapp_paired()

    # 1. Dispatch WhatsApp to all stakeholders with valid phone numbers
    for s in stakeholders:
        phone = s.get('phone')
        if phone:
            if wa_paired:
                res = send_whatsapp_message_headless(phone=phone, message=digest_message, headless=True)
                if res.get('success'):
                    wa_sent_count += 1
                else:
                    wa_failed_count += 1
            else:
                wa_failed_count += 1

    # 2. Dispatch Email to all stakeholders with valid email addresses
    for s in stakeholders:
        email = s.get('email')
        if email:
            success, msg = send_executive_digest_email(
                recipient_email=email,
                recipient_name=s['name'],
                role_title=s['role_title'],
                digest_text=digest_message,
                stats_dict=stats_dict
            )
            if success:
                email_sent_count += 1
            else:
                email_failed_count += 1

    summary_str = f"Pillar 5 Executive Digest: WhatsApp (Sent: {wa_sent_count}, Failed: {wa_failed_count}) | Email (Sent: {email_sent_count}, Failed: {email_failed_count})."
    if warnings:
        summary_str += f" [{len(warnings)} profile contact warning(s) detected]"

    err_details = "\n".join(warnings) if warnings else ""

    AutopilotLog.objects.create(
        pillar='pillar_5',
        action_name='Executive Daily Digest (Admins & Managers)',
        target_count=len(stakeholders),
        success_count=wa_sent_count + email_sent_count,
        failed_count=wa_failed_count + email_failed_count,
        summary=summary_str,
        error_details=err_details[:500],
        status='success' if (wa_failed_count == 0 and email_failed_count == 0) else 'partial'
    )

    return {
        'status': 'success' if (wa_failed_count == 0 and email_failed_count == 0) else 'partial',
        'wa_sent': wa_sent_count,
        'wa_failed': wa_failed_count,
        'email_sent': email_sent_count,
        'email_failed': email_failed_count,
        'warnings': warnings,
        'summary': summary_str
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER ORCHESTRATOR & BACKGROUND DAEMON
# ═══════════════════════════════════════════════════════════════════════════════

def run_autopilot_cycle(forced=False, dry_run=False):
    """
    Checks scheduled execution times and runs active pillars.
    Called periodically by background scheduler or management command.
    """
    config = get_or_create_autopilot_config()
    if not config.is_enabled and not forced:
        return {'status': 'idle', 'message': 'Autopilot is paused.'}

    now = timezone.localtime()
    current_time = now.time()
    today_str = now.strftime('%Y-%m-%d')
    results = {}

    try:
        # Check Pillar 2: WhatsApp Collections (default 10:00 AM)
        p2_time = _parse_time(config.whatsapp_dispatch_time, dtime(10, 0))
        if forced or (_LAST_DISPATCH_RECORD['pillar_2_date'] != today_str and current_time >= p2_time):
            res_p2 = run_pillar_2_whatsapp_collections(config=config, forced=forced, dry_run=dry_run)
            results['pillar_2'] = res_p2
            if not dry_run and res_p2.get('status') in ('success', 'partial'):
                _LAST_DISPATCH_RECORD['pillar_2_date'] = today_str

        # Check Pillar 3: LTV Risk Surveillance (default 11:00 AM)
        p3_time = _parse_time(config.ltv_check_time, dtime(11, 0))
        if forced or (_LAST_DISPATCH_RECORD['pillar_3_date'] != today_str and current_time >= p3_time):
            res_p3 = run_pillar_3_ltv_surveillance(config=config, forced=forced, dry_run=dry_run)
            results['pillar_3'] = res_p3
            if not dry_run and res_p3.get('status') in ('success', 'partial'):
                _LAST_DISPATCH_RECORD['pillar_3_date'] = today_str

        # Check Pillar 4: Retention Marketing (default 03:00 PM)
        p4_time = _parse_time(config.marketing_dispatch_time, dtime(15, 0))
        if forced or (_LAST_DISPATCH_RECORD['pillar_4_date'] != today_str and current_time >= p4_time):
            res_p4 = run_pillar_4_retention_marketing(config=config, forced=forced, dry_run=dry_run)
            results['pillar_4'] = res_p4
            if not dry_run and res_p4.get('status') in ('success', 'partial'):
                _LAST_DISPATCH_RECORD['pillar_4_date'] = today_str

        # Check Pillar 4: Birthday & Wedding Anniversary Greetings (Scheduled daily after 09:30 AM)
        if forced or (_LAST_DISPATCH_RECORD['pillar_4_wishes_date'] != today_str and current_time >= dtime(9, 30)):
            res_wishes = run_special_dates_wishes_dispatch(config=config, forced=forced, dry_run=dry_run)
            results['pillar_4_wishes'] = res_wishes
            if not dry_run and res_wishes.get('status') in ('success', 'partial'):
                _LAST_DISPATCH_RECORD['pillar_4_wishes_date'] = today_str

        # Check Pillar 5: Owner Daily Digest (default 08:30 PM)
        p5_time = _parse_time(config.digest_time, dtime(20, 30))
        if forced or (_LAST_DISPATCH_RECORD['pillar_5_date'] != today_str and current_time >= p5_time):
            res_p5 = run_pillar_5_owner_digest(config=config, forced=forced, dry_run=dry_run)
            results['pillar_5'] = res_p5
            if not dry_run and res_p5.get('status') in ('sent', 'success'):
                _LAST_DISPATCH_RECORD['pillar_5_date'] = today_str

        config.last_run_at = now
        config.last_status = 'success'
        config.last_log_summary = f"Autopilot cycle completed at {now.strftime('%d-%b %H:%M:%S')}."
        config.consecutive_failures = 0
        config.save(update_fields=['last_run_at', 'last_status', 'last_log_summary', 'consecutive_failures'])

    except Exception as exc:
        logger.exception("Error in Autopilot master cycle: %s", exc)
        config.last_status = 'error'
        config.last_log_summary = f"Cycle Error: {str(exc)}"
        config.consecutive_failures += 1
        config.save(update_fields=['last_status', 'last_log_summary', 'consecutive_failures'])
        results['error'] = str(exc)

    return results


def _autopilot_background_worker():
    """Background daemon loop checking cycle every 60 seconds."""
    logger.info("🚀 Autopilot Background Daemon started.")
    while not _AUTOPILOT_STOP_EVENT.is_set():
        try:
            run_autopilot_cycle(forced=False)
        except Exception as e:
            logger.error("Autopilot background daemon loop error: %s", e)
        # Sleep for 60 seconds or until stop signal
        _AUTOPILOT_STOP_EVENT.wait(60)


def start_autopilot_daemon():
    """Starts thread-safe singleton background worker if not already running."""
    global _AUTOPILOT_THREAD
    if _AUTOPILOT_THREAD is None or not _AUTOPILOT_THREAD.is_alive():
        _AUTOPILOT_STOP_EVENT.clear()
        _AUTOPILOT_THREAD = threading.Thread(
            target=_autopilot_background_worker,
            name="pawnshop-autopilot-daemon",
            daemon=True
        )
        _AUTOPILOT_THREAD.start()
        logger.info("Autopilot worker thread spawned successfully.")
        return True
    return False
