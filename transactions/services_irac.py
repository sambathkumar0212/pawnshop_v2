"""
transactions/services_irac.py
Services for RBI IRAC (Income Recognition & Asset Classification)
Delinquency Watchlist, Multi-Tier Risk Alerts, and Automated Statutory Notifications.
"""

import logging
import urllib.parse
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count, Q

from transactions.models import Loan, IRACAlertLog
from transactions.services_whatsapp import normalize_phone_number, get_clean_phone_for_url
from transactions.services_eod import classify_loan_irac

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bilingual IRAC Risk Alert Templates
# ---------------------------------------------------------------------------

IRAC_ALERT_TEMPLATES = {
    'SMA_0': {
        'badge': 'Early Due (1-30d)',
        'risk_level': 'Low',
        'title_en': 'Monthly Interest Due Reminder',
        'title_ta': 'மாதாந்திர வட்டி செலுத்த நினைவூட்டல்',
        'body_en': (
            "🔔 *INTEREST PAYMENT REMINDER - {organization_name}*\n\n"
            "Dear *{customer_name}*,\n"
            "This is a gentle reminder that the monthly interest for your Gold Loan *#{loan_number}* is due.\n\n"
            "📋 *Loan Details:*\n"
            "• Principal Amount: *₹{principal_amount}*\n"
            "• Due Amount: *₹{overdue_amount}*\n"
            "• Due Since: *{ref_date}* ({overdue_days} days)\n\n"
            "💡 Kindly pay your monthly interest to maintain a standard account rating and keep your gold loan active.\n\n"
            "📍 Branch: *{branch_name}*\n"
            "📞 Contact: *{branch_phone}*"
        ),
        'body_ta': (
            "🔔 *வட்டி செலுத்த நினைவூட்டல் - {organization_name}*\n\n"
            "அன்புள்ள *{customer_name}*,\n"
            "தங்களின் தங்கக்கடன் *#{loan_number}*-க்கான மாதாந்திர வட்டித் தொகை செலுத்த வேண்டியுள்ளது.\n\n"
            "📋 *கடன் விவரங்கள்:*\n"
            "• அசல் தொகை: *₹{principal_amount}*\n"
            "• செலுத்த வேண்டிய வட்டி: *₹{overdue_amount}*\n"
            "• நிலுவை நாட்கள்: *{overdue_days} நாட்கள்*\n\n"
            "💡 தங்களின் கடன் கணக்கை சீராக வைத்திருக்க மாதாந்திர வட்டியை உடனே செலுத்துமாறு கேட்டுக் கொள்கிறோம்.\n\n"
            "📍 கிளை: *{branch_name}*\n"
            "📞 தொடர்பு: *{branch_phone}*"
        )
    },
    'SMA_1': {
        'badge': 'SMA-1 (31-60d Overdue)',
        'risk_level': 'Moderate',
        'title_en': 'Overdue Interest Warning Notice',
        'title_ta': 'வட்டி நிலுவை எச்சரிக்கை அறிவிப்பு',
        'body_en': (
            "⚠️ *OVERDUE PAYMENT NOTICE - {organization_name}*\n\n"
            "Dear *{customer_name}*,\n"
            "Interest payment for your Gold Loan *#{loan_number}* has been overdue for *{overdue_days} days*.\n\n"
            "📋 *Overdue Summary:*\n"
            "• Principal: *₹{principal_amount}*\n"
            "• Overdue Interest: *₹{overdue_amount}*\n"
            "• Classification: *SMA-1 Watchlist*\n\n"
            "⚡ Please clear your overdue interest immediately to avoid penal charges and adverse credit reporting.\n\n"
            "📍 Visit: *{branch_name}*\n"
            "📞 Helpline: *{branch_phone}*"
        ),
        'body_ta': (
            "⚠️ *வட்டி நிலுவை எச்சரிக்கை - {organization_name}*\n\n"
            "அன்புள்ள *{customer_name}*,\n"
            "தங்களின் தங்கக்கடன் *#{loan_number}*-க்கான வட்டித் தொகை கடந்த *{overdue_days} நாட்களாக* நிலுவையில் உள்ளது.\n\n"
            "📋 *நிலுவை விவரங்கள்:*\n"
            "• அசல் தொகை: *₹{principal_amount}*\n"
            "• நிலுவை வட்டி: *₹{overdue_amount}*\n"
            "• கணக்கு நிலை: *SMA-1 (கண்காணிப்பு)*\n\n"
            "⚡ கூடுதல் அபராத வட்டியைத் தவிர்க்க நிலுவைத் தொகையை உடனடியாக செலுத்துமாறு கேட்டுக் கொள்கிறோம்.\n\n"
            "📍 கிளை: *{branch_name}*\n"
            "📞 தொடர்பு: *{branch_phone}*"
        )
    },
    'SMA_2': {
        'badge': 'SMA-2 (61-90d Pre-NPA)',
        'risk_level': 'High',
        'title_en': 'Critical Pre-NPA Statutory Alert',
        'title_ta': 'முக்கிய Pre-NPA சட்டபூர்வ எச்சரிக்கை',
        'body_en': (
            "🚨 *CRITICAL PRE-NPA STATUTORY ALERT - {organization_name}*\n\n"
            "Dear *{customer_name}*,\n"
            "Your Gold Loan *#{loan_number}* is severely overdue by *{overdue_days} days* (Total Due: *₹{overdue_amount}*).\n\n"
            "⚖️ *RBI Prudential Guidelines Notice:*\n"
            "Under RBI asset classification norms, loans exceeding 90 days overdue are automatically tagged as *Non-Performing Assets (NPA)*, triggering statutory recovery and gold ornament auction notices.\n\n"
            "🔴 *Urgent Action Required:* Please visit *{branch_name}* within 48 hours to clear overdue interest and prevent NPA classification.\n\n"
            "📞 Branch Manager Direct: *{branch_phone}*"
        ),
        'body_ta': (
            "🚨 *அவசர PRE-NPA சட்டபூர்வ அறிவிப்பு - {organization_name}*\n\n"
            "அன்புள்ள *{customer_name}*,\n"
            "தங்களின் தங்கக்கடன் *#{loan_number}*-ன் நிலுவை *{overdue_days} நாட்களைக்* கடந்துள்ளது (மொத்த நிலுவை: *₹{overdue_amount}*).\n\n"
            "⚖️ *ரிசர்வ் வங்கி (RBI) விதிகளின்படி:* 90 நாட்களுக்கு மேல் நிலுவையில் உள்ள கடன்கள் *வாராக்கடனாக (NPA)* வகைப்படுத்தப்பட்டு, நகைகள் ஏல நடவடிக்கைக்கு உட்படுத்தப்படும்.\n\n"
            "🔴 *அவசர நடவடிக்கை:* வாராக்கடன் நடவடிக்கையைத் தவிர்க்க 48 மணி நேரத்திற்குள் கிளையை அணுகி நிலுவையைச் செலுத்தவும்.\n\n"
            "📍 கிளை: *{branch_name}* | 📞 மேலாளர் தொடர்பு: *{branch_phone}*"
        )
    },
    'NPA_SUBSTANDARD': {
        'badge': 'NPA Substandard (91-180d)',
        'risk_level': 'Severe',
        'title_en': 'Formal Statutory NPA Recovery Notice',
        'title_ta': 'வாராக்கடன் சட்டபூர்வ மீட்பு அறிவிப்பு',
        'body_en': (
            "🚨 *FORMAL NPA RECOVERY NOTICE - {organization_name}*\n\n"
            "To: *{customer_name}*\n"
            "Loan Account: *#{loan_number}*\n"
            "Total Outstanding: *₹{total_outstanding}* (Overdue Days: *{overdue_days}*)\n\n"
            "Take notice that your loan has been classified as *Non-Performing Asset (NPA Substandard)* as per statutory prudential guidelines.\n\n"
            "⚖️ Unless the full outstanding dues are cleared within 7 days, recovery proceedings and ornament liquidation will be initiated as per the loan agreement.\n\n"
            "📍 Authorized Branch: *{branch_name}*\n"
            "📞 Recovery Desk: *{branch_phone}*"
        ),
        'body_ta': (
            "🚨 *வாராக்கடன் (NPA) சட்டபூர்வ மீட்பு அறிவிப்பு - {organization_name}*\n\n"
            "பெறுநர்: *{customer_name}*\n"
            "கடன் எண்: *#{loan_number}*\n"
            "மொத்த நிலுவைத் தொகை: *₹{total_outstanding}* (நிலுவை: *{overdue_days} நாட்கள்*)\n\n"
            "தங்களின் கடன் கணக்கு விதிமுறைகளின்படி *வாராக்கடனாக (NPA)* வகைப்படுத்தப்பட்டுள்ளது என்பதைத் தெரிவித்துக் கொள்கிறோம்.\n\n"
            "⚖️ 7 நாட்களுக்குள் நிலுவைத் தொகையை முழுமையாகச் செலுத்தி தங்களின் அடமான நகைகளை மீட்கவும். தவறினால் ஏல நடவடிக்கைகள் துவக்கப்படும்.\n\n"
            "📍 கிளை: *{branch_name}* | 📞 தொடர்பு: *{branch_phone}*"
        )
    },
    'NPA_LOSS': {
        'badge': 'Auction & Liquidation (>365d)',
        'risk_level': 'Critical',
        'title_en': 'Final Gold Ornament Public Auction Notice',
        'title_ta': 'இறுதி தங்க நகை பொது ஏல அறிவிப்பு',
        'body_en': (
            "⚖️ *FINAL GOLD ORNAMENT PUBLIC AUCTION NOTICE - {organization_name}*\n\n"
            "To: *{customer_name}*\n"
            "Loan Reference: *#{loan_number}* (Pledged on: *{issue_date}*)\n"
            "Total Principal + Accrued Interest: *₹{total_outstanding}*\n\n"
            "Notice is hereby given that the gold ornaments pledged under Loan #{loan_number} are listed for *Statutory Public Auction* to recover defaulted dues.\n\n"
            "🔴 *FINAL OPPORTUNITY:* You may redeem your ornaments by settling total outstanding dues in full at *{branch_name}* before the auction date.\n\n"
            "📞 Auction & Recovery Desk: *{branch_phone}*"
        ),
        'body_ta': (
            "⚖️ *இறுதி தங்க நகை பொது ஏல அறிவிப்பு - {organization_name}*\n\n"
            "பெறுநர்: *{customer_name}*\n"
            "கடன் எண்: *#{loan_number}* (அடகு தேதி: *{issue_date}*)\n"
            "மொத்த அசல் மற்றும் வட்டி நிலுவை: *₹{total_outstanding}*\n\n"
            "கடன் #{loan_number}-ன் கீழ் அடமானம் வைக்கப்பட்ட தங்க நகைகள் நிலுவைத் தொகையை ஈடுசெய்ய *பொது ஏலத்திற்கு* பட்டியலிடப்பட்டுள்ளது.\n\n"
            "🔴 *கடைசி வாய்ப்பு:* ஏல தேதிக்கு முன் கிளைக்கு நேரில் வந்து முழு நிலுவைத் தொகையைச் செலுத்தி நகைகளை மீட்டுக் கொள்ளலாம்.\n\n"
            "📍 கிளை: *{branch_name}* | 📞 தொடர்பு: *{branch_phone}*"
        )
    }
}


