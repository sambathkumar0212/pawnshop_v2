"""
transactions/services_email.py
Email notification helpers for the Pawnshop Management System.
Supports bilingual (English / Tamil) email output.
"""

import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@myapp.com')


def _get_branch_phone(branch):
    if not branch:
        return ''
    try:
        from transactions.views import get_branch_bill_header_phones
        return get_branch_bill_header_phones(branch)
    except Exception:
        return getattr(branch, 'phone', '') or ''


def _get_branch_address(branch):
    if not branch:
        return ''
    try:
        parts = []
        for attr in ('address', 'city', 'state', 'pincode'):
            val = getattr(branch, attr, None)
            if val:
                parts.append(str(val).strip())
        return ', '.join(p for p in parts if p)
    except Exception:
        return ''


def _get_total_payable(loan):
    """Returns (total_due, interest_due) in Decimal."""
    try:
        from transactions.services_partial_release import get_loan_current_interest_due
        interest_due = get_loan_current_interest_due(loan)
    except Exception:
        interest_due = Decimal('0.00')
    principal = Decimal(str(getattr(loan, 'principal_amount', 0) or 0))
    return principal + interest_due, interest_due


def _customer_email(loan):
    try:
        email = getattr(loan.customer, 'email', None)
        return email if email and '@' in str(email) else None
    except Exception:
        return None


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


def _customer_address(loan):
    try:
        c = loan.customer
        parts = []
        for attr in ('address', 'city', 'state', 'zip_code'):
            val = getattr(c, attr, None)
            if val:
                parts.append(str(val).strip())
        return ', '.join(p for p in parts if p)
    except Exception:
        return ''


def _detect_tamil(loan, lang=None):
    """
    Detect whether to send in Tamil.
    Priority:
    1. Explicit lang parameter ('ta' or 'en')
    2. Active Django translation language in thread (e.g. from user session)
    3. Customer profile has Tamil name/address data filled
    """
    if lang is not None:
        return str(lang).lower().startswith('ta')
    try:
        from django.utils.translation import get_language
        curr_lang = get_language()
        if curr_lang and str(curr_lang).lower().startswith('ta'):
            return True
    except Exception:
        pass
    try:
        c = loan.customer
        # If the customer has any Tamil field filled, use Tamil
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


# ---------------------------------------------------------------------------
# Tamil string helpers (static translations for email labels/subjects)
# ---------------------------------------------------------------------------

