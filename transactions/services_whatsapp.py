"""
transactions/services_whatsapp.py
WhatsApp notification helpers for the Pawnshop Management System.
Supports PyWhatKit background automation and direct WhatsApp Web (wa.me) links
with bilingual (English / Tamil) message formatting.
"""

import logging
import re
import threading
import urllib.parse
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.utils.translation import get_language

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phone Number Helper
# ---------------------------------------------------------------------------

def normalize_phone_number(raw_phone, default_country_code='+91'):
    """
    Normalizes phone number to E.164-like format (e.g., '+919876543210').
    Returns None if phone cannot be normalized to a valid mobile number.
    """
    if not raw_phone:
        return None
    raw_str = str(raw_phone).strip()
    # Remove whitespace, dashes, parentheses, dots
    cleaned = re.sub(r'[\s\-\(\)\.]+', '', raw_str)
    if not cleaned:
        return None

    # If starts with +, ensure digits follow
    if cleaned.startswith('+'):
        digits = re.sub(r'\D', '', cleaned[1:])
        return f"+{digits}" if len(digits) >= 10 else None

    # Remove leading zero if present for 10-digit national format
    if cleaned.startswith('0') and len(cleaned) == 11:
        cleaned = cleaned[1:]

    # 10-digit Indian number
    if len(cleaned) == 10 and cleaned.isdigit():
        return f"{default_country_code}{cleaned}"

    # 12-digit Indian number starting with 91
    if len(cleaned) == 12 and cleaned.startswith('91') and cleaned.isdigit():
        return f"+{cleaned}"

    # General digits fallback
    digits = re.sub(r'\D', '', cleaned)
    if len(digits) >= 10:
        return f"+{digits}"

    return None


def get_clean_phone_for_url(phone_number):
    """Returns digits only without leading '+' for wa.me URLs."""
    if not phone_number:
        return ''
    return re.sub(r'\D', '', str(phone_number))


def get_whatsapp_link(phone_number, message_text):
    """
    Generates a direct WhatsApp web/app launch URL (https://wa.me/...).
    """
    norm_phone = normalize_phone_number(phone_number)
    if not norm_phone:
        return ''
    digits = get_clean_phone_for_url(norm_phone)
    encoded_text = urllib.parse.quote(message_text or '')
    return f"https://wa.me/{digits}?text={encoded_text}"


# ---------------------------------------------------------------------------
# Data Helpers
# ---------------------------------------------------------------------------

def _get_total_payable(loan):
    """Returns (total_due, interest_due) in Decimal."""
    try:
        from transactions.services_partial_release import get_loan_current_interest_due
        interest_due = get_loan_current_interest_due(loan)
    except Exception:
        interest_due = Decimal('0.00')
    principal = Decimal(str(getattr(loan, 'principal_amount', 0) or 0))
    return principal + interest_due, interest_due


def _customer_name(loan):
    try:
        c = loan.customer
        return (
            getattr(c, 'full_name', None)
            or f"{getattr(c, 'first_name', '')} {getattr(c, 'last_name', '')}".strip()
            or 'Valued Customer'
        )
    except Exception:
        return 'Valued Customer'


def _customer_phone(loan):
    try:
        c = loan.customer
        return getattr(c, 'phone', '') or ''
    except Exception:
        return ''


def _detect_tamil(loan, lang=None):
    """Detect whether to output in Tamil."""
    if lang is not None:
        return str(lang).lower().startswith('ta')
    try:
        curr_lang = get_language()
        if curr_lang and str(curr_lang).lower().startswith('ta'):
            return True
    except Exception:
        pass
    try:
        c = loan.customer
        return bool(
            getattr(c, 'first_name_tamil', None)
            or getattr(c, 'last_name_tamil', None)
            or getattr(c, 'address_tamil', None)
        )
    except Exception:
        return False


def _compute_days_left(loan):
    """Returns (days_left: int or None, is_overdue: bool)."""
    try:
        today = timezone.now().date()
        ref = getattr(loan, 'grace_period_end', None) or getattr(loan, 'due_date', None)
        if not ref:
            return None, False
        delta = (ref - today).days
        return delta, delta < 0
    except Exception:
        return None, False