def get_alert_bucket_for_loan(loan, as_of_date=None):
    """
    Returns the appropriate alert template key ('SMA_0', 'SMA_1', 'SMA_2', 'NPA_SUBSTANDARD', 'NPA_LOSS')
    based on IRAC classification status and overdue days.
    """
    if as_of_date is None:
        as_of_date = timezone.now().date()

    irac_status, overdue_days, prov_pct, npa_date = classify_loan_irac(loan, as_of_date=as_of_date)

    if irac_status in IRAC_ALERT_TEMPLATES:
        return irac_status, overdue_days, prov_pct
    elif irac_status in ['NPA_DOUBTFUL', 'NPA_LOSS']:
        return 'NPA_LOSS', overdue_days, prov_pct
    else:
        return 'SMA_0', overdue_days, prov_pct


def render_irac_alert_message(loan, bucket=None, use_tamil=None, lang=None, as_of_date=None):
    """
    Renders personalized IRAC alert message for a loan in Tamil or English.
    """
    if as_of_date is None:
        as_of_date = timezone.now().date()

    if lang is not None:
        use_tamil = (lang == 'ta' or lang == 'both')
    elif use_tamil is None:
        use_tamil = True

    if not bucket:
        bucket, overdue_days, _ = get_alert_bucket_for_loan(loan, as_of_date)
    else:
        ref_date = loan.grace_period_end or loan.due_date
        overdue_days = max(0, (as_of_date - ref_date).days) if ref_date else 0

    template_dict = IRAC_ALERT_TEMPLATES.get(bucket) or IRAC_ALERT_TEMPLATES['SMA_0']
    
    if lang == 'both':
        raw_body = f"{template_dict['body_en']}\n\n{'─'*24}\n\n{template_dict['body_ta']}"
    else:
        raw_body = template_dict['body_ta'] if use_tamil else template_dict['body_en']

    cust_name = f"{loan.customer.first_name} {loan.customer.last_name}".strip() if loan.customer else "Valued Customer"
    principal = f"{(loan.principal_amount or Decimal('0.00')):,.2f}"
    accrued_int = loan.accrued_interest or Decimal('0.00')
    overdue_amt = f"{accrued_int:,.2f}" if accrued_int > 0 else principal
    total_outstanding = f"{((loan.principal_amount or 0) + accrued_int):,.2f}"
    ref_date_str = (loan.grace_period_end or loan.due_date or loan.issue_date).strftime('%d-%b-%Y')
    issue_date_str = loan.issue_date.strftime('%d-%b-%Y') if loan.issue_date else "N/A"

    branch_name = loan.branch.name if loan.branch else "Main Branch"
    branch_phone = loan.branch.phone if (loan.branch and loan.branch.phone) else getattr(settings, 'COMPANY_PHONE', 'Customer Care')
    org_name = getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold')

    msg = raw_body \
        .replace('{customer_name}', cust_name) \
        .replace('{loan_number}', loan.loan_number or '') \
        .replace('{principal_amount}', principal) \
        .replace('{overdue_amount}', overdue_amt) \
        .replace('{total_outstanding}', total_outstanding) \
        .replace('{overdue_days}', str(overdue_days)) \
        .replace('{ref_date}', ref_date_str) \
        .replace('{issue_date}', issue_date_str) \
        .replace('{branch_name}', branch_name) \
        .replace('{branch_phone}', branch_phone) \
        .replace('{organization_name}', org_name)

    return msg