TAMIL = {
    # Payment receipt
    'payment_subject':   'தங்கக் கடன் கட்டணம் உறுதிப்படுத்தல் - #{loan_number}',
    'payment_dear':      'அன்புள்ள {name},',
    'payment_body':      'தங்கக் கடன் #{loan_number} -க்கு ₹{amount} கட்டணம் {date} அன்று வெற்றிகரமாக பெறப்பட்டது. நன்றி.',
    # Reminder
    'reminder_subject_upcoming':  'நினைவூட்டல்: தங்கக் கடன் #{loan_number} - நிலுவை தேதி {due_date}',
    'reminder_subject_overdue':   'அவசர அறிவிப்பு: தங்கக் கடன் #{loan_number} - {days} நாட்கள் கடன் தாமதமானது',
    'reminder_dear':     'அன்புள்ள {name},',
    'reminder_body_upcoming': (
        'உங்கள் தங்கக் கடன் #{loan_number} நிலுவை தேதி {due_date} ஆகும். '
        'இன்றைய மொத்த செலுத்த வேண்டிய தொகை: ₹{total_due}. '
        'தயவுசெய்து உங்கள் கிளையை தொடர்பு கொண்டு கடனை முடிக்கவும்.'
    ),
    'reminder_body_overdue': (
        'உங்கள் தங்கக் கடன் #{loan_number} நிலுவை தேதி {due_date} கடந்து {days} நாட்கள் ஆகிவிட்டன. '
        'இன்றைய மொத்த செலுத்த வேண்டிய தொகை: ₹{total_due}. '
        'உடனடியாக தீர்க்கவும் இல்லையேல் தங்க நகைகள் ஏலம் விடப்படும்.'
    ),
    # Demand notice
    'demand_subject':    'கட்டாய அறிவிப்பு - தங்கக் கடன் #{loan_number} | ஏலத்தை தவிர்க்க உடனடியாக செலுத்தவும்',
    'demand_dear':       '{name} அவர்களுக்கு,',
    'demand_body': (
        'தங்கக் கடன் எண் #{loan_number} நிலுவை தேதி {due_date} கடந்துவிட்டது. '
        'மொத்த நிலுவை: ₹{total_due}. '
        'உடனடியாக செலுத்தவில்லையென்றால் அடமானம் வைத்த தங்க நகைகள் ஏலம் விடப்படும். '
        'உடனடியாக கிளையை தொடர்பு கொள்ளவும்.'
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_customer_payment_email(payment, lang=None):
    """Send a payment-receipt confirmation email to the borrower."""
    try:
        loan = payment.loan
        email = _customer_email(loan)
        if not email:
            return

        use_tamil = _detect_tamil(loan, lang)
        branch = getattr(loan, 'branch', None)
        total_due, interest_due = _get_total_payable(loan)
        customer_name = _customer_name(loan)

        context = {
            'loan': loan,
            'payment': payment,
            'customer_name': customer_name,
            'customer_address': _customer_address(loan),
            'branch_name': getattr(branch, 'name', '') if branch else '',
            'branch_phone': _get_branch_phone(branch),
            'branch_address': _get_branch_address(branch),
            'organization_name': getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold'),
            'interest_due': interest_due,
            'total_due': total_due,
            'use_tamil': use_tamil,
            'today': timezone.now().date(),
        }

        payment_date_str = payment.payment_date.strftime('%d/%m/%Y') if hasattr(payment.payment_date, 'strftime') else str(payment.payment_date)
        if use_tamil:
            subject = TAMIL['payment_subject'].format(loan_number=loan.loan_number)
            text_body = (
                TAMIL['payment_dear'].format(name=customer_name) + '\n\n' +
                TAMIL['payment_body'].format(
                    loan_number=loan.loan_number,
                    amount=f"{payment.amount:,.2f}",
                    date=payment_date_str
                ) + f'\n\n{context["branch_name"] or context["organization_name"]}'
            )
        else:
            subject = f"Payment Confirmed - Gold Loan #{loan.loan_number}"
            text_body = (
                f"Dear {customer_name},\n\n"
                f"We have received your payment of Rs.{payment.amount:,.2f} "
                f"against Gold Loan #{loan.loan_number} on {payment_date_str}.\n\n"
                f"Thank you for your prompt payment.\n\n"
                f"Regards,\n{context['branch_name'] or context['organization_name']}"
            )

        html_body = render_to_string(
            'transactions/emails/payment_receipt_customer_email.html', context
        )
        msg = EmailMultiAlternatives(subject=subject, body=text_body,
                                     from_email=_from_email(), to=[email])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=True)
        logger.info("Payment receipt email sent for loan %s to %s (tamil=%s)", loan.loan_number, email, use_tamil)

    except Exception as exc:
        logger.warning("send_customer_payment_email failed: %s", exc)


def send_due_date_reminder_email(loan, days_left=None, lang=None):
    """Send a due-date reminder OR overdue notice email to the borrower."""
    try:
        email = _customer_email(loan)
        if not email:
            return

        use_tamil = _detect_tamil(loan, lang)
        branch = getattr(loan, 'branch', None)
        total_due, interest_due = _get_total_payable(loan)
        customer_name = _customer_name(loan)

        computed_days, is_overdue = _compute_days_left(loan)
        if days_left is None:
            days_left = computed_days
        is_overdue = days_left is not None and days_left < 0
        overdue_days = abs(days_left) if is_overdue else 0

        context = {
            'loan': loan,
            'customer_name': customer_name,
            'customer_address': _customer_address(loan),
            'branch_name': getattr(branch, 'name', '') if branch else '',
            'branch_phone': _get_branch_phone(branch),
            'branch_address': _get_branch_address(branch),
            'organization_name': getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold'),
            'days_left': days_left,
            'is_overdue': is_overdue,
            'overdue_days': overdue_days,
            'interest_due': interest_due,
            'total_due': total_due,
            'use_tamil': use_tamil,
            'today': timezone.now().date(),
        }

        due_date_str = loan.due_date.strftime('%d/%m/%Y') if loan.due_date else ''
        if use_tamil:
            if is_overdue:
                subject = TAMIL['reminder_subject_overdue'].format(
                    loan_number=loan.loan_number, days=overdue_days
                )
                text_body = (
                    TAMIL['reminder_dear'].format(name=customer_name) + '\n\n' +
                    TAMIL['reminder_body_overdue'].format(
                        loan_number=loan.loan_number,
                        due_date=due_date_str,
                        days=overdue_days,
                        total_due=f"{total_due:,.2f}"
                    ) + f'\n\n{context["branch_name"] or context["organization_name"]}'
                )
            else:
                subject = TAMIL['reminder_subject_upcoming'].format(
                    loan_number=loan.loan_number, due_date=due_date_str
                )
                text_body = (
                    TAMIL['reminder_dear'].format(name=customer_name) + '\n\n' +
                    TAMIL['reminder_body_upcoming'].format(
                        loan_number=loan.loan_number,
                        due_date=due_date_str,
                        total_due=f"{total_due:,.2f}"
                    ) + f'\n\n{context["branch_name"] or context["organization_name"]}'
                )
        else:
            if is_overdue:
                subject = (
                    f"OVERDUE NOTICE: Gold Loan #{loan.loan_number} - "
                    f"Payment {overdue_days} day{'s' if overdue_days != 1 else ''} overdue"
                )
            else:
                subject = f"Reminder: Gold Loan #{loan.loan_number} due on {due_date_str}"
            text_body = (
                f"Dear {customer_name},\n\n"
                + (
                    f"OVERDUE: Your Gold Loan #{loan.loan_number} was due on {due_date_str} "
                    f"and is now {overdue_days} day(s) overdue.\n\n"
                    if is_overdue else
                    f"Your Gold Loan #{loan.loan_number} is due on {due_date_str}.\n\n"
                ) +
                f"Today's Net Payable: Rs.{total_due:,.2f}\n"
                f"Principal: Rs.{loan.principal_amount:,.2f} | Interest: Rs.{interest_due:,.2f}\n\n"
                f"Please visit your branch immediately.\n\n"
                f"Regards,\n{context['branch_name'] or context['organization_name']}"
            )

        html_body = render_to_string(
            'transactions/emails/loan_due_date_reminder_email.html', context
        )
        msg = EmailMultiAlternatives(subject=subject, body=text_body,
                                     from_email=_from_email(), to=[email])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=True)
        logger.info("Reminder email sent for loan %s to %s (tamil=%s, overdue=%s)", loan.loan_number, email, use_tamil, is_overdue)

    except Exception as exc:
        logger.warning("send_due_date_reminder_email failed for loan %s: %s", getattr(loan, 'loan_number', '?'), exc)