def _get_branch_info(loan):
    branch = getattr(loan, 'branch', None)
    name = getattr(branch, 'name', '') if branch else ''
    phone = getattr(branch, 'phone', '') if branch else ''
    org_name = getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold')
    return {
        'branch_name': name,
        'branch_phone': phone,
        'org_name': org_name,
    }


# ---------------------------------------------------------------------------
# Message Builders
# ---------------------------------------------------------------------------

def build_payment_receipt_whatsapp(payment, use_tamil=False):
    """Build WhatsApp text message for payment confirmation."""
    loan = payment.loan
    customer_name = _customer_name(loan)
    total_due, _ = _get_total_payable(loan)
    b_info = _get_branch_info(loan)
    b_display = b_info['branch_name'] or b_info['org_name']
    
    pay_date = payment.payment_date.strftime('%d/%m/%Y') if hasattr(payment.payment_date, 'strftime') else str(payment.payment_date)
    due_date = loan.due_date.strftime('%d/%m/%Y') if loan.due_date else 'N/A'

    if use_tamil:
        return (
            f"💰 *கட்டணம் உறுதிப்படுத்தல் - {b_info['org_name']}*\n\n"
            f"அன்புள்ள *{customer_name}*,\n"
            f"தங்கக் கடன் *#{loan.loan_number}* -க்கான உங்கள் கட்டணம் வெற்றிகரமாக பெறப்பட்டது. நன்றி!\n\n"
            f"📋 *கட்டண விவரங்கள்:*\n"
            f"• *செலுத்திய தொகை:* ₹{payment.amount:,.2f}\n"
            f"• *கட்டண தேதி:* {pay_date}\n"
            f"• *கட்டண முறை:* {payment.get_payment_method_display()}\n"
            f"• *நிலுவை அசல்:* ₹{loan.principal_amount:,.2f}\n"
            f"• *கடன் நிலுவை தேதி:* {due_date}\n"
            f"• *இன்றைய மொத்த நிலுவை:* ₹{total_due:,.2f}\n\n"
            f"தொடர்புக்கு: {b_display}"
            + (f" | 📞 {b_info['branch_phone']}" if b_info['branch_phone'] else "")
        )
    else:
        return (
            f"💰 *Payment Received - {b_info['org_name']}*\n\n"
            f"Dear *{customer_name}*,\n"
            f"We have received your payment of *₹{payment.amount:,.2f}* against Gold Loan *#{loan.loan_number}* on {pay_date}.\n\n"
            f"📋 *Transaction Summary:*\n"
            f"• *Amount Paid:* ₹{payment.amount:,.2f}\n"
            f"• *Date:* {pay_date}\n"
            f"• *Payment Mode:* {payment.get_payment_method_display()}\n"
            f"• *Outstanding Principal:* ₹{loan.principal_amount:,.2f}\n"
            f"• *Loan Due Date:* {due_date}\n"
            f"• *Today's Net Payable:* ₹{total_due:,.2f}\n\n"
            f"Regards,\n{b_display}"
            + (f" | 📞 {b_info['branch_phone']}" if b_info['branch_phone'] else "")
        )