def build_irac_alert_url(loan, bucket=None, use_tamil=True):
    """
    Builds direct WhatsApp web URL for sending IRAC alert.
    """
    phone = get_clean_phone_for_url(loan.customer.phone) if (loan.customer and loan.customer.phone) else ''
    if not phone:
        return ''

    msg = render_irac_alert_message(loan, bucket=bucket, use_tamil=use_tamil)
    encoded = urllib.parse.quote(msg)
    return f"https://web.whatsapp.com/send?phone={phone}&text={encoded}"


def log_irac_alert(loan, bucket, channel='whatsapp_web', status='sent', message_text='', user=None, overdue_days=None, overdue_amount=None):
    """
    Logs dispatched alert into IRACAlertLog table.
    """
    if overdue_days is None:
        ref_date = loan.grace_period_end or loan.due_date
        overdue_days = max(0, (timezone.now().date() - ref_date).days) if ref_date else 0

    if overdue_amount is None:
        overdue_amount = loan.accrued_interest or loan.principal_amount or Decimal('0.00')

    log_entry = IRACAlertLog.objects.create(
        loan=loan,
        customer=loan.customer,
        irac_bucket=bucket,
        overdue_days=overdue_days,
        overdue_amount=overdue_amount,
        channel=channel,
        status=status,
        message_sent=message_text or '',
        sent_by=user if user and user.is_authenticated else None
    )

    try:
        from transactions.models import LoanWhatsAppLog
        LoanWhatsAppLog.objects.create(
            loan=loan,
            customer=loan.customer,
            recipient_phone=getattr(loan.customer, 'phone', '') or '',
            notification_type=f"irac_{bucket.lower()}",
            status=status.lower() if status else 'sent',
            message_content=message_text or f"Regulatory IRAC Alert [{bucket}]",
            channel=channel.lower() if channel else 'whatsapp_web',
            sent_by=user if user and user.is_authenticated else None,
        )
    except Exception:
        pass

    return log_entry