def send_loan_expiry_notice_email(loan, request_user=None, lang=None):
    """
    Send a formal Expiry / Demand Notice email to the borrower.
    Returns True if sent successfully, False otherwise.
    """
    try:
        email = _customer_email(loan)
        if not email:
            logger.warning("send_loan_expiry_notice_email: loan %s customer has no email.", getattr(loan, 'loan_number', '?'))
            return False

        use_tamil = _detect_tamil(loan, lang)
        branch = getattr(loan, 'branch', None)
        total_due, interest_due = _get_total_payable(loan)
        days_left, is_overdue = _compute_days_left(loan)
        overdue_days = abs(days_left) if (days_left is not None and days_left < 0) else 0
        customer_name = _customer_name(loan)

        try:
            items = list(loan.loanitem_set.select_related('item').all())
        except Exception:
            items = []

        context = {
            'loan': loan,
            'customer_name': customer_name,
            'customer_address': _customer_address(loan),
            'branch_name': getattr(branch, 'name', '') if branch else '',
            'branch_phone': _get_branch_phone(branch),
            'branch_address': _get_branch_address(branch),
            'organization_name': getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold'),
            'interest_due': interest_due,
            'total_due': total_due,
            'overdue_days': overdue_days,
            'is_overdue': is_overdue,
            'items': items,
            'use_tamil': use_tamil,
            'today': timezone.now().date(),
            'issued_by': (
                getattr(request_user, 'get_full_name', lambda: '')()
                or getattr(request_user, 'username', '')
            ) if request_user else '',
        }

        due_date_str = loan.due_date.strftime('%d/%m/%Y') if loan.due_date else ''
        if use_tamil:
            subject = TAMIL['demand_subject'].format(loan_number=loan.loan_number)
            text_body = (
                TAMIL['demand_dear'].format(name=customer_name) + '\n\n' +
                TAMIL['demand_body'].format(
                    loan_number=loan.loan_number,
                    due_date=due_date_str,
                    total_due=f"{total_due:,.2f}"
                ) + f'\n\n{context["branch_name"] or context["organization_name"]}'
            )
        else:
            subject = f"DEMAND NOTICE - Gold Loan #{loan.loan_number} | Settle Dues to Avoid Auction"
            text_body = (
                f"EXPIRY / DEMAND NOTICE\n\nTo: {customer_name}\n"
                f"Loan Number: {loan.loan_number}\nDue Date: {due_date_str}\n\n"
                f"Your Gold Loan has exceeded the redemption period. "
                f"Principal: Rs.{loan.principal_amount:,.2f}. "
                f"Interest Due: Rs.{interest_due:,.2f}. "
                f"Total Payable Today: Rs.{total_due:,.2f}.\n\n"
                f"Pledged gold ornaments will be auctioned if dues are not settled immediately.\n\n"
                f"Regards,\n{context['branch_name'] or context['organization_name']}"
            )

        html_body = render_to_string('transactions/emails/loan_demand_notice_email.html', context)
        msg = EmailMultiAlternatives(subject=subject, body=text_body,
                                     from_email=_from_email(), to=[email])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)

        logger.info("Demand notice email sent for loan %s to %s (tamil=%s, by %s)",
                    loan.loan_number, email, use_tamil, context['issued_by'] or 'system')
        return True

    except Exception as exc:
        logger.warning("send_loan_expiry_notice_email failed for loan %s: %s", getattr(loan, 'loan_number', '?'), exc)
        return False