def build_due_date_reminder_whatsapp(loan, days_left=None, use_tamil=False):
    """Build WhatsApp text message for upcoming or overdue loan reminder."""
    customer_name = _customer_name(loan)
    total_due, interest_due = _get_total_payable(loan)
    b_info = _get_branch_info(loan)
    b_display = b_info['branch_name'] or b_info['org_name']

    computed_days, is_overdue = _compute_days_left(loan)
    if days_left is None:
        days_left = computed_days
    is_overdue = days_left is not None and days_left < 0
    overdue_days = abs(days_left) if is_overdue else 0

    due_date = loan.due_date.strftime('%d/%m/%Y') if loan.due_date else 'N/A'

    if use_tamil:
        if is_overdue:
            return (
                f"🚨 *அவசர அறிவிப்பு: தாமத தங்கக் கடன் - {b_info['org_name']}*\n\n"
                f"அன்புள்ள *{customer_name}*,\n"
                f"உங்கள் தங்கக் கடன் *#{loan.loan_number}* நிலுவை தேதி (*{due_date}*) கடந்து *{overdue_days} நாட்கள்* ஆகிவிட்டன.\n\n"
                f"📊 *நிலுவை விவரங்கள்:*\n"
                f"• *கடன் எண்:* #{loan.loan_number}\n"
                f"• *நிலுவை அசல்:* ₹{loan.principal_amount:,.2f}\n"
                f"• *வட்டி & கட்டணம்:* ₹{interest_due:,.2f}\n"
                f"• *இன்றைய மொத்த செலுத்த வேண்டிய தொகை:* *₹{total_due:,.2f}*\n\n"
                f"⚠️ *எச்சரிக்கை:* தங்க நகைகள் ஏலம் விடப்படுவதை தவிர்க்க உடனடியாக கிளையை அணுகி நிலுவையை செலுத்தவும்.\n\n"
                f"கிளை: {b_display}"
                + (f" | 📞 {b_info['branch_phone']}" if b_info['branch_phone'] else "")
            )
        else:
            days_str = f"({days_left} நாள் உள்ளது)" if (days_left is not None and days_left >= 0) else ""
            return (
                f"🔔 *நினைவூட்டல்: தங்கக் கடன் நிலுவை தேதி - {b_info['org_name']}*\n\n"
                f"அன்புள்ள *{customer_name}*,\n"
                f"உங்கள் தங்கக் கடன் *#{loan.loan_number}* நிலுவை தேதி அணுகி வருகிறது.\n\n"
                f"📊 *கடன் விவரங்கள்:*\n"
                f"• *கடன் எண்:* #{loan.loan_number}\n"
                f"• *நிலுவை தேதி:* {due_date} {days_str}\n"
                f"• *நிலுவை அசல்:* ₹{loan.principal_amount:,.2f}\n"
                f"• *வட்டி:* ₹{interest_due:,.2f}\n"
                f"• *இன்றைய மொத்த செலுத்த வேண்டிய தொகை:* *₹{total_due:,.2f}*\n\n"
                f"கடனை முடிக்க அல்லது நீட்டிக்க உங்கள் கிளையை தொடர்பு கொள்ளவும்.\n\n"
                f"கிளை: {b_display}"
                + (f" | 📞 {b_info['branch_phone']}" if b_info['branch_phone'] else "")
            )
    else:
        if is_overdue:
            return (
                f"🚨 *OVERDUE NOTICE - {b_info['org_name']}*\n\n"
                f"Dear *{customer_name}*,\n"
                f"Your Gold Loan *#{loan.loan_number}* was due on *{due_date}* and is now *{overdue_days} day(s) overdue*.\n\n"
                f"📊 *Account Details:*\n"
                f"• *Loan Number:* #{loan.loan_number}\n"
                f"• *Due Date:* {due_date}\n"
                f"• *Principal:* ₹{loan.principal_amount:,.2f}\n"
                f"• *Accrued Interest:* ₹{interest_due:,.2f}\n"
                f"• *Today's Net Payable:* *₹{total_due:,.2f}*\n\n"
                f"⚠️ *Urgent Action Required:* Please visit the branch immediately to settle dues and prevent auction of your pledged gold ornaments.\n\n"
                f"Branch: {b_display}"
                + (f" | 📞 {b_info['branch_phone']}" if b_info['branch_phone'] else "")
            )
        else:
            days_str = f"({days_left} day{'s' if days_left != 1 else ''} remaining)" if (days_left is not None and days_left >= 0) else ""
            return (
                f"🔔 *Due Date Reminder - {b_info['org_name']}*\n\n"
                f"Dear *{customer_name}*,\n"
                f"This is a friendly reminder that your Gold Loan *#{loan.loan_number}* maturity date is approaching.\n\n"
                f"📊 *Account Details:*\n"
                f"• *Loan Number:* #{loan.loan_number}\n"
                f"• *Due Date:* {due_date} {days_str}\n"
                f"• *Principal:* ₹{loan.principal_amount:,.2f}\n"
                f"• *Accrued Interest:* ₹{interest_due:,.2f}\n"
                f"• *Today's Net Payable:* *₹{total_due:,.2f}*\n\n"
                f"Please visit your branch to redeem your ornaments or renew your loan.\n\n"
                f"Branch: {b_display}"
                + (f" | 📞 {b_info['branch_phone']}" if b_info['branch_phone'] else "")
            )