def get_delinquency_watchlist(branch_id=None, bucket_filter=None, search_query=None, use_tamil=True):
    """
    Fetches full delinquency watchlist with real-time IRAC calculations,
    provisioning amounts, risk badges, and direct WhatsApp URLs.
    """
    today = timezone.now().date()

    loans_qs = Loan.objects.filter(status__in=['active', 'approved']).select_related('customer', 'branch', 'scheme')

    if branch_id and str(branch_id).isdigit():
        loans_qs = loans_qs.filter(branch_id=int(branch_id))

    watchlist = []

    # Portfolio stats
    stats = {
        'total_overdue_loans': 0,
        'total_overdue_principal': Decimal('0.00'),
        'total_accrued_interest': Decimal('0.00'),
        'total_provisioning_required': Decimal('0.00'),
        'sma0_count': 0,
        'sma0_principal': Decimal('0.00'),
        'sma1_count': 0,
        'sma1_principal': Decimal('0.00'),
        'sma2_count': 0,
        'sma2_principal': Decimal('0.00'),
        'npa_count': 0,
        'npa_principal': Decimal('0.00'),
    }

    for loan in loans_qs:
        irac_status, overdue_days, prov_pct, npa_date = classify_loan_irac(loan, as_of_date=today)

        principal = loan.principal_amount or Decimal('0.00')
        accrued = loan.accrued_interest or Decimal('0.00')
        total_due = principal + accrued
        prov_amt = (principal * prov_pct) / Decimal('100.00')
        prov_amt = prov_amt.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Count in stats if overdue > 0 or in SMA/NPA
        if overdue_days > 0 or irac_status != 'STANDARD':
            stats['total_overdue_loans'] += 1
            stats['total_overdue_principal'] += principal
            stats['total_accrued_interest'] += accrued
            stats['total_provisioning_required'] += prov_amt

            if irac_status == 'SMA_0':
                stats['sma0_count'] += 1
                stats['sma0_principal'] += principal
            elif irac_status == 'SMA_1':
                stats['sma1_count'] += 1
                stats['sma1_principal'] += principal
            elif irac_status == 'SMA_2':
                stats['sma2_count'] += 1
                stats['sma2_principal'] += principal
            elif irac_status.startswith('NPA'):
                stats['npa_count'] += 1
                stats['npa_principal'] += principal

        # Apply bucket filter
        if bucket_filter:
            if bucket_filter == 'NPA':
                if not irac_status.startswith('NPA'):
                    continue
            elif bucket_filter == 'ALL_OVERDUE':
                if overdue_days <= 0 and irac_status == 'STANDARD':
                    continue
            elif irac_status != bucket_filter:
                continue
        else:
            # Default: show all overdue accounts
            if overdue_days <= 0 and irac_status == 'STANDARD':
                continue

        # Search filter
        if search_query:
            q = search_query.lower()
            cust_name = f"{loan.customer.first_name} {loan.customer.last_name}".lower() if loan.customer else ""
            cust_phone = (loan.customer.phone or "").lower() if loan.customer else ""
            loan_num = (loan.loan_number or "").lower()
            if q not in cust_name and q not in cust_phone and q not in loan_num:
                continue

        # Build Alert URL & Message
        alert_bucket = irac_status if irac_status in IRAC_ALERT_TEMPLATES else ('NPA_LOSS' if irac_status.startswith('NPA') else 'SMA_0')
        alert_msg = render_irac_alert_message(loan, bucket=alert_bucket, use_tamil=use_tamil, as_of_date=today)
        whatsapp_url = build_irac_alert_url(loan, bucket=alert_bucket, use_tamil=use_tamil)

        # Last alert info
        last_alert = loan.irac_alert_logs.order_by('-created_at').first()

        watchlist.append({
            'loan': loan,
            'loan_id': loan.id,
            'loan_number': loan.loan_number,
            'customer_name': f"{loan.customer.first_name} {loan.customer.last_name}".strip() if loan.customer else "N/A",
            'customer_phone': loan.customer.phone if loan.customer else "",
            'branch_name': loan.branch.name if loan.branch else "Main Branch",
            'branch_id': loan.branch.id if loan.branch else "",
            'principal_amount': principal,
            'accrued_interest': accrued,
            'total_due': total_due,
            'issue_date': loan.issue_date,
            'due_date': loan.due_date,
            'grace_period_end': loan.grace_period_end,
            'overdue_days': overdue_days,
            'irac_status': irac_status,
            'provisioning_percentage': prov_pct,
            'provisioning_amount': prov_amt,
            'alert_bucket': alert_bucket,
            'alert_message': alert_msg,
            'whatsapp_url': whatsapp_url,
            'last_alert_at': last_alert.created_at if last_alert else None,
            'last_alert_bucket': last_alert.irac_bucket if last_alert else None,
        })

    # Sort by highest overdue days first
    watchlist.sort(key=lambda x: x['overdue_days'], reverse=True)

    return watchlist, stats