def build_demand_notice_whatsapp(loan, request_user=None, use_tamil=False):
    """Build WhatsApp text message for legal expiry/demand notice (auction warning)."""
    customer_name = _customer_name(loan)
    total_due, interest_due = _get_total_payable(loan)
    b_info = _get_branch_info(loan)
    b_display = b_info['branch_name'] or b_info['org_name']

    days_left, is_overdue = _compute_days_left(loan)
    overdue_days = abs(days_left) if (days_left is not None and days_left < 0) else 0
    due_date = loan.due_date.strftime('%d/%m/%Y') if loan.due_date else 'N/A'
    today_str = timezone.now().date().strftime('%d/%m/%Y')

    if use_tamil:
        return (
            f"⚖️ *சட்டப்பூர்வ கோரிக்கை & ஏல அறிவிப்பு*\n"
            f"*{b_info['org_name']}*\n\n"
            f"பெறுநர்: *{customer_name}*\n"
            f"தேதி: {today_str}\n"
            f"கடன் எண்: *#{loan.loan_number}*\n\n"
            f"உங்கள் தங்கக் கடன் நிலுவை தேதி (*{due_date}*) கடந்துவிட்டது. நிலுவைத் தொகை இன்னும் செலுத்தப்படவில்லை.\n\n"
            f"💰 *மொத்த நிலுவை தொகை: ₹{total_due:,.2f}*\n"
            f"(அசல்: ₹{loan.principal_amount:,.2f} | வட்டி & தாமதக் கட்டணம்: ₹{interest_due:,.2f})\n\n"
            f"📢 *இறுதி ஏல எச்சரிக்கை:*\n"
            f"இந்த அறிவிப்பு கிடைத்த *7 நாட்களுக்குள்* முழு நிலுவைத் தொகையை செலுத்தி நகைகளை மீட்கவும். தவறினால் அடமான தங்க நகைகள் *பொது ஏலத்தில் விற்கப்படும்*.\n\n"
            f"உடனடியாக தொடர்பு கொள்ளவும்:\n"
            f"கிளை: *{b_display}*"
            + (f"\n📞 தொலைபேசி: {b_info['branch_phone']}" if b_info['branch_phone'] else "")
        )
    else:
        return (
            f"⚖️ *FINAL LEGAL DEMAND & AUCTION NOTICE*\n"
            f"*{b_info['org_name']}*\n\n"
            f"To: *{customer_name}*\n"
            f"Date: {today_str}\n"
            f"Loan No: *#{loan.loan_number}*\n\n"
            f"Your Gold Loan has exceeded its redemption period (Due Date: {due_date}).\n\n"
            f"💰 *Total Outstanding Due: ₹{total_due:,.2f}*\n"
            f"(Principal: ₹{loan.principal_amount:,.2f} | Accrued Interest & Fees: ₹{interest_due:,.2f})\n\n"
            f"📢 *FINAL AUCTION NOTICE:*\n"
            f"You are called upon to clear all dues within *7 (Seven) Days* of this notice. Failure to do so will result in the pledged gold ornaments being sold via *Public Auction* without further notice.\n\n"
            f"Please visit the branch immediately:\n"
            f"Branch: *{b_display}*"
            + (f"\n📞 Phone: {b_info['branch_phone']}" if b_info['branch_phone'] else "")
        )


# ---------------------------------------------------------------------------
# PyWhatKit Execution Helper (Background Thread)
# ---------------------------------------------------------------------------

def _run_pywhatkit_send(phone, message, wait_time=15, tab_close=True, close_time=3):
    """Executes pywhatkit sendwhatmsg_instantly in a safe background thread."""
    try:
        import pywhatkit
        logger.info("Executing PyWhatKit dispatch to %s...", phone)
        pywhatkit.sendwhatmsg_instantly(
            phone_no=phone,
            message=message,
            wait_time=wait_time,
            tab_close=tab_close,
            close_time=close_time
        )
        logger.info("PyWhatKit dispatch completed for %s.", phone)
    except Exception as exc:
        logger.warning("PyWhatKit dispatch failed for %s: %s", phone, exc)


def send_pywhatkit_async(phone_number, message_text, wait_time=15, tab_close=True, close_time=3):
    """
    Spawns a daemon thread to send WhatsApp message via PyWhatKit.
    Returns True if thread started, False if phone invalid.
    """
    norm_phone = normalize_phone_number(phone_number)
    if not norm_phone:
        logger.warning("send_pywhatkit_async: invalid phone number %s", phone_number)
        return False

    t = threading.Thread(
        target=_run_pywhatkit_send,
        args=(norm_phone, message_text, wait_time, tab_close, close_time),
        daemon=True,
        name=f"pywhatkit-send-{norm_phone}"
    )
    t.start()
    return True


# ---------------------------------------------------------------------------
# High-Level Service Dispatchers
# ---------------------------------------------------------------------------

def send_customer_payment_whatsapp(payment, lang=None, send_pywhatkit=False):
    """
    Builds payment confirmation WhatsApp message, returns direct link and optionally triggers PyWhatKit.
    """
    loan = payment.loan
    raw_phone = _customer_phone(loan)
    norm_phone = normalize_phone_number(raw_phone)
    use_tamil = _detect_tamil(loan, lang)
    msg = build_payment_receipt_whatsapp(payment, use_tamil)
    link = get_whatsapp_link(norm_phone, msg) if norm_phone else ''

    pywhatkit_started = False
    if send_pywhatkit and norm_phone:
        pywhatkit_started = send_pywhatkit_async(norm_phone, msg)

    return {
        'success': bool(norm_phone),
        'phone': norm_phone or raw_phone,
        'link': link,
        'message': msg,
        'pywhatkit_started': pywhatkit_started,
        'use_tamil': use_tamil,
    }


def send_due_date_reminder_whatsapp(loan, days_left=None, lang=None, send_pywhatkit=False):
    """
    Builds due-date / overdue WhatsApp message, returns direct link and optionally triggers PyWhatKit.
    """
    raw_phone = _customer_phone(loan)
    norm_phone = normalize_phone_number(raw_phone)
    use_tamil = _detect_tamil(loan, lang)
    msg = build_due_date_reminder_whatsapp(loan, days_left=days_left, use_tamil=use_tamil)
    link = get_whatsapp_link(norm_phone, msg) if norm_phone else ''

    pywhatkit_started = False
    if send_pywhatkit and norm_phone:
        pywhatkit_started = send_pywhatkit_async(norm_phone, msg)

    return {
        'success': bool(norm_phone),
        'phone': norm_phone or raw_phone,
        'link': link,
        'message': msg,
        'pywhatkit_started': pywhatkit_started,
        'use_tamil': use_tamil,
    }


def send_loan_expiry_notice_whatsapp(loan, request_user=None, lang=None, send_pywhatkit=False):
    """
    Builds demand / auction WhatsApp message, returns direct link and optionally triggers PyWhatKit.
    """
    raw_phone = _customer_phone(loan)
    norm_phone = normalize_phone_number(raw_phone)
    use_tamil = _detect_tamil(loan, lang)
    msg = build_demand_notice_whatsapp(loan, request_user=request_user, use_tamil=use_tamil)
    link = get_whatsapp_link(norm_phone, msg) if norm_phone else ''

    pywhatkit_started = False
    if send_pywhatkit and norm_phone:
        pywhatkit_started = send_pywhatkit_async(norm_phone, msg)

    return {
        'success': bool(norm_phone),
        'phone': norm_phone or raw_phone,
        'link': link,
        'message': msg,
        'pywhatkit_started': pywhatkit_started,
        'use_tamil': use_tamil,
    }
