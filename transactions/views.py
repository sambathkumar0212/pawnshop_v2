from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.http import Http404, HttpResponse, JsonResponse
from django.template.loader import get_template
from io import BytesIO
import csv
from .models import Loan, Payment, LoanExtension, Sale, DisbursementTransaction, LoanItem
from accounts.mixins import RoleBranchAccessMixin
from .forms import LoanForm, SaleForm, LoanExtensionForm, PaymentRecordForm
from .utils import ManagerPermissionMixin
from django.db.models import Q
from num2words import num2words
from django.core.files.base import ContentFile
from decimal import Decimal
import logging
import base64
import json
import ast
import os
import shutil
import subprocess
import tempfile
import re
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError
from urllib.parse import urlparse
from utils.download_utils import DownloadMixin
from utils.translation import translate_text

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    pdfmetrics = None
    TTFont = None


import functools

# ---------------------------------------------------------------------------
# Translation cache — avoids repeated HTTP calls to Google for the same
# labels (e.g. "Customer Name", "Date", "Branch") that appear on every bill.
# LRU cache keeps up to 512 unique (text, lang) pairs in memory.
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=512)
def _cached_google_translate(text, target_lang, timeout=5):
    """Internal cached wrapper for the Google Translate free endpoint."""
    try:
        import requests as _requests
        response = _requests.get(
            'https://translate.googleapis.com/translate_a/single',
            params={
                'client': 'gtx',
                'sl': 'en',
                'tl': target_lang,
                'dt': 't',
                'q': text,
            },
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json,text/plain,*/*',
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = json.loads(response.content.decode('utf-8', errors='replace'))
        translated = ''.join(part[0] for part in payload[0] if part and part[0]).strip()
        if translated and translated.replace('?', '').strip():
            return translated
    except Exception:
        pass
    return None


def translate_text_for_pdf(text, target_lang='ta', timeout=5):
    """Translate a short piece of text for PDF output with timeout and fallback.

    Results are cached in-memory (LRU) so each unique string is only
    translated once per server process — no repeated network round-trips.
    """
    if not text:
        return ''

    if target_lang == 'en':
        return text

    # Try cached Google Translate first
    result = _cached_google_translate(text, target_lang, timeout)
    if result:
        return result

    # Fallback to configured provider (Google Cloud / Azure via API key)
    try:
        translated = translate_text(text, target_lang=target_lang)
        if translated:
            return translated
    except Exception:
        pass

    return text



def format_mobile_number(value):
    """Format to '85758 69850' from phone-like input."""
    digits = re.sub(r'\D', '', str(value or ''))
    if len(digits) >= 10:
        digits = digits[-10:]
    return f"{digits[:5]} {digits[5:]}" if len(digits) == 10 else digits


def get_branch_bill_header_phones(branch):
    """Return formatted bill-header phone numbers from branch settings or fallback phone."""
    if not branch:
        return ''

    try:
        settings_obj = getattr(branch, 'settings', None)
    except (OperationalError, ProgrammingError):
        settings_obj = None
    raw_numbers = getattr(settings_obj, 'bill_header_mobile_numbers', '') if settings_obj else ''

    def _extract_numbers(text):
        extracted = []
        if not text:
            return extracted
        normalized = str(text).replace('\n', ',').replace('/', ',').replace('|', ',').replace(';', ',')
        for part in normalized.split(','):
            chunk = part.strip()
            if not chunk:
                continue
            digits = ''.join(ch for ch in chunk if ch.isdigit())
            if len(digits) >= 10:
                # Support pasted groups: pick each 10-digit slice from right.
                while len(digits) >= 10:
                    extracted.append(format_mobile_number(digits[-10:]))
                    digits = digits[:-10]
        return list(dict.fromkeys(extracted))

    numbers = _extract_numbers(raw_numbers)

    if numbers:
        return ', '.join(numbers)

    fallback_numbers = _extract_numbers(getattr(branch, 'phone', ''))
    if fallback_numbers:
        return ', '.join(fallback_numbers)
    return ''


def get_branch_bill_details(branch):
    """Return branch-wise bill header details with custom override support."""
    if not branch:
        return {
            'shop_name': 'Pawnshop Management System',
            'address': '',
            'phone': '',
            'email': '',
            'logo_url': '',
            'color_customer_name': '#000000',
            'color_issue_date': '#8B0000',
            'color_due_date': '#CC0000',
            'color_terms': '#111111',
            'color_items': '#000000',
            'color_header_title': '#002f6c',
            'color_header_subtitle': '#003f91',
            'color_header_text': '#444444',
            'color_field_label': '#333333',
            'color_field_value': '#000000',
            'color_table_header': '#222222',
        }

    default_address_parts = [branch.address, branch.city, branch.state, branch.zip_code]
    default_address = ', '.join([p for p in default_address_parts if p])

    details = {
        'shop_name': branch.name or 'Pawnshop Management System',
        'address': default_address,
        'phone': get_branch_bill_header_phones(branch),
        'email': branch.email or '',
        'logo_url': '',
        'color_customer_name': '#000000',
        'color_issue_date': '#8B0000',
        'color_due_date': '#CC0000',
        'color_terms': '#111111',
        'color_items': '#000000',
        'color_header_title': '#002f6c',
        'color_header_subtitle': '#003f91',
        'color_header_text': '#444444',
        'color_field_label': '#333333',
        'color_field_value': '#000000',
        'color_table_header': '#222222',
    }

    try:
        settings_obj = getattr(branch, 'settings', None)
    except (OperationalError, ProgrammingError):
        settings_obj = None

    if not settings_obj or not getattr(settings_obj, 'use_custom_bill_details', False):
        return details

    custom_shop_name = (getattr(settings_obj, 'bill_shop_name', '') or '').strip()
    custom_address = (getattr(settings_obj, 'bill_address', '') or '').strip()
    custom_email = (getattr(settings_obj, 'bill_email', '') or '').strip()
    custom_phone = (getattr(settings_obj, 'bill_header_mobile_numbers', '') or '').strip()

    if custom_shop_name:
        details['shop_name'] = custom_shop_name
    if custom_address:
        details['address'] = custom_address
    if custom_email:
        details['email'] = custom_email
    if custom_phone:
        numbers = []
        for part in custom_phone.replace('\n', ',').split(','):
            cleaned = part.strip()
            if cleaned:
                numbers.append(format_mobile_number(cleaned))
        if numbers:
            details['phone'] = ', '.join(numbers)

    logo = getattr(settings_obj, 'bill_logo', None)
    if logo:
        try:
            details['logo_url'] = logo.url
        except Exception:
            details['logo_url'] = ''

    details['color_customer_name'] = (getattr(settings_obj, 'bill_color_customer_name', '') or details['color_customer_name']).strip()
    details['color_issue_date'] = (getattr(settings_obj, 'bill_color_issue_date', '') or details['color_issue_date']).strip()
    details['color_due_date'] = (getattr(settings_obj, 'bill_color_due_date', '') or details['color_due_date']).strip()
    details['color_terms'] = (getattr(settings_obj, 'bill_color_terms', '') or details['color_terms']).strip()
    details['color_items'] = (getattr(settings_obj, 'bill_color_items', '') or details['color_items']).strip()
    details['color_header_title'] = (getattr(settings_obj, 'bill_color_header_title', '') or details['color_header_title']).strip()
    details['color_header_subtitle'] = (getattr(settings_obj, 'bill_color_header_subtitle', '') or details['color_header_subtitle']).strip()
    details['color_header_text'] = (getattr(settings_obj, 'bill_color_header_text', '') or details['color_header_text']).strip()
    details['color_field_label'] = (getattr(settings_obj, 'bill_color_field_label', '') or details['color_field_label']).strip()
    details['color_field_value'] = (getattr(settings_obj, 'bill_color_field_value', '') or details['color_field_value']).strip()
    details['color_table_header'] = (getattr(settings_obj, 'bill_color_table_header', '') or details['color_table_header']).strip()

    return details


def get_loan_tiered_rates(loan, use_tamil=False):
    """Fetch loan's tiered scheme rates dynamically for table display."""
    tiered_rates = []
    if not loan:
        return tiered_rates
    s = getattr(loan, 'scheme', None)
    if s and s.interest_rate_structure:
        sorted_keys = sorted(s.interest_rate_structure.keys(), key=lambda k: [int(x) if x.isdigit() else 999999 for x in k.replace('+', '').split('-') if x])
        for range_key in sorted_keys:
            rate = s.interest_rate_structure[range_key]
            # Use 'days' suffix if days-based scheme (e.g., 0-30days)
            if use_tamil:
                suffix = 'நாட்கள்' if s.is_days_based else 'மாதங்கள்'
            else:
                suffix = 'days' if s.is_days_based else 'months'
            range_display = f"{range_key}{suffix}"
            try:
                original_dist = loan.principal_amount - Decimal(str(loan.processing_fee or 0))
                monthly_rate = (Decimal(str(rate)) / Decimal('12')).quantize(Decimal('0.01'))
                interest_amount = (original_dist * monthly_rate / Decimal('100')).quantize(Decimal('0.01'))
                
                # Format rate in Rupees (e.g. 1 Rupee, 1.50 Rupees, 3 Rupees)
                if monthly_rate == monthly_rate.to_integral_value():
                    rate_num = str(int(monthly_rate))
                else:
                    rate_num = f"{monthly_rate:.2f}"

                if use_tamil:
                    rate_val = f"{rate_num} ரூபாய்"
                else:
                    unit = "Rupee" if rate_num == "1" else "Rupees"
                    rate_val = f"{rate_num} {unit}"

                amount_val = f"Rs {round(interest_amount):,}"
            except Exception:
                rate_val = f"{rate} Rupees" if not use_tamil else f"{rate} ரூபாய்"
                amount_val = ""
            
            tiered_rates.append({
                'range': range_display,
                'rate': rate_val,
                'amount': amount_val
            })
    return tiered_rates


def build_loan_pdf_language_context(loan, current_language):
    use_tamil = str(current_language).startswith('ta')
    customer = loan.customer
    loan_items = list(loan.loanitem_set.exclude(status='released').select_related('item'))
    branch = loan.branch

    customer_name_en = customer.full_name if customer else ''
    customer_name_ta = customer_name_en
    if customer and use_tamil:
        tamil_name_parts = [
            (customer.first_name_tamil or '').strip(),
            (customer.last_name_tamil or '').strip(),
        ]
        customer_name_ta = ' '.join([part for part in tamil_name_parts if part]).strip()

    customer_address_parts = []
    if customer:
        if customer.address:
            customer_address_parts.append(customer.address)
        if customer.city:
            customer_address_parts.append(customer.city)
        if customer.state:
            customer_address_parts.append(customer.state)
        if customer.zip_code:
            customer_address_parts.append(customer.zip_code)
    customer_address_en = ', '.join([part for part in customer_address_parts if part])
    customer_address_ta = customer_address_en
    if customer and use_tamil:
        tamil_address_parts = []
        if customer.address_tamil:
            tamil_address_parts.append(customer.address_tamil)
        if customer.city_tamil:
            tamil_address_parts.append(customer.city_tamil)
        if customer.state_tamil:
            tamil_address_parts.append(customer.state_tamil)
        if customer.zip_code:
            tamil_address_parts.append(customer.zip_code)
        customer_address_ta = ', '.join([part for part in tamil_address_parts if part])

    customer_id_label_en = customer.get_id_type_display() if customer and customer.id_type else ''
    customer_id_label_ta = customer_id_label_en

    branch_address_parts = []
    if branch:
        if branch.address:
            branch_address_parts.append(branch.address)
        if branch.city:
            branch_address_parts.append(branch.city)
        if branch.state:
            branch_address_parts.append(branch.state)
        if branch.zip_code:
            branch_address_parts.append(branch.zip_code)
    branch_address_en = ', '.join([part for part in branch_address_parts if part])
    branch_address_ta = branch_address_en
    customer_phone_display = format_mobile_number(customer.phone) if customer and getattr(customer, 'phone', None) else ''
    branch_phone_display = get_branch_bill_header_phones(branch)
    bill_details = get_branch_bill_details(branch)

    localized_items = []
    for loan_item in loan_items:
        item = loan_item.item
        name_en = item.name if item else ''
        description_en = item.description if item else ''
        name_ta = (item.tamil_name if item and getattr(item, 'tamil_name', '') else '') if use_tamil else ''
        description_ta = (item.tamil_description if item and getattr(item, 'tamil_description', '') else '') if use_tamil else ''

        localized_items.append({
            'loan_item': loan_item,
            'display_name': name_ta if use_tamil else name_en,
            'display_description': description_ta if use_tamil else description_en,
        })

    label_keys = {
        'document_title': 'Gold Loan Agreement',
        'borrower_name': 'Borrower Name',
        'loan_number': 'Loan Number',
        'email': 'Email',
        'phone': 'Phone Number',
        'address': 'Address',
        'id_details': 'ID Details',
        'not_provided': 'Not provided',
        'borrower_photo': 'Borrower Photo',
        'principal_amount': 'Principal Amount',
        'processing_fee': 'Processing Fee',
        'distribution_amount': 'Distribution Amount',
        'monthly_interest': 'Monthly Interest',
        'issue_date': 'Loan Date',
        'due_date': 'Due Date',
        'minimum_term': 'Minimum Term',
        'minimum_date': 'Minimum Date',
        'gold_items_details': 'Gold Items Details',
        'item_description': 'Item Description',
        'gold_karat': 'Gold Karat',
        'gross_weight': 'Gross Weight(g)',
        'net_weight': 'Net Weight(g)',
        'qty': 'Qty',
        'total': 'Total',
        'total_items': 'Total Items',
        'pledged_gold_item_photos': 'Pledged Gold Item Photos',
        'item': 'Item',
        'no_photos': 'No photos available for this loan.',
        'borrower_signature': 'Borrower Signature',
        'authorized_signatory': 'Authorized Signatory',
        'branch_manager': 'Branch Manager',
        'phone_label': 'Phone',
        'email_label': 'Email',
        'document_generated_on': 'Document generated on',
        'terms_and_conditions': 'TERMS AND CONDITIONS',
        'first_month_interest_paid': 'First Month Interest Paid (Upfront)',
        'processing_fee_paid': 'Processing Fees Paid (Upfront)',
    }

    if use_tamil:
        labels = {
            'document_title': 'தங்கக் கடன் ஒப்பந்தம்',
            'borrower_name': 'கடன் வாங்கியவர் பெயர்',
            'loan_number': 'கடன் எண்',
            'email': 'மின்னஞ்சல்',
            'phone': 'தொலைபேசி எண்',
            'address': 'முகவரி',
            'id_details': 'அடையாள விவரங்கள்',
            'not_provided': 'வழங்கப்படவில்லை',
            'borrower_photo': 'கடன் வாங்கியவர் புகைப்படம்',
            'principal_amount': 'முதன்மை தொகை',
            'processing_fee': 'செயலாக்கக் கட்டணம்',
            'distribution_amount': 'வழங்கப்பட்ட தொகை',
            'monthly_interest': 'மாத வட்டி',
            'issue_date': 'வழங்கிய தேதி',
            'due_date': 'கடைசி தேதி',
            'minimum_term': 'குறைந்தபட்ச காலம்',
            'minimum_date': 'குறைந்தபட்ச தேதி',
            'gold_items_details': 'தங்கப் பொருட்கள் விவரம்',
            'item_description': 'பொருள் விவரம்',
            'gold_karat': 'தங்க சுத்தம்',
            'gross_weight': 'மொத்த எடை (கி)',
            'net_weight': 'நிகர எடை (கி)',
            'qty': 'அளவு',
            'total': 'மொத்தம்',
            'total_items': 'மொத்த பொருட்கள்',
            'pledged_gold_item_photos': 'அடமான பொருள் புகைப்படங்கள்',
            'item': 'பொருள்',
            'no_photos': 'இந்தக் கடனுக்கான படங்கள் எதுவுமில்லை.',
            'borrower_signature': 'கடன் வாங்கியவர் கையொப்பம்',
            'authorized_signatory': 'அங்கீகரிக்கப்பட்ட கையொப்பம்',
            'branch_manager': 'கிளை மேலாளர்',
            'phone_label': 'தொலைபேசி',
            'email_label': 'மின்னஞ்சல்',
            'document_generated_on': 'ஆவணம் உருவாக்கப்பட்ட தேதி',
            'terms_and_conditions': 'விதிமுறைகள் மற்றும் நிபந்தனைகள்',
            'first_month_interest_paid': 'முதல் மாத வட்டி செலுத்தப்பட்டது (முன்கூட்டியே)',
            'processing_fee_paid': 'செயலாக்கக் கட்டணம் செலுத்தப்பட்டது (முன்கூட்டியே)',
        }
    else:
        labels = label_keys

    scheme_name = loan.scheme.name if loan.scheme else 'Standard Gold Loan'
    scheme_interest = loan.scheme.interest_rate if loan.scheme else loan.interest_rate
    scheme_duration = loan.scheme.loan_duration if loan.scheme and loan.scheme.loan_duration else 0
    minimum_term = loan.scheme.minimum_duration if loan.scheme and loan.scheme.minimum_duration else 0
    display_scheme_name = scheme_name
    due_date = loan.due_date.strftime('%d-%m-%Y')

    base_terms = [
        {
            'title': '1. Loan Scheme Details:',
            'content': f'This loan is issued under the "{scheme_name}" scheme. Interest rate: {scheme_interest}% per annum for {scheme_duration} days duration.'
        },
        {
            'title': '2. Purpose of Loan:',
            'content': 'The loan is granted solely on the security of gold ornaments/items deposited as collateral with the lender. The borrower affirms that the pledged article is their own property and is not stolen or encumbered.'
        },
        {
            'title': '3. Gold Recovery Timing:',
            'content': 'For gold recovery, payment must be made before 11:00 AM and gold collection will be available after 4:00 PM on the same day.'
        },
        {
            'title': '4. KYC Compliance:',
            'content': 'The borrower has provided necessary KYC documents as required under RBI guidelines, including proof of identity and address.'
        },
        {
            'title': '5. Fair Practices Code:',
            'content': "Loss or damage to the pledged article due to natural calamities, theft, or circumstances beyond the lender's control will not be the responsibility of the lender."
        },
        {
            'title': '6. Repayment and Recovery:',
            'content': f'The loan is repayable (principal and total interest) before the due date "{due_date}". If not repaid, the lender may sell the pledged gold within 5 days loan due date "{due_date}". I sincerely aggree for this without any opposition'
        },
        {
            'title': '7. Receipt Requirement:',
            'content': 'No release of pledged gold items will be processed without verification of the original loan document and submitted ID proof.'
        },
        {
            'title': '8. Declaration:',
            'content': 'The borrower declares that all information provided is true and that they have read and understood all the terms and conditions mentioned herein.'
        },
    ]

    if use_tamil:
        terms = [
            {'title': '1. கடன் திட்ட விவரங்கள்:', 'content': f'இந்தக் கடன் "{display_scheme_name}" திட்டத்தின் கீழ் வழங்கப்படுகிறது. வட்டி விகிதம்: வருடத்திற்கு {scheme_interest}% மற்றும் காலம் {scheme_duration} நாட்கள்.'},
            {'title': '2. கடனின் நோக்கம்:', 'content': 'கடன் வழங்குநரிடம் பிணையமாக வைக்கப்பட்ட தங்க நகைகள்/பொருட்களின் பாதுகாப்பின் பேரில் மட்டுமே இந்தக் கடன் வழங்கப்படுகிறது. அடமானம் வைக்கப்பட்ட பொருள் தங்களுடைய சொந்தச் சொத்து என்றும், அது திருடப்பட்டதோ அல்லது போலி  நகை அல்ல என்றும் கடன் வாங்குபவர் உறுதிப்படுத்துகிறார்.'},
            {'title': '3. தங்கம் மீட்பு நேரம்:', 'content': 'தங்கத்தை மீட்க, காலை 11:00 மணிக்கு முன் பணம் செலுத்தப்பட வேண்டும், மேலும் அதே நாளில் மாலை 4:00 மணிக்கு மேல் தங்கம் பெற்றுக்கொள்ளலாம்.'},
            {'title': '4. KYC இணக்கம்:', 'content': 'RBI வழிகாட்டுதலின்படி KYC விவரங்கள் சரிபார்க்கப்பட்டுள்ளன.'},
            {'title': '5. திருப்பிச் செலுத்தல்:', 'content': f'கடனை (அசல் & வட்டி) கடைசி தேதிக்கு முன்பாகத் திருப்பிச் செலுத்தப்படாவிட்டால், செலுத்த வேண்டிய தேதி  "{due_date}" யிலிருந்து 5 நாட்களுக்குள் அடமான தங்கத்தை விற்பதன் மூலம் கடன் தொகையை கடன் கொடுத்தவர் வசூலிப்பார். நான் இதற்கு எந்தவித எதிர்ப்புமின்றி மனப்பூர்வமாக ஒப்புக்கொள்கிறேன்.'},
            {'title': '6. ரசீது அவசியம்:', 'content': 'அசல் கடன் ஆவணங்களைச் சரிபார்த்த பின்பே அடமானம் பொருட்கள் தரப்படும். ஒவ்வொரு கட்டணத்திற்கும் ரசீது வழங்கப்படும்.'},
            {'title': '7. அறிவிப்பு:', 'content': 'மேலே உள்ள தகவல்கள் அனைத்தும் உண்மையானவை என உறுதிசெய்து, விதிமுறைகளைப் படித்துப் புரிந்துகொண்டு கீழே கையொப்பமிடுகிறேன்.'},
        ]
    else:
        terms = base_terms

    unique_item_names_count = len({
        (loan_item.item.name if loan_item.item and loan_item.item.name else '').strip().lower()
        for loan_item in loan_items
        if loan_item.item and loan_item.item.name
    })

    total_items_count = sum(
        int(getattr(loan_item, 'quantity', 1) or 1)
        for loan_item in loan_items
    ) if loan_items else 0
    if total_items_count <= 0:
        total_items_count = unique_item_names_count

    # Calculate minimum date (issue_date + minimum_duration days)
    minimum_date = None
    if minimum_term and minimum_term > 0:
        from datetime import timedelta
        minimum_date = loan.issue_date + timedelta(days=minimum_term)

    # Fetch current loan's tiered scheme rates dynamically for table display
    tiered_rates = get_loan_tiered_rates(loan, use_tamil=use_tamil)

    total_gross_weight = sum(
        Decimal(str(loan_item.gross_weight or 0))
        for loan_item in loan_items
    ) if loan_items else Decimal('0.000')

    total_net_weight = sum(
        Decimal(str(loan_item.net_weight or 0))
        for loan_item in loan_items
    ) if loan_items else Decimal('0.000')

    return {
        'current_language': current_language,
        'labels': labels,
        'localized_items': localized_items,
        'unique_item_names_count': unique_item_names_count,
        'total_items_count': total_items_count,
        'total_gross_weight': total_gross_weight,
        'total_net_weight': total_net_weight,
        'customer_name_display': customer_name_en,
        'customer_phone_display': customer_phone_display,
        'customer_address_display': customer_address_ta if use_tamil else customer_address_en,
        'customer_id_type_display': customer_id_label_ta if use_tamil else customer_id_label_en,
        'branch_address_display': branch_address_ta if use_tamil else branch_address_en,
        'branch_phone_display': branch_phone_display,
        'bill_shop_name': bill_details.get('shop_name', ''),
        'bill_address_display': bill_details.get('address', ''),
        'bill_phone_display': bill_details.get('phone', ''),
        'bill_email_display': bill_details.get('email', ''),
        'bill_logo_url': bill_details.get('logo_url', ''),
        'bill_color_customer_name': bill_details.get('color_customer_name', '#000000'),
        'bill_color_issue_date': bill_details.get('color_issue_date', '#8B0000'),
        'bill_color_due_date': bill_details.get('color_due_date', '#CC0000'),
        'bill_color_terms': bill_details.get('color_terms', '#111111'),
        'bill_color_items': bill_details.get('color_items', '#000000'),
        'bill_color_header_title': bill_details.get('color_header_title', '#002f6c'),
        'bill_color_header_subtitle': bill_details.get('color_header_subtitle', '#003f91'),
        'bill_color_header_text': bill_details.get('color_header_text', '#444444'),
        'bill_color_field_label': bill_details.get('color_field_label', '#333333'),
        'bill_color_field_value': bill_details.get('color_field_value', '#000000'),
        'bill_color_table_header': bill_details.get('color_table_header', '#222222'),
        'terms_list': terms,
        'minimum_term': minimum_term,
        'minimum_date': minimum_date,
        'tiered_rates': tiered_rates,
    }


def get_loan_total_items_count(loan):
    """Return total item count for a loan, preferring LoanItem.quantity values."""
    if not loan:
        return 0
    loan_items = list(loan.loanitem_set.all())
    total = sum(int(getattr(item, 'quantity', 1) or 1) for item in loan_items) if loan_items else 0
    if total > 0:
        return total
    return len(loan_items)


ORNAMENT_DICT_EN_TO_TA = {
    # Ornaments
    'ring': 'மோதிரம்', 'rings': 'மோதிரங்கள்', 'mothiram': 'மோதிரம்', 'modhiram': 'மோதிரம்', 'mothirangal': 'மோதிரங்கள்',
    'chain': 'சங்கிலி', 'chains': 'சங்கிலிகள்', 'sangili': 'சங்கிலி', 'sangilikal': 'சங்கிலிகள்',
    'bangle': 'வளையல்', 'bangles': 'வளையல்கள்', 'valaiyal': 'வளையல்', 'valaiyalkal': 'வளையல்கள்', 'kappu': 'காப்பு',
    'necklace': 'நெக்லஸ்', 'necklaces': 'நெக்லஸ்கள்', 'aarum': 'ஹாரம்', 'haram': 'ஹாரம்', 'choker': 'சோக்கர்',
    'stud': 'தோடு', 'studs': 'தோடுகள்', 'thodu': 'தோடு', 'thodukal': 'தோடுகள்',
    'earring': 'கம்மல்', 'earrings': 'கம்மல்கள்', 'kammal': 'கம்மல்', 'kammalkal': 'கம்மல்கள்', 'jimikki': 'ஜிமிக்கி', 'jhumka': 'ஜிமிக்கி', 'mattal': 'மாட்டல்',
    'coin': 'நாணயம்', 'coins': 'நாணயங்கள்', 'gold coin': 'தங்க நாணயம்', 'kasu': 'காசு', 'kasumaalai': 'காசுமாலை',
    'pendant': 'டாலர்', 'pendants': 'டாலர்கள்', 'dollar': 'டாலர்', 'dolar': 'டாலர்', 'locket': 'லாக்கெட்',
    'bracelet': 'காப்பு', 'bracelets': 'காப்புகள்', 'bracelete': 'காப்பு',
    'anklet': 'கொலுசு', 'anklets': 'கொலுசுகள்', 'golusu': 'கொலுசு', 'kolusu': 'கொலுசு', 'kolusukal': 'கொலுசுகள்',
    'waist chain': 'ஒட்டியாணம்', 'ottiyanam': 'ஒட்டியாணம்', 'oddiyanam': 'ஒட்டியாணம்',
    'nose pin': 'மூக்குத்தி', 'mookuthi': 'மூக்குத்தி', 'nattu': 'மூக்குத்தி', 'bullaku': 'புல்லாக்கு',
    'mangalsutra': 'தாலி கொடி', 'thali': 'தாலி', 'thaali': 'தாலி', 'kodi': 'கொடி', 'mugappu': 'முகப்பு',
    'metti': 'மெட்டி', 'minji': 'மிஞ்சி', 'vanki': 'வங்கி',

    # Metals & Materials
    'gold': 'தங்கம்', 'thangam': 'தங்கம்', 'thanga': 'தங்க',
    'silver': 'வெள்ளி', 'velli': 'வெள்ளி',
    'stone': 'கல்', 'stones': 'கற்கள்', 'kal': 'கல்', 'kallu': 'கல்',
    'ruby': 'ரூபி கல்', 'emerald': 'மரகதம்', 'pearl': 'முத்து', 'coral': 'பவளம்',
    'red': 'சிவப்பு', 'white': 'வெள்ளை', 'green': 'பச்சை', 'blue': 'நீல',

    # Description & Conditions
    'lock': 'லாக்', 'hook': 'கொக்கி', 'screw': 'திருகு', 'kdm': 'கே.டி.எம்', 'hallmark': 'ஹால்மார்க்',
    '916': '916', 'seal': 'முத்திரை', 'old': 'பழைய', 'new': 'புதிய', 'antique': 'ஆன்டிக்',
    'fancy': 'ஃபேன்ஸி', 'damage': 'சேதம்', 'damaged': 'சேதமடைந்தது', 'broken': 'உடைந்தது',
    'scratch': 'கீறல்', 'pair': 'ஜோடி', 'single': 'ஒற்றை', 'cut': 'கட்', 'joint': 'ஜாயிண்ட்',
    'with': 'உடன்', 'without': 'இல்லாமல்', 'and': 'மற்றும்', 'piece': 'பீஸ்', 'pieces': 'பீஸ்கள்',
    'plain': 'ப்ளெயின்', 'hollow': 'ஹாலோ', 'casting': 'காஸ்டிங்', 'rope': 'ரோப்',

    # Loan & Scheme Terms
    'scheme': 'திட்டம்', 'loan': 'கடன்', 'gold loan': 'தங்கக் கடன்', 'classic': 'கிளாசிக்',
    'express': 'எக்ஸ்பிரஸ்', 'super': 'சூப்பர்', 'regular': 'ரெகுலர்', 'standard': 'ஸ்டாண்டர்ட்',
    'special': 'ஸ்பெஷல்', 'prime': 'பிரைம்', 'silver scheme': 'வெள்ளித் திட்டம்', 'bullet': 'புல்லட்',
    'monthly': 'மாதாந்திர', 'annual': 'ஆண்டு'
}

ORNAMENT_DICT_TA_TO_EN = {v: k.title() for k, v in ORNAMENT_DICT_EN_TO_TA.items()}


def transliterate_between_english_tamil(request):
    text = (request.GET.get('text') or '').strip()
    direction = request.GET.get('direction', 'to_tamil')

    if not text:
        return JsonResponse({'result': ''})

    clean_lower = text.lower().strip()

    # 1. Fast Dictionary Lookup (Exact match — instant, no network)
    if direction == 'to_tamil':
        if clean_lower in ORNAMENT_DICT_EN_TO_TA:
            return JsonResponse({'result': ORNAMENT_DICT_EN_TO_TA[clean_lower]})
    else:
        if text in ORNAMENT_DICT_TA_TO_EN:
            return JsonResponse({'result': ORNAMENT_DICT_TA_TO_EN[text]})

    # 2. MyMemory Translation API (free, no API key, handles names & sentences)
    try:
        import requests as req

        source_lang = 'ta' if direction == 'to_english' else 'en'
        target_lang = 'en' if direction == 'to_english' else 'ta'
        langpair = f'{source_lang}|{target_lang}'

        response = req.get(
            'https://api.mymemory.translated.net/get',
            params={'q': text, 'langpair': langpair},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            translated = (data.get('responseData') or {}).get('translatedText', '').strip()
            # MyMemory returns 'PLEASE SELECT' or similar on errors
            if translated and translated != text and 'PLEASE' not in translated.upper() and 'SELECT' not in translated.upper():
                return JsonResponse({'result': translated})
    except Exception:
        pass

    # 3. Word-by-word Dictionary + Phonetic Fallback (last resort)
    if direction == 'to_tamil':
        words = text.split()
        translated_parts = []
        for w in words:
            wl = w.lower().strip('.,:;()-[]{}')
            if wl in ORNAMENT_DICT_EN_TO_TA:
                translated_parts.append(ORNAMENT_DICT_EN_TO_TA[wl])
            else:
                translated_parts.append(w)
        return JsonResponse({'result': ' '.join(translated_parts)})

    return JsonResponse({'result': text})



# --- Number to words helpers (English and Tamil) ---
def amount_to_english_words(amount):
    """Convert a numeric amount to English words formatted as 'X Rupees Only'."""
    try:
        dec = Decimal(str(amount))
    except Exception:
        return ''

    rupees = int(dec)
    paise = int(round((dec - Decimal(rupees)) * 100))

    try:
        try:
            words_rupees = num2words(rupees, lang='en_IN').title()
        except Exception:
            words_rupees = num2words(rupees, lang='en').title()

        words = f"{words_rupees} Rupees"
        if paise:
            words_paise = num2words(paise, lang='en').title()
            words += f" and {words_paise} Paise"
        words += " Only"
        return words
    except Exception:
        return f"{rupees:,} Rupees Only"


def _int_to_tamil_under_thousand(n):
    """Convert integer < 1000 to Tamil words."""
    if n <= 0:
        return ''
    
    ones = {
        1: 'ஒன்று', 2: 'இரண்டு', 3: 'மூன்று', 4: 'நான்கு', 5: 'ஐந்து',
        6: 'ஆறு', 7: 'ஏழு', 8: 'எட்டு', 9: 'ஒன்பது', 10: 'பத்து',
        11: 'பதினொன்று', 12: 'பன்னிரண்டு', 13: 'பதின்மூன்று', 14: 'பதினான்கு', 15: 'பதினைந்து',
        16: 'பதினாறு', 17: 'பதினேழு', 18: 'பதினெட்டு', 19: 'பத்தொன்பது'
    }
    
    tens_exact = {
        20: 'இருபது', 30: 'முப்பது', 40: 'நாற்பது', 50: 'ஐம்பது',
        60: 'அறுபது', 70: 'எழுபது', 80: 'எண்பது', 90: 'தொண்ணூறு'
    }
    
    tens_prefix = {
        20: 'இருபத்து', 30: 'முப்பத்து', 40: 'நாற்பத்து', 50: 'ஐம்பத்து',
        60: 'அறுபத்து', 70: 'எழுபத்து', 80: 'எண்பத்து', 90: 'தொண்ணூற்று'
    }
    
    hundreds_exact = {
        100: 'நூறு', 200: 'இருநூறு', 300: 'முந்நூறு', 400: 'நானூறு',
        500: 'ஐந்நூறு', 600: 'அறுநூறு', 700: 'எழுநூறு', 800: 'எண்ணூறு', 900: 'தொள்ளாயிரம்'
    }
    
    hundreds_prefix = {
        100: 'நூற்று', 200: 'இருநூற்று', 300: 'முந்நூற்று', 400: 'நானூற்று',
        500: 'ஐந்நூற்று', 600: 'அறுநூற்று', 700: 'எழுநூற்று', 800: 'எண்ணூற்று', 900: 'தொள்ளாயிரத்து'
    }

    parts = []
    
    # Hundreds
    if n >= 100:
        h_val = (n // 100) * 100
        rem = n % 100
        if rem == 0:
            return hundreds_exact.get(h_val, '')
        else:
            parts.append(hundreds_prefix.get(h_val, ''))
            n = rem

    # Tens and units
    if n >= 20:
        t_val = (n // 10) * 10
        rem = n % 10
        if rem == 0:
            parts.append(tens_exact.get(t_val, ''))
        else:
            parts.append(tens_prefix.get(t_val, ''))
            parts.append(ones.get(rem, ''))
    elif n > 0:
        parts.append(ones.get(n, ''))

    return ' '.join([p for p in parts if p])


def _int_to_tamil_units(n):
    """Convert small integer (e.g. for count of thousands, lakhs) with proper prefix."""
    unit_prefixes = {
        1: 'ஒரு', 2: 'இரண்டு', 3: 'மூன்று', 4: 'நான்கு', 5: 'ஐந்து',
        6: 'ஆறு', 7: 'ஏழு', 8: 'எட்டு', 9: 'ஒன்பது'
    }
    if n in unit_prefixes:
        return unit_prefixes[n]
    return _int_to_tamil_under_thousand(n)


def number_to_tamil_words(amount):
    """Convert numeric amount to clean Tamil words (Indian grouping)."""
    try:
        dec = Decimal(str(amount))
    except Exception:
        return ''

    rupees = int(dec)
    paise = int(round((dec - Decimal(rupees)) * 100))

    if rupees == 0 and paise == 0:
        return 'பூஜ்ஜியம் ரூபாய் மட்டும்'

    parts = []

    # Crores (1,00,00,000)
    crores = rupees // 10000000
    if crores:
        parts.append(f"{_int_to_tamil_units(crores)} கோடி")
    rupees = rupees % 10000000

    # Lakhs (1,00,000)
    lakhs = rupees // 100000
    if lakhs:
        parts.append(f"{_int_to_tamil_units(lakhs)} லட்சம்")
    rupees = rupees % 100000

    # Thousands (1,000)
    thousands = rupees // 1000
    if thousands:
        parts.append(f"{_int_to_tamil_units(thousands)} ஆயிரம்")
    rupees = rupees % 1000

    # Under Thousand
    if rupees:
        parts.append(_int_to_tamil_under_thousand(rupees))

    rupees_str = ' '.join([p for p in parts if p]).strip()
    if rupees_str:
        result = f"{rupees_str} ரூபாய் மட்டும்"
    else:
        result = ''

    if paise > 0:
        paise_str = _int_to_tamil_under_thousand(paise)
        if result:
            result = f"{rupees_str} ரூபாய் {paise_str} பைசா மட்டும்"
        else:
            result = f"{paise_str} பைசா மட்டும்"

    return result


def process_item_photos_for_display(item_photos):
    """
    Centralized function to process item photos for display across the project.
    Handles both old file-based photos and new database-stored base64 photos.
    
    Args:
        item_photos: String containing either JSON array of photos or single photo data
        
    Returns:
        list: List of photo URLs/data URLs ready for display
    """
    if not item_photos:
        return []
    
    try:
        photo_list = []
        
        # Handle single base64 image
        if isinstance(item_photos, str) and item_photos.startswith('data:image/'):
            return [item_photos]
        
        # Handle JSON array of photos
        if isinstance(item_photos, str):
            if item_photos.startswith('['):
                photos_data = json.loads(item_photos)
            else:
                photos_data = [item_photos]
        else:
            photos_data = item_photos if isinstance(item_photos, list) else [item_photos]
        
        for photo in photos_data:
            if photo and isinstance(photo, str):
                if photo.startswith('data:image/'):
                    # Already base64 format, use directly
                    photo_list.append(photo)
                elif photo.startswith('/media/'):
                    # File path - convert to base64 or check if file exists
                    try:
                        relative_path = photo.replace('/media/', '')
                        file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                        
                        if os.path.exists(file_path):
                            # Convert file to base64 for consistent display
                            with open(file_path, 'rb') as f:
                                file_content = f.read()
                                encoded = base64.b64encode(file_content).decode('utf-8')
                                photo_list.append(f"data:image/jpeg;base64,{encoded}")
                        else:
                            # File doesn't exist, skip it
                            continue
                    except Exception as e:
                        print(f"Error processing file photo {photo}: {str(e)}")
                        continue
                else:
                    # Assume it's already base64 (without data: prefix)
                    photo_list.append(f"data:image/jpeg;base64,{photo}")
        
        return photo_list
    
    except Exception as e:
        print(f"Error processing item photos: {str(e)}")
        return []


def get_first_item_photo(item_photos):
    """
    Get the first item photo for thumbnails and previews.
    
    Args:
        item_photos: String containing photo data
        
    Returns:
        str: First photo URL/data URL or placeholder if none available
    """
    photos = process_item_photos_for_display(item_photos)
    if photos:
        return photos[0]
    return "/static/img/placeholder-item.png"


def get_item_photos_count(item_photos):
    """
    Get the count of item photos.
    
    Args:
        item_photos: String containing photo data
        
    Returns:
        int: Number of photos
    """
    photos = process_item_photos_for_display(item_photos)
    return len(photos)


# Basic placeholder views for the transactions app
# These will need to be implemented properly with the correct models

class LoanListView(LoginRequiredMixin, RoleBranchAccessMixin, DownloadMixin, ListView):
    model = Loan
    template_name = 'transactions/loan_list.html'
    context_object_name = 'loans'
    paginate_by = 15
    
    def get_queryset(self):
        queryset = Loan.objects.all()
        user = self.request.user

        # Apply centralized branch/region access rules and organization isolation
        queryset = self.filter_queryset_by_branches(queryset, branch_field_name='branch')
        if user.organization:
            queryset = queryset.filter(branch__organization=user.organization)

        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Scheme filter
        scheme_id = self.request.GET.get('scheme')
        if scheme_id:
            queryset = queryset.filter(scheme_id=scheme_id)

        # Search filter
        search = self.request.GET.get('search')
        if search:
            search = search.strip()
        if search:
            search_terms = search.split()
            search_filter = (
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__phone__icontains=search) |
                Q(loan_number__icontains=search) |
                Q(loanitem__item__name__icontains=search)
            )
            # If multiple terms provided (e.g. pasted full name with space "Ramesh Kumar"), match across fields
            if len(search_terms) > 1:
                multi_q = Q()
                for term in search_terms:
                    multi_q &= (
                        Q(customer__first_name__icontains=term) |
                        Q(customer__last_name__icontains=term) |
                        Q(customer__phone__icontains=term) |
                        Q(loan_number__icontains=term) |
                        Q(loanitem__item__name__icontains=term)
                    )
                search_filter = search_filter | multi_q

            queryset = queryset.filter(search_filter).distinct()

        # Date range filter
        date_range = self.request.GET.get('date_range')
        today = timezone.now().date()
        
        if date_range == 'today':
            queryset = queryset.filter(issue_date=today)
        elif date_range == 'this_week':
            week_start = today - timezone.timedelta(days=today.weekday())
            queryset = queryset.filter(issue_date__gte=week_start)
        elif date_range == 'this_month':
            queryset = queryset.filter(issue_date__year=today.year, issue_date__month=today.month)
        elif date_range == 'this_year':
            queryset = queryset.filter(issue_date__year=today.year)

        # New filters for overdue, due_soon, tiered, and due date +/- 5 days
        filter_type = self.request.GET.get('filter_type')
        if filter_type == 'overdue':
            queryset = queryset.filter(status='active', due_date__lt=today)
        elif filter_type == 'due_soon':
            queryset = queryset.filter(status='active', due_date__gte=today, due_date__lte=today + timezone.timedelta(days=30))
        elif filter_type == 'tiered':
            queryset = queryset.filter(
                scheme__interest_rate_structure__isnull=False
            ).exclude(scheme__interest_rate_structure={})
        elif filter_type == 'due_plus_5':
            queryset = queryset.filter(status='active', due_date__gte=today, due_date__lte=today + timezone.timedelta(days=5))
        elif filter_type == 'due_minus_5':
            queryset = queryset.filter(status='active', due_date__gte=today - timezone.timedelta(days=5), due_date__lt=today)
        elif filter_type == 'due_window_5':
            queryset = queryset.filter(status='active', due_date__gte=today - timezone.timedelta(days=5), due_date__lte=today + timezone.timedelta(days=5))

        # Sorting
        sort_by = self.request.GET.get('sort', '-issue_date')  # Default sort by newest first
        valid_sort_fields = {
            'customer': 'customer__first_name',
            '-customer': '-customer__first_name',
            'principal': 'principal_amount',
            '-principal': '-principal_amount',
            'issue_date': 'issue_date',
            '-issue_date': '-issue_date',
            'due_date': 'due_date',
            '-due_date': '-due_date',
            'status': 'status',
            '-status': '-status',
            'branch': 'branch__name',
            '-branch': '-branch__name',
        }
        
        if sort_by in valid_sort_fields:
            queryset = queryset.order_by(valid_sort_fields[sort_by])
        else:
            queryset = queryset.order_by('-issue_date')  # Default fallback

        return queryset.select_related('customer', 'branch').prefetch_related('loanitem_set', 'loanitem_set__item')

    def get_download_filename(self, format_type='csv'):
        """Generate download filename for loans export"""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        status = (self.request.GET.get('status') or 'all').strip().lower()
        # Normalize status to safe filename fragment
        status = re.sub(r'[^a-z0-9_\-]', '_', status)
        return f'loans_export_{status}_{timestamp}.{format_type}'

    def get_download_headers(self):
        """Return headers for download export"""
        all_headers = [
            ('roll_number', 'Roll Number'),
            ('loan_number', 'Loan Number'),
            ('customer_name', 'Customer Name'),
            ('phone', 'Customer Phone'),
            ('email', 'Customer Email'), 
            ('branch', 'Branch'),
            ('item_images', 'Image Count'),
            ('principal_amount', 'Principal Amount (Rs: )'),
            ('distribution_amount', 'Distribution Amount (Rs: )'),
            ('interest_rate', 'Interest Rate (%)'),
            ('issue_date', 'Issue Date'),
            ('due_date', 'Due Date'),
            ('status', 'Status'),
            ('days_since_issue', 'Days Since Issue'),
            ('days_remaining', 'Days Remaining'),
            ('item_names', 'Item Names'),
            ('total_weight', 'Total Weight (grams)'),
            ('karat', 'Gold Karat'),
            ('gold_location', 'Gold Location'),
            ('repledge_date', 'Repledge Date'),
            ('repledge_amount', 'Repledge Amount (Rs: )'),
            ('monthly_interest', 'Monthly Interest Amount (Rs: )'),
            ('total_payable', 'Total Payable Till Date (Rs: )'),
            ('amount_paid', 'Amount Paid (Rs: )'),
            ('remaining_balance', 'Remaining Balance (Rs: )'),
            ('created_at', 'Created Date'),
            ('created_by', 'Created By')
        ]
        
        selected_columns = self.get_selected_columns()
        if selected_columns:
            headers = []
            for col_key, col_name in all_headers:
                if col_key in selected_columns:
                    headers.append(col_name)
            return headers
        
        return [col_name for _, col_name in all_headers]
    
    def get_selected_columns(self):
        """Get selected columns from request"""
        columns_param = self.request.GET.get('columns', '')
        if columns_param:
            return columns_param.split(',')
        return None
    
    def filter_row_data(self, row_data, selected_columns=None):
        """Filter row data based on selected columns"""
        if not selected_columns:
            return row_data
        
        column_keys = [
            'roll_number', 'loan_number', 'customer_name', 'phone', 'email', 'branch',
            'item_images', 'principal_amount', 'distribution_amount', 'interest_rate', 'issue_date', 'due_date', 'status',
            'days_since_issue', 'days_remaining', 'item_names', 'total_weight', 'karat',
            'gold_location', 'repledge_date', 'repledge_amount',
            'monthly_interest', 'total_payable', 'amount_paid', 'remaining_balance',
            'created_at', 'created_by'
        ]
        
        filtered_row = []
        for i, col_key in enumerate(column_keys):
            if i < len(row_data) and col_key in selected_columns:
                filtered_row.append(row_data[i])
        return filtered_row

    def get_download_data(self):
        """Return data for download export"""
        queryset = self.get_queryset()
        
        data = []
        for index, loan in enumerate(queryset, start=1):
            # Get loan items information
            loan_items = loan.loanitem_set.all()
            item_names = []
            total_weight = 0
            karat_info = set()
            
            for item in loan_items:
                if item.item:
                    item_names.append(item.item.name)
                if hasattr(item, 'net_weight') and item.net_weight:
                    total_weight += float(item.net_weight)
                if hasattr(item, 'gold_karat') and item.gold_karat:
                    karat_info.add(f"{item.gold_karat}K")
            
            repledge_date_str = loan.repledge_date.strftime('%Y-%m-%d') if loan.repledge_date else ''
            repledge_amt = float(loan.repledge_amount) if loan.repledge_amount else 0
            gold_loc = loan.gold_location or ''
            
            # Calculate financial information
            try:
                monthly_interest = 0
                if hasattr(loan, 'monthly_interest_amount'):
                    monthly_interest = round(float(loan.monthly_interest_amount()))
                
                total_payable = 0
                if hasattr(loan, 'total_payable_till_date'):
                    total_payable = round(float(loan.total_payable_till_date))
                
                amount_paid = 0
                if hasattr(loan, 'amount_paid'):
                    amount_paid = round(float(loan.amount_paid))
                
                remaining_balance = total_payable
            except:
                monthly_interest = 0
                total_payable = 0
                amount_paid = 0
                remaining_balance = 0
            
            # Calculate days information
            try:
                days_since_issue = (timezone.now().date() - loan.issue_date).days if loan.issue_date else 0
                days_remaining = (loan.due_date - timezone.now().date()).days if loan.due_date else 0
            except:
                days_since_issue = 0
                days_remaining = 0
            
            row = [
                index,
                loan.loan_number or '',
                f"{loan.customer.first_name} {loan.customer.last_name}" if loan.customer else '',
                loan.customer.phone if loan.customer and hasattr(loan.customer, 'phone') else '',
                loan.customer.email if loan.customer and hasattr(loan.customer, 'email') else '',
                loan.branch.name if loan.branch else '',
                str(len(loan.item_photo_list)) if hasattr(loan, 'item_photo_list') and loan.item_photo_list else '0',
                round(float(loan.principal_amount)) if loan.principal_amount else 0,
                round(float(loan.distribution_amount)) if hasattr(loan, 'distribution_amount') and loan.distribution_amount else 0,
                float(loan.interest_rate) if loan.interest_rate else 0,
                loan.issue_date.strftime('%Y-%m-%d') if loan.issue_date else '',
                loan.due_date.strftime('%Y-%m-%d') if loan.due_date else '',
                loan.get_status_display() if hasattr(loan, 'get_status_display') else (loan.status or ''),
                days_since_issue,
                days_remaining,
                ', '.join(item_names) if item_names else '',
                total_weight,
                ', '.join(sorted(karat_info)) if karat_info else '',
                gold_loc,
                repledge_date_str,
                repledge_amt,
                monthly_interest,
                total_payable,
                amount_paid,
                remaining_balance,
                loan.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(loan, 'created_at') and loan.created_at else '',
                f"{loan.created_by.first_name} {loan.created_by.last_name}" if hasattr(loan, 'created_by') and loan.created_by else ''
            ]
            data.append(row)
        
        return data

    def get_download_data_for_index(self, loan, index):
        """Return data row for a single loan (used by PDF export)."""
        try:
            monthly_interest = 0
            if hasattr(loan, 'monthly_interest_amount'):
                monthly_interest = round(float(loan.monthly_interest_amount()))

            total_payable = 0
            if hasattr(loan, 'total_payable_till_date'):
                total_payable = round(float(loan.total_payable_till_date))

            amount_paid = 0
            if hasattr(loan, 'amount_paid'):
                amount_paid = round(float(loan.amount_paid))

            remaining_balance = total_payable
        except Exception:
            monthly_interest = 0
            total_payable = 0
            amount_paid = 0
            remaining_balance = 0

        try:
            days_since_issue = (timezone.now().date() - loan.issue_date).days if loan.issue_date else 0
            days_remaining = (loan.due_date - timezone.now().date()).days if loan.due_date else 0
        except Exception:
            days_since_issue = 0
            days_remaining = 0

        loan_items = loan.loanitem_set.all()
        item_names = [li.item.name for li in loan_items if li.item]
        repledge_date_str = loan.repledge_date.strftime('%Y-%m-%d') if loan.repledge_date else ''
        repledge_amt = float(loan.repledge_amount) if loan.repledge_amount else 0
        gold_loc = loan.gold_location or ''

        return [
            index,
            loan.loan_number or '',
            f"{loan.customer.first_name} {loan.customer.last_name}" if loan.customer else '',
            loan.customer.phone if loan.customer and hasattr(loan.customer, 'phone') else '',
            loan.customer.email if loan.customer and hasattr(loan.customer, 'email') else '',
            loan.branch.name if loan.branch else '',
            str(len(getattr(loan, 'item_photo_list', []))) if getattr(loan, 'item_photo_list', None) else '0',
            float(loan.principal_amount) if loan.principal_amount else 0,
            float(loan.distribution_amount) if hasattr(loan, 'distribution_amount') and loan.distribution_amount else 0,
            float(loan.interest_rate) if loan.interest_rate else 0,
            loan.issue_date.strftime('%Y-%m-%d') if loan.issue_date else '',
            loan.due_date.strftime('%Y-%m-%d') if loan.due_date else '',
            loan.get_status_display() if hasattr(loan, 'get_status_display') else (loan.status or ''),
            days_since_issue,
            days_remaining,
            ', '.join(item_names) if item_names else '',
            0,
            '',
            gold_loc,
            repledge_date_str,
            repledge_amt,
            monthly_interest,
            total_payable,
            amount_paid,
            remaining_balance,
            loan.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(loan, 'created_at') and loan.created_at else '',
            f"{loan.created_by.first_name} {loan.created_by.last_name}" if hasattr(loan, 'created_by') and loan.created_by else ''
        ]

    
    def download_csv(self):
        return self.export_csv()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = (self.request.GET.get('search') or '').strip()
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_date_range'] = self.request.GET.get('date_range', '')
        context['selected_filter_type'] = self.request.GET.get('filter_type', '')
        context['current_sort'] = self.request.GET.get('sort', '-issue_date')
        context['selected_scheme'] = self.request.GET.get('scheme', '')

        # Populate scheme dropdown with schemes visible to this user's organization
        from schemes.models import Scheme
        user = self.request.user
        if user.organization:
            context['schemes'] = Scheme.objects.filter(
                Q(is_default=True) | Q(organization=user.organization)
            ).order_by('name')
        else:
            context['schemes'] = Scheme.objects.all().order_by('name')
        
        # Calculate loan statistics for the cards - optimized with aggregation
        user = self.request.user
        base_queryset = Loan.objects.all()
        base_queryset = self.filter_queryset_by_branches(base_queryset, branch_field_name='branch')
        if user.organization:
            base_queryset = base_queryset.filter(branch__organization=user.organization)
        
        # Calculate statistics efficiently - SINGLE QUERY with annotations
        from django.utils import timezone
        from django.db.models import Count, Q, Sum, F, Case, When
        
        today = timezone.now().date()
        
        # Get all statistics in a single aggregation query, including outstanding sums
        from django.db.models import Sum, F, Value as V
        from django.db.models.functions import Coalesce

        # Expression for outstanding per loan: use total_payable_till_date if present else principal_amount, minus amount_paid
        outstanding_expr = (Coalesce(F('total_payable_till_date'), F('principal_amount'), V(0)) - Coalesce(F('amount_paid'), V(0)))

        # Only aggregate simple count metrics via the database; monetary
        # totals rely on model properties and are calculated in Python below.
        stats = base_queryset.aggregate(
            active_count=Count('id', filter=Q(status='active')),
            due_today_count=Count('id', filter=Q(status='active', due_date=today)),
            overdue_count=Count('id', filter=Q(status='active', due_date__lt=today)),
            due_soon_count=Count('id', filter=Q(status='active', due_date__gte=today, due_date__lte=today + timezone.timedelta(days=30))),
            tiered_count=Count('id', filter=Q(status='active', scheme__interest_rate_structure__isnull=False) & ~Q(scheme__interest_rate_structure={})),
            due_plus_5_count=Count('id', filter=Q(status='active', due_date__gte=today, due_date__lte=today + timezone.timedelta(days=5))),
            due_minus_5_count=Count('id', filter=Q(status='active', due_date__gte=today - timezone.timedelta(days=5), due_date__lt=today)),
            due_window_5_count=Count('id', filter=Q(status='active', due_date__gte=today - timezone.timedelta(days=5), due_date__lte=today + timezone.timedelta(days=5))),
        )

        # Debug logging to help trace incorrect zeros in the UI
        try:
            import logging
            logger = logging.getLogger('transactions.views')
            logger.info(f"LoanListView.get_context_data called for user={getattr(user,'username',None)}; stats={stats}")
        except Exception:
            pass
        # Also print to stdout for dev server visibility
        try:
            print(f"[DEBUG] LoanListView.stats for user={getattr(user,'username',None)}: {stats}")
        except Exception:
            pass

        context['active_loans_count'] = stats.get('active_count') or 0
        context['due_today_count'] = stats.get('due_today_count') or 0
        context['overdue_count'] = stats.get('overdue_count') or 0
        context['due_soon_count'] = stats.get('due_soon_count') or 0
        context['tiered_count'] = stats.get('tiered_count') or 0
        context['due_plus_5_count'] = stats.get('due_plus_5_count') or 0
        context['due_minus_5_count'] = stats.get('due_minus_5_count') or 0
        context['due_window_5_count'] = stats.get('due_window_5_count') or 0

        # Monetary summaries (Decimal) - coerce None to 0
        # Compute monetary summaries in Python using model properties (accurate
        # even when values are computed via methods). Prefetch payments to avoid
        # N+1 queries.
        loans_iter = base_queryset.select_related('customer', 'branch').prefetch_related('payments')

        def loan_outstanding(ln):
            try:
                tp = getattr(ln, 'total_payable_till_date', None)
                if callable(tp):
                    tp = tp()
                if tp is None:
                    tp = getattr(ln, 'principal_amount', 0) or 0

                return Decimal(str(tp or 0))
            except Exception:
                return Decimal('0.00')

        active_sum = Decimal('0.00')
        due_today_sum = Decimal('0.00')
        due_soon_sum = Decimal('0.00')
        overdue_sum = Decimal('0.00')
        total_sum = Decimal('0.00')
        
        thirty_days_later = today + timezone.timedelta(days=30)

        for ln in loans_iter:
            o = loan_outstanding(ln)
            total_sum += o
            if getattr(ln, 'status', '') == 'active':
                active_sum += o
                if getattr(ln, 'due_date', None) == today:
                    due_today_sum += o
                if getattr(ln, 'due_date', None) and getattr(ln, 'due_date') < today:
                    overdue_sum += o
                if getattr(ln, 'due_date', None) and today <= getattr(ln, 'due_date') <= thirty_days_later:
                    due_soon_sum += o

        context['active_outstanding'] = active_sum
        context['due_today_outstanding'] = due_today_sum
        context['due_soon_outstanding'] = due_soon_sum
        context['overdue_outstanding'] = overdue_sum
        context['total_outstanding'] = total_sum

        # Visibility controls: show financial summary only for admin users
        is_admin_user = bool((user.username == 'admin') or user.is_staff or user.is_superuser or getattr(user, 'is_pawnshop_admin', False) or getattr(user, 'is_organization_admin', False))
        context['show_total_outstanding'] = is_admin_user
        context['show_total_loan_lists'] = is_admin_user
        return context

    def get(self, request, *args, **kwargs):
        # Check if download is requested
        download_format = request.GET.get('download')
        if download_format:
            if download_format == 'csv':
                return self.export_csv()
            elif download_format == 'excel':
                return self.export_excel()
            elif download_format == 'pdf':
                return self.export_pdf()
        
        return super().get(request, *args, **kwargs)

    def export_csv(self):
        """Export data as CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.get_download_filename("csv")}"'
        
        writer = csv.writer(response)
        writer.writerow(self.get_download_headers())
        
        selected_columns = self.get_selected_columns()
        for row in self.get_download_data():
            filtered_row = self.filter_row_data(row, selected_columns)
            writer.writerow(filtered_row)
        
        return response

    def export_excel(self):
        """Export data as Excel"""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Loans Export"
        
        # Style headers
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        # Write headers
        headers = self.get_download_headers()
        for col, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        
        # Write data
        selected_columns = self.get_selected_columns()
        for row_idx, row_data in enumerate(self.get_download_data(), 2):
            filtered_row = self.filter_row_data(row_data, selected_columns)
            for col_idx, value in enumerate(filtered_row, 1):
                worksheet.cell(row=row_idx, column=col_idx, value=value)
        
        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Save to response
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{self.get_download_filename("xlsx")}"'
        
        return response

    def export_pdf(self):
        from reportlab.lib.pagesizes import letter, A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from datetime import datetime
        
        response = HttpResponse(content_type='application/pdf')
        disposition = 'inline' if self.request.GET.get('preview') == '1' else 'attachment'
        response['Content-Disposition'] = f'{disposition}; filename="{self.get_download_filename("pdf")}"'
        
        doc = SimpleDocTemplate(
            response,
            pagesize=landscape(A4),
            rightMargin=0.3*inch,
            leftMargin=0.3*inch,
            topMargin=0.6*inch,
            bottomMargin=0.6*inch
        )
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=12,
            alignment=1
        )
        elements.append(Paragraph("LOANS EXPORT", title_style))
        elements.append(Spacer(1, 12))

        header_cell_style = ParagraphStyle(
            'LoanExportHeaderCell',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9,
            textColor=colors.whitesmoke,
            alignment=TA_CENTER,
            splitLongWords=1,
        )
        body_cell_style = ParagraphStyle(
            'LoanExportBodyCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7,
            leading=8.5,
            alignment=TA_LEFT,
            splitLongWords=1,
        )
        
        # PDF Export - Show key columns including Gold Location and Repledge Info
        pdf_headers = [
            'Roll Number',
            'Loan Number',
            'Customer Name',
            'Customer Phone',
            'Branch',
            'Distribution Amount (Rs: )',
            'Issue Date',
            'Due Date',
            'Status',
            'Item Names',
            'Gold Location',
            'Repledge Date',
            'Repledge Amount (Rs: )'
        ]
        
        # Map header names to row indices
        all_headers = self.get_download_headers()
        header_indices = {
            'Roll Number': 0,
            'Loan Number': 1,
            'Customer Name': 2,
            'Customer Phone': 3,
            'Branch': 5,
            'Distribution Amount (Rs: )': 8,
            'Issue Date': 10,
            'Due Date': 11,
            'Status': 12,
            'Item Names': 15,
            'Gold Location': 18,
            'Repledge Date': 19,
            'Repledge Amount (Rs: )': 20
        }
        
        if self.request.GET.get('full') == '1':
            pdf_headers = self.get_download_headers()
            header_indices = {header: index for index, header in enumerate(pdf_headers)}

        # Build table with only selected columns
        table_data = [[Paragraph(str(header), header_cell_style) for header in pdf_headers]]
        queryset = self.get_queryset()
        
        for index, loan in enumerate(queryset, start=1):
            row = self.get_download_data_for_index(loan, index)
            pdf_row = [
                Paragraph(str(row[header_indices[h]]) if row[header_indices[h]] is not None else '', body_cell_style)
                for h in pdf_headers
            ]
            table_data.append(pdf_row)
        
        # Column widths for 13 columns on landscape A4
        # Available width: 11.69 - 0.6 = 11.09 inches
        col_widths = [
            0.50 * inch,  # Roll Number
            0.90 * inch,  # Loan Number
            1.05 * inch,  # Customer Name
            0.80 * inch,  # Customer Phone
            1.10 * inch,  # Branch
            0.80 * inch,  # Distribution Amount
            0.70 * inch,  # Issue Date
            0.70 * inch,  # Due Date
            0.55 * inch,  # Status
            1.15 * inch,  # Item Names
            0.90 * inch,  # Gold Location
            0.75 * inch,  # Repledge Date
            0.80 * inch,  # Repledge Amount
        ]
        
        if self.request.GET.get('full') == '1':
            col_widths = [0.45 * inch] * len(pdf_headers)

        # Create table with specified column widths
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Define table style with better formatting
        table_style = TableStyle([
            # Header style - blue background with white text
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
            
            # Data rows - larger font for readability
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            
            # Grid lines - darker and thicker for visibility
            ('GRID', (0, 0), (-1, -1), 1.5, colors.HexColor('#34495E')),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
            
            # Right align numeric columns
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Roll Number
            ('ALIGN', (5, 1), (5, -1), 'RIGHT'),   # Distribution Amount
            ('ALIGN', (6, 1), (8, -1), 'CENTER'),  # Dates, Status
        ])
        
        table.setStyle(table_style)
        elements.append(table)
        elements.append(Spacer(1, 12))
        
        # Footer with timestamp
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#7F8C8D'),
            alignment=1
        )
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y at %I:%M %p')}", footer_style))
        
        # Build PDF
        doc.build(elements)
        return response


class LoanExpiryNoticeView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    def get(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # enforce branch access
        self.check_object_branch_access(loan, branch_attr='branch')
        today = timezone.now().date()

        # Determine if an expiry/auction notice should be shown
        show_notice = False
        try:
            if getattr(loan, 'due_date', None) and loan.due_date <= today:
                show_notice = True
            elif getattr(loan, 'grace_period_end', None) and loan.grace_period_end <= today:
                show_notice = True
        except Exception:
            show_notice = False

        # Compute a best-effort remaining balance for display
        remaining = None
        try:
            remaining = getattr(loan, 'remaining_balance', None)
            if remaining is None:
                total_payable = getattr(loan, 'total_payable_till_date', None) or 0
                paid = sum(p.amount for p in loan.payments.all()) if hasattr(loan, 'payments') else 0
                remaining = max(0, total_payable - paid) if total_payable else getattr(loan, 'principal_amount', 0)
        except Exception:
            remaining = getattr(loan, 'principal_amount', 0)

        use_tamil = str(getattr(request, 'LANGUAGE_CODE', '')).startswith('ta')

        context = {
            'loan': loan,
            'remaining_balance': remaining,
            'today': today,
            'show_notice': show_notice,
            'use_tamil': use_tamil,
            'branch_phone_display': get_branch_bill_header_phones(getattr(loan, 'branch', None)),
            'customer_photo': get_first_item_photo(loan.customer_face_capture) if loan.customer_face_capture else None,
            'first_item_photo': get_first_item_photo(loan.item_photos) if loan.item_photos else None,
        }
        # Generate WhatsApp demand notice link
        try:
            from transactions.services_whatsapp import send_loan_expiry_notice_whatsapp
            wa_data = send_loan_expiry_notice_whatsapp(loan, request_user=request.user, lang=getattr(request, 'LANGUAGE_CODE', None))
            context['whatsapp_demand_link'] = wa_data.get('link', '')
            context['customer_phone'] = wa_data.get('phone', '')
        except Exception:
            context['whatsapp_demand_link'] = ''
            context['customer_phone'] = ''

        return render(request, 'transactions/loan_expiry_notice.html', context)

    def post(self, request, loan_number):
        """Send Expiry/Demand Notice email to the borrower."""
        loan = get_object_or_404(Loan, loan_number=loan_number)
        self.check_object_branch_access(loan, branch_attr='branch')
        try:
            from transactions.services_email import send_loan_expiry_notice_email
            lang = getattr(request, 'LANGUAGE_CODE', None)
            sent = send_loan_expiry_notice_email(loan, request_user=request.user, lang=lang)
            if sent:
                messages.success(
                    request,
                    f"Demand Notice email has been sent to {loan.customer.email} successfully."
                )
            else:
                messages.warning(
                    request,
                    "Could not send email. The customer may not have a registered email address."
                )
        except Exception as exc:
            messages.error(request, f"Failed to send demand notice email: {exc}")
        return redirect(reverse('loan_expiry_notice', kwargs={'loan_number': loan_number}))


class LoanSendEmailView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    POST-only view to send email notifications to the borrower directly
    from the Loan Detail page.

    POST params:
      email_type: 'reminder' | 'demand_notice' | 'payment_reminder'
    """
    def post(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        self.check_object_branch_access(loan, branch_attr='branch')
        email_type = request.POST.get('email_type', 'reminder')
        lang = getattr(request, 'LANGUAGE_CODE', None)

        try:
            from transactions.services_email import (
                send_due_date_reminder_email,
                send_loan_expiry_notice_email,
            )
            customer_email = getattr(loan.customer, 'email', None)
            if not customer_email:
                messages.warning(
                    request,
                    f"No email address found for customer {loan.customer}. "
                    "Please update the customer profile with a valid email."
                )
            elif email_type == 'demand_notice':
                sent = send_loan_expiry_notice_email(loan, request_user=request.user, lang=lang)
                if sent:
                    messages.success(
                        request,
                        f"\u2709 Demand / Expiry Notice email sent to {customer_email} successfully."
                    )
                else:
                    messages.error(request, "Demand notice email could not be delivered. Check server email settings.")
            elif email_type in ('reminder', 'payment_reminder'):
                send_due_date_reminder_email(loan, days_left=None, lang=lang)
                messages.success(
                    request,
                    f"\u2709 Due-date reminder email sent to {customer_email} successfully."
                )
            else:
                messages.warning(request, f"Unknown email type: {email_type}")
        except Exception as exc:
            messages.error(request, f"Failed to send email: {exc}")

        return redirect(reverse('loan_detail', kwargs={'loan_number': loan_number}))


def safe_whatsapp_redirect(url):
    """
    Safely redirects browser to WhatsApp Web even if URL exceeds Django's 2048-char DisallowedRedirect limit.
    """
    import json
    from django.utils.html import escape
    from django.http import HttpResponse

    escaped_url = escape(url)
    json_url = json.dumps(url)
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="0; url={escaped_url}">
    <title>Opening WhatsApp...</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background-color: #f8fafc;">
    <div style="text-align: center; background: white; padding: 2.5rem; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); max-width: 420px; border: 1px solid #e2e8f0;">
        <div style="font-size: 2.5rem; color: #25D366; margin-bottom: 1rem;">💬</div>
        <h3 style="margin-top: 0; color: #1e293b; font-size: 1.25rem;">Opening WhatsApp Web...</h3>
        <p style="color: #64748b; font-size: 0.9rem; margin-bottom: 1.5rem;">Redirecting to WhatsApp chat. If it doesn't open automatically, click below:</p>
        <a href="{escaped_url}" style="display: inline-block; background-color: #25D366; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 0.95rem;">Continue to WhatsApp</a>
    </div>
    <script>
        window.location.replace({json_url});
    </script>
</body>
</html>"""
    return HttpResponse(html)


class LoanSendWhatsAppView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    POST-only view to trigger WhatsApp notifications (via PyWhatKit or WhatsApp direct).
    POST params:
      whatsapp_type: 'reminder' | 'demand_notice' | 'payment_reminder'
      mode: 'pywhatkit' (default) | 'link'
    """
    def post(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        self.check_object_branch_access(loan, branch_attr='branch')
        whatsapp_type = request.POST.get('whatsapp_type', 'reminder')
        mode = request.POST.get('mode', 'pywhatkit')
        lang = getattr(request, 'LANGUAGE_CODE', None)

        try:
            from transactions.models import LoanWhatsAppLog
            from transactions.services_whatsapp import (
                send_due_date_reminder_whatsapp,
                send_loan_expiry_notice_whatsapp,
            )
            raw_phone = getattr(loan.customer, 'phone', None)
            if not raw_phone:
                messages.warning(
                    request,
                    f"No phone number found for customer {loan.customer}. "
                    "Please update the customer profile with a valid phone number."
                )
                LoanWhatsAppLog.objects.create(
                    loan=loan,
                    customer=loan.customer,
                    recipient_phone='',
                    notification_type=whatsapp_type,
                    status='failed',
                    error_message='No phone number on customer profile',
                    channel='manual',
                    sent_by=request.user,
                )
                return redirect(reverse('loan_detail', kwargs={'loan_number': loan_number}))

            if whatsapp_type == 'demand_notice':
                res = send_loan_expiry_notice_whatsapp(
                    loan, request_user=request.user, lang=lang, send_pywhatkit=(mode == 'pywhatkit')
                )
                if not res.get('success'):
                    messages.warning(request, f"Invalid phone number '{raw_phone}'. Could not prepare WhatsApp notification.")
                    LoanWhatsAppLog.objects.create(
                        loan=loan,
                        customer=loan.customer,
                        recipient_phone=raw_phone,
                        notification_type='demand_notice',
                        status='failed',
                        error_message=f"Invalid phone number '{raw_phone}'",
                        channel=mode,
                        sent_by=request.user,
                    )
                elif mode == 'link' and res.get('link'):
                    LoanWhatsAppLog.objects.create(
                        loan=loan,
                        customer=loan.customer,
                        recipient_phone=res.get('phone', raw_phone),
                        notification_type='demand_notice',
                        status='sent',
                        message_content=res.get('message', ''),
                        channel='direct_link',
                        sent_by=request.user,
                    )
                    return safe_whatsapp_redirect(res['link'])
                else:
                    LoanWhatsAppLog.objects.create(
                        loan=loan,
                        customer=loan.customer,
                        recipient_phone=res.get('phone', raw_phone),
                        notification_type='demand_notice',
                        status='sent',
                        message_content=res.get('message', ''),
                        channel='pywhatkit',
                        sent_by=request.user,
                    )
                    messages.success(
                        request,
                        f"💬 Demand Notice WhatsApp message scheduled to {res['phone']} via PyWhatKit automation."
                    )
            elif whatsapp_type in ('reminder', 'payment_reminder'):
                res = send_due_date_reminder_whatsapp(
                    loan, days_left=None, lang=lang, send_pywhatkit=(mode == 'pywhatkit')
                )
                if not res.get('success'):
                    messages.warning(request, f"Invalid phone number '{raw_phone}'. Could not prepare WhatsApp notification.")
                    LoanWhatsAppLog.objects.create(
                        loan=loan,
                        customer=loan.customer,
                        recipient_phone=raw_phone,
                        notification_type=whatsapp_type,
                        status='failed',
                        error_message=f"Invalid phone number '{raw_phone}'",
                        channel=mode,
                        sent_by=request.user,
                    )
                elif mode == 'link' and res.get('link'):
                    LoanWhatsAppLog.objects.create(
                        loan=loan,
                        customer=loan.customer,
                        recipient_phone=res.get('phone', raw_phone),
                        notification_type=whatsapp_type,
                        status='sent',
                        message_content=res.get('message', ''),
                        channel='direct_link',
                        sent_by=request.user,
                    )
                    return safe_whatsapp_redirect(res['link'])
                else:
                    LoanWhatsAppLog.objects.create(
                        loan=loan,
                        customer=loan.customer,
                        recipient_phone=res.get('phone', raw_phone),
                        notification_type=whatsapp_type,
                        status='sent',
                        message_content=res.get('message', ''),
                        channel='pywhatkit',
                        sent_by=request.user,
                    )
                    messages.success(
                        request,
                        f"💬 Due-date reminder WhatsApp message scheduled to {res['phone']} via PyWhatKit automation."
                    )
            else:
                messages.warning(request, f"Unknown WhatsApp type: {whatsapp_type}")
        except Exception as exc:
            messages.error(request, f"Failed to send WhatsApp notification: {exc}")

        return redirect(reverse('loan_detail', kwargs={'loan_number': loan_number}))


class LoanTrackWhatsAppClickView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    Tracks and records WhatsApp notification clicks/dispatches into LoanWhatsAppLog,
    then seamlessly redirects the staff browser to WhatsApp Web or returns JSON.
    """
    def get(self, request, loan_number):
        return self._handle(request, loan_number, request.GET)

    def post(self, request, loan_number):
        import json
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = request.POST
        return self._handle(request, loan_number, data)

    def _handle(self, request, loan_number, params):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        self.check_object_branch_access(loan, branch_attr='branch')

        from transactions.models import LoanWhatsAppLog
        from transactions.services_whatsapp import (
            build_smart_loan_whatsapp_message,
            send_due_date_reminder_whatsapp,
            send_loan_expiry_notice_whatsapp,
            get_whatsapp_link,
            normalize_phone_number,
        )

        notification_type = params.get('type', 'reminder')
        custom_message = params.get('custom_message', '').strip()
        lang = params.get('lang') or getattr(request, 'LANGUAGE_CODE', 'ta')
        should_redirect = params.get('redirect') in ('1', 'true', True)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or (not should_redirect and request.method == 'POST')

        raw_phone = getattr(loan.customer, 'phone', '') or ''
        norm_phone = normalize_phone_number(raw_phone)

        # Build message
        if custom_message:
            message_text = custom_message
        elif notification_type == 'demand_notice':
            wa_data = send_loan_expiry_notice_whatsapp(loan, request_user=request.user, lang=lang, send_pywhatkit=False)
            message_text = wa_data.get('message', '')
        elif notification_type in ('custom_chat', 'direct_chat'):
            branch_name = loan.branch.name if loan.branch else 'First Money Gold'
            cust_name = getattr(loan.customer, 'first_name', '') or getattr(loan.customer, 'name', '') or 'Customer'
            message_text = f"Hello {cust_name}, regarding Gold Loan #{loan.loan_number} at {branch_name}."
        else:
            message_text = build_smart_loan_whatsapp_message(loan=loan, notification_type=notification_type, lang=lang, request_user=request.user)

        wa_url = get_whatsapp_link(norm_phone or raw_phone, message_text) if (norm_phone or raw_phone) else ''

        # Create audit log
        log_entry = LoanWhatsAppLog.objects.create(
            loan=loan,
            customer=loan.customer,
            recipient_phone=norm_phone or raw_phone,
            notification_type=notification_type,
            status='sent' if norm_phone else 'failed',
            error_message='' if norm_phone else f"Invalid customer phone number '{raw_phone}'",
            message_content=message_text,
            channel='direct_link',
            sent_by=request.user if request.user.is_authenticated else None,
        )

        if is_ajax:
            return JsonResponse({
                'status': 'success' if norm_phone else 'failed',
                'log_id': log_entry.id,
                'whatsapp_url': wa_url,
                'sent_at': log_entry.created_at.strftime('%d-%b-%Y %I:%M %p'),
                'short_message': log_entry.short_message,
            })

        if wa_url:
            return safe_whatsapp_redirect(wa_url)
        else:
            messages.error(request, f"Could not open WhatsApp: Invalid customer phone number '{raw_phone}'.")
            return redirect('loan_detail', loan_number=loan_number)


class LoanBatchWhatsAppHelperMixin:
    """Helper methods to resolve filtered loans queryset for WhatsApp broadcasting."""
    def get_loans_from_params(self, request, params):
        scope = params.get('scope', 'all_filtered')
        loan_ids = params.get('loan_ids')
        if isinstance(loan_ids, str):
            loan_ids = [int(x.strip()) for x in loan_ids.split(',') if x.strip().isdigit()]

        if scope == 'selected' and loan_ids:
            qs = Loan.objects.filter(id__in=loan_ids)
            qs = self.filter_queryset_by_branches(qs, branch_field_name='branch')
            if request.user.organization:
                qs = qs.filter(branch__organization=request.user.organization)
            return qs.select_related('customer', 'branch', 'scheme')

        # Otherwise, resolve all loans matching the current filter parameters
        qs = Loan.objects.all()
        qs = self.filter_queryset_by_branches(qs, branch_field_name='branch')
        if request.user.organization:
            qs = qs.filter(branch__organization=request.user.organization)

        # Status filter
        status = params.get('status')
        if status:
            qs = qs.filter(status=status)

        # Scheme filter
        scheme_id = params.get('scheme')
        if scheme_id:
            qs = qs.filter(scheme_id=scheme_id)

        # Search filter
        search = params.get('search')
        if search:
            search = search.strip()
            search_terms = search.split()
            search_filter = (
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__phone__icontains=search) |
                Q(loan_number__icontains=search) |
                Q(loanitem__item__name__icontains=search)
            )
            if len(search_terms) > 1:
                multi_q = Q()
                for term in search_terms:
                    multi_q &= (
                        Q(customer__first_name__icontains=term) |
                        Q(customer__last_name__icontains=term) |
                        Q(customer__phone__icontains=term) |
                        Q(loan_number__icontains=term) |
                        Q(loanitem__item__name__icontains=term)
                    )
                search_filter = search_filter | multi_q
            qs = qs.filter(search_filter).distinct()

        # Date range filter
        date_range = params.get('date_range')
        today = timezone.now().date()
        if date_range == 'today':
            qs = qs.filter(issue_date=today)
        elif date_range == 'this_week':
            week_start = today - timezone.timedelta(days=today.weekday())
            qs = qs.filter(issue_date__gte=week_start)
        elif date_range == 'this_month':
            qs = qs.filter(issue_date__year=today.year, issue_date__month=today.month)
        elif date_range == 'this_year':
            qs = qs.filter(issue_date__year=today.year)

        # Filter type (overdue, due_soon, etc.)
        filter_type = params.get('filter_type')
        if filter_type == 'overdue':
            qs = qs.filter(status='active', due_date__lt=today)
        elif filter_type == 'due_soon':
            qs = qs.filter(status='active', due_date__gte=today, due_date__lte=today + timezone.timedelta(days=30))
        elif filter_type == 'tiered':
            qs = qs.filter(
                scheme__interest_rate_structure__isnull=False
            ).exclude(scheme__interest_rate_structure={})
        elif filter_type == 'due_plus_5':
            qs = qs.filter(status='active', due_date__gte=today, due_date__lte=today + timezone.timedelta(days=5))
        elif filter_type == 'due_minus_5':
            qs = qs.filter(status='active', due_date__gte=today - timezone.timedelta(days=5), due_date__lt=today)
        elif filter_type == 'due_window_5':
            qs = qs.filter(status='active', due_date__gte=today - timezone.timedelta(days=5), due_date__lte=today + timezone.timedelta(days=5))

        return qs.select_related('customer', 'branch', 'scheme').order_by('-due_date')


class LoanBatchWhatsAppPreviewView(LoginRequiredMixin, RoleBranchAccessMixin, LoanBatchWhatsAppHelperMixin, View):
    """
    Returns live preview of recipients and sample message for bulk WhatsApp notifications.
    """
    def get(self, request):
        return self._process(request, request.GET)

    def post(self, request):
        import json
        try:
            body = json.loads(request.body.decode('utf-8'))
        except Exception:
            body = request.POST
        return self._process(request, body)

    def _process(self, request, params):
        from transactions.services_whatsapp import (
            build_smart_loan_whatsapp_message,
            normalize_phone_number,
            _get_total_payable,
            _compute_days_left,
            get_whatsapp_link,
        )
        from transactions.services_whatsapp_automator import is_whatsapp_paired

        notification_type = params.get('notification_type', 'auto')
        custom_template = params.get('custom_template', '')
        lang = params.get('lang')
        if not lang or lang == 'auto':
            lang = getattr(request, 'LANGUAGE_CODE', 'ta')

        loans_qs = self.get_loans_from_params(request, params)
        total_count = loans_qs.count()

        # Prepare summary preview of first 50 loans
        sample_loans = list(loans_qs[:50])
        loans_preview = []
        for l in sample_loans:
            c = getattr(l, 'customer', None)
            raw_phone = getattr(c, 'phone', '') or ''
            norm_phone = normalize_phone_number(raw_phone)
            days_left, is_overdue = _compute_days_left(l)
            tot_due, _ = _get_total_payable(l)
            loans_preview.append({
                'id': l.id,
                'loan_number': l.loan_number,
                'customer_name': f"{getattr(c, 'first_name', '')} {getattr(c, 'last_name', '')}".strip() or "Customer",
                'phone': raw_phone,
                'is_phone_valid': bool(norm_phone),
                'due_date': l.due_date.strftime('%d/%m/%Y') if l.due_date else 'N/A',
                'is_overdue': is_overdue,
                'days_left': days_left,
                'total_due': float(tot_due),
                'status': l.status,
            })

        # Sample rendered message
        sample_msg = ""
        if sample_loans:
            sample_msg = build_smart_loan_whatsapp_message(
                loan=sample_loans[0],
                notification_type=notification_type,
                custom_template=custom_template,
                lang=lang,
                request_user=request.user,
            )

        return JsonResponse({
            'status': 'success',
            'total_count': total_count,
            'is_whatsapp_paired': is_whatsapp_paired(),
            'sample_message': sample_msg,
            'loans_preview': loans_preview,
        })


class LoanBatchWhatsAppDispatchView(LoginRequiredMixin, RoleBranchAccessMixin, LoanBatchWhatsAppHelperMixin, View):
    """
    Executes bulk WhatsApp dispatch across filtered loans or generates direct links queue.
    """
    def post(self, request):
        import json
        from transactions.services_whatsapp import (
            build_smart_loan_whatsapp_message,
            normalize_phone_number,
            get_whatsapp_link,
            send_pywhatkit_async,
        )
        from transactions.services_whatsapp_automator import (
            send_batch_loans_whatsapp_automated,
            is_whatsapp_paired,
        )

        try:
            params = json.loads(request.body.decode('utf-8'))
        except Exception:
            params = request.POST

        notification_type = params.get('notification_type', 'auto')
        custom_template = params.get('custom_template', '')
        lang = params.get('lang')
        if not lang or lang == 'auto':
            lang = getattr(request, 'LANGUAGE_CODE', 'ta')
        dispatch_mode = params.get('dispatch_mode', 'headless_automated')  # 'headless_automated' | 'links' | 'pywhatkit'

        loans_qs = self.get_loans_from_params(request, params)
        loans = list(loans_qs)

        if not loans:
            return JsonResponse({
                'status': 'error',
                'message': 'No loans found matching the selected filters/criteria.',
                'sent': 0,
                'failed': 0,
                'total': 0,
            })

        if dispatch_mode == 'headless_automated':
            if not is_whatsapp_paired():
                from transactions.models import LoanWhatsAppLog
                for l in loans:
                    try:
                        c = getattr(l, 'customer', None)
                        raw_phone = getattr(c, 'phone', '') or ''
                        msg = build_smart_loan_whatsapp_message(
                            loan=l,
                            notification_type=notification_type,
                            custom_template=custom_template,
                            lang=lang,
                            request_user=request.user,
                        )
                        LoanWhatsAppLog.objects.create(
                            loan=l,
                            customer=c,
                            recipient_phone=raw_phone,
                            notification_type=notification_type or 'automated_notice',
                            status='failed',
                            message_content=msg,
                            error_message='WhatsApp session is not paired. Please link device first.',
                            channel='automated_browser',
                            sent_by=request.user if request.user.is_authenticated else None,
                        )
                    except Exception:
                        pass

                return JsonResponse({
                    'status': 'not_paired',
                    'message': 'WhatsApp session is not paired yet. Please scan QR code to pair first.',
                    'total': len(loans),
                })

            res = send_batch_loans_whatsapp_automated(
                loans=loans,
                notification_type=notification_type,
                custom_template=custom_template,
                user=request.user,
                lang=lang,
                delay_between_seconds=2,
                headless=True,
            )
            return JsonResponse({
                'status': 'success' if not res.get('error') else 'partial',
                'sent': res.get('sent', 0),
                'failed': res.get('failed', 0),
                'total': res.get('total', len(loans)),
                'details': res.get('details', []),
                'message': res.get('error') or f"Successfully dispatched WhatsApp notifications to {res.get('sent', 0)} borrowers.",
            })

        elif dispatch_mode == 'pywhatkit':
            from transactions.models import LoanWhatsAppLog
            sent_count = 0
            failed_count = 0
            details = []
            for l in loans:
                c = getattr(l, 'customer', None)
                raw_phone = getattr(c, 'phone', '') or ''
                norm_phone = normalize_phone_number(raw_phone)
                msg = build_smart_loan_whatsapp_message(
                    loan=l,
                    notification_type=notification_type,
                    custom_template=custom_template,
                    lang=lang,
                    request_user=request.user,
                )
                if norm_phone:
                    send_pywhatkit_async(norm_phone, msg)
                    LoanWhatsAppLog.objects.create(
                        loan=l,
                        customer=c,
                        recipient_phone=norm_phone,
                        notification_type=notification_type or 'pywhatkit_blast',
                        status='sent',
                        message_content=msg,
                        channel='pywhatkit',
                        sent_by=request.user if request.user.is_authenticated else None,
                    )
                    sent_count += 1
                    details.append({'loan_no': l.loan_number, 'customer': str(c), 'status': 'SENT', 'phone': norm_phone})
                else:
                    LoanWhatsAppLog.objects.create(
                        loan=l,
                        customer=c,
                        recipient_phone=raw_phone,
                        notification_type=notification_type or 'pywhatkit_blast',
                        status='failed',
                        message_content=msg,
                        error_message=f"Invalid phone number '{raw_phone}'",
                        channel='pywhatkit',
                        sent_by=request.user if request.user.is_authenticated else None,
                    )
                    failed_count += 1
                    details.append({'loan_no': l.loan_number, 'customer': str(c), 'status': 'FAILED', 'error': 'Invalid phone'})

            return JsonResponse({
                'status': 'success',
                'sent': sent_count,
                'failed': failed_count,
                'total': len(loans),
                'details': details,
                'message': f"PyWhatKit Auto-Blast scheduled for {len(loans)} loans in background.",
            })

        # Direct Web Link / Queue Mode
        links_queue = []
        for l in loans:
            c = getattr(l, 'customer', None)
            raw_phone = getattr(c, 'phone', '') or ''
            norm_phone = normalize_phone_number(raw_phone)
            msg = build_smart_loan_whatsapp_message(
                loan=l,
                notification_type=notification_type,
                custom_template=custom_template,
                lang=lang,
                request_user=request.user,
            )
            track_url = reverse('loan_track_whatsapp_click', kwargs={'loan_number': l.loan_number}) + f"?type={notification_type}&redirect=1"
            wa_link = get_whatsapp_link(norm_phone, msg) if norm_phone else ''
            links_queue.append({
                'loan_number': l.loan_number,
                'customer_name': f"{getattr(c, 'first_name', '')} {getattr(c, 'last_name', '')}".strip(),
                'phone': raw_phone,
                'link': track_url if norm_phone else '',
                'direct_link': wa_link,
                'is_valid': bool(norm_phone),
                'message': msg,
            })

        return JsonResponse({
            'status': 'links_ready',
            'total': len(loans),
            'queue': links_queue,
            'message': f"Generated WhatsApp launch links for {len(loans)} loans.",
        })



class LoanDetailView(LoginRequiredMixin, RoleBranchAccessMixin, DetailView):
    model = Loan
    template_name = 'transactions/loan_detail.html'
    context_object_name = 'loan'
    slug_field = 'loan_number'
    slug_url_kwarg = 'loan_number'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        # enforce branch access
        self.check_object_branch_access(obj, branch_attr='branch')
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan = self.get_object()
        
        # Add payments and other related data to context
        context['payments'] = loan.payments.all().order_by('-payment_date')
        context['extensions'] = loan.extensions.all().order_by('-extension_date')
        
        # Fetch active vs released loan items
        all_loan_items = list(loan.loanitem_set.all().select_related('item'))
        if not all_loan_items:
            all_loan_items = list(LoanItem.objects.filter(loan=loan).select_related('item'))
            
        active_loan_items = [it for it in all_loan_items if it.status != 'released']
        released_loan_items = [it for it in all_loan_items if it.status == 'released']

        context['loan_items'] = all_loan_items
        context['active_loan_items'] = active_loan_items
        context['released_loan_items'] = released_loan_items
        
        # Calculate active in-vault collateral totals
        total_items_qty = sum(it.quantity or 1 for it in active_loan_items)
        total_gross_wt = sum(it.gross_weight or Decimal('0.000') for it in active_loan_items)
        total_net_wt = sum(it.net_weight or Decimal('0.000') for it in active_loan_items)
        total_stone_wt = sum(it.stone_weight or Decimal('0.000') for it in active_loan_items)
        total_collateral_valuation = sum(it.item_valuation for it in active_loan_items)
        
        context['total_items_qty'] = total_items_qty
        context['total_gross_wt'] = total_gross_wt
        context['total_net_wt'] = total_net_wt
        context['total_stone_wt'] = total_stone_wt
        context['total_collateral_valuation'] = total_collateral_valuation

        # Live LTV based on current principal and active collateral
        if total_collateral_valuation > Decimal('0.00'):
            context['current_ltv'] = ((loan.principal_amount / total_collateral_valuation) * Decimal('100')).quantize(Decimal('0.01'))
        else:
            context['current_ltv'] = Decimal('0.00')

        # Live Accrued Interest & Net Payable Today
        try:
            from transactions.services_partial_release import get_loan_current_interest_due
            today_interest_due = get_loan_current_interest_due(loan)
            context['today_interest_due'] = today_interest_due
            context['today_net_payable'] = loan.principal_amount + today_interest_due
        except Exception:
            context['today_interest_due'] = Decimal('0.00')
            context['today_net_payable'] = loan.principal_amount
        
        # Process item photos for the template using centralized function
        context['item_photos_list'] = process_item_photos_for_display(loan.item_photos)
        context['tiered_rates'] = get_loan_tiered_rates(loan)

        # WhatsApp tracked dispatch links for seamless 1-click staff action & audit logging
        try:
            from transactions.services_whatsapp import normalize_phone_number
            cust_phone = getattr(loan.customer, 'phone', '')
            norm_phone = normalize_phone_number(cust_phone)
            
            track_base = reverse('loan_track_whatsapp_click', kwargs={'loan_number': loan.loan_number})
            context['whatsapp_reminder_link'] = f"{track_base}?type=reminder&redirect=1" if norm_phone else ''
            context['whatsapp_demand_link'] = f"{track_base}?type=demand_notice&redirect=1" if norm_phone else ''
            context['whatsapp_chat_link'] = f"{track_base}?type=custom_chat&redirect=1" if norm_phone else ''
            context['customer_phone_normalized'] = norm_phone
        except Exception:
            context['whatsapp_reminder_link'] = ''
            context['whatsapp_demand_link'] = ''
            context['whatsapp_chat_link'] = ''
            context['customer_phone_normalized'] = ''

        # Auto-sync legacy IRAC alert logs into LoanWhatsAppLog if not present
        try:
            from transactions.models import LoanWhatsAppLog
            for irac in loan.irac_alert_logs.all():
                if not loan.whatsapp_logs.filter(created_at=irac.created_at).exists():
                    LoanWhatsAppLog.objects.create(
                        loan=loan,
                        customer=irac.customer,
                        recipient_phone=getattr(irac.customer, 'phone', '') or '',
                        notification_type=f"irac_{irac.irac_bucket.lower()}",
                        status=irac.status.lower() if irac.status else 'sent',
                        message_content=irac.message_sent or f"Regulatory IRAC Alert [{irac.irac_bucket}]",
                        channel=irac.channel or 'whatsapp_web',
                        sent_by=irac.sent_by,
                        created_at=irac.created_at,
                    )
        except Exception:
            pass

        # Auto-sync Marketing Campaign / Blast logs for this customer into LoanWhatsAppLog if not present
        try:
            from transactions.models import MarketingCampaignLog, LoanWhatsAppLog
            from transactions.services_whatsapp import normalize_phone_number
            cust_phone = getattr(loan.customer, 'phone', '') or ''
            norm_phone = normalize_phone_number(cust_phone)
            phone_variants = [p for p in [cust_phone, norm_phone, norm_phone[-10:] if len(norm_phone) >= 10 else ''] if p]
            if phone_variants:
                m_logs = MarketingCampaignLog.objects.filter(recipient_phone__in=phone_variants)
                for m in m_logs:
                    if not loan.whatsapp_logs.filter(created_at=m.created_at).exists():
                        LoanWhatsAppLog.objects.create(
                            loan=loan,
                            customer=loan.customer,
                            recipient_phone=m.recipient_phone,
                            notification_type='marketing_broadcast',
                            status=m.status.lower() if m.status else 'sent',
                            message_content=f"[{m.campaign_name}] {m.message_snippet or ''}",
                            channel=m.channel or 'whatsapp_blast',
                            sent_by=m.sent_by,
                            created_at=m.created_at,
                        )
        except Exception:
            pass

        # WhatsApp dispatch and delivery history logs
        context['whatsapp_logs'] = loan.whatsapp_logs.all().select_related('sent_by', 'customer').order_by('-created_at')
            
        return context


class UpdateGoldStatusView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    def post(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        self.check_object_branch_access(loan, branch_attr='branch')
        
        loan.gold_location = request.POST.get('gold_location')
        
        rep_date = request.POST.get('repledge_date')
        if rep_date:
            loan.repledge_date = rep_date
        else:
            loan.repledge_date = None
            
        repledge_amt = request.POST.get('repledge_amount')
        if repledge_amt:
            try:
                loan.repledge_amount = Decimal(repledge_amt)
            except Exception:
                loan.repledge_amount = None
        else:
            loan.repledge_amount = None
            
        loan.gold_status_others = request.POST.get('gold_status_others')
        loan.save()
        
        messages.success(request, "Gold current status updated successfully.")
        return redirect('loan_detail', loan_number=loan_number)


class LoanCreateView(LoginRequiredMixin, RoleBranchAccessMixin, CreateView):
    model = Loan
    form_class = LoanForm
    template_name = 'transactions/loan_form.html'
    
    def get_success_url(self):
        return reverse('loan_detail', kwargs={'loan_number': self.object.loan_number})
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        """Set initial values for the form, including pre-selected customer"""
        initial = super().get_initial()
        
        # Handle customer_id from URL parameter (from customer detail/list pages)
        customer_id = self.request.GET.get('customer_id')
        if customer_id:
            try:
                from accounts.models import Customer
                customer = Customer.objects.get(id=customer_id)
                # Verify the customer belongs to the user's organization/branch
                user = self.request.user
                if user.organization:
                    if customer.branch and customer.branch.organization == user.organization:
                        initial['customer'] = customer
                        # Also set the branch to customer's branch if available
                        if customer.branch:
                            initial['branch'] = customer.branch
                elif user.is_superuser:
                    # Superusers can access any customer
                    initial['customer'] = customer
                    if customer.branch:
                        initial['branch'] = customer.branch
            except Customer.DoesNotExist:
                # Customer not found, ignore the parameter
                pass
        
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add customer information to context if pre-selected
        customer_id = self.request.GET.get('customer_id')
        if customer_id:
            try:
                from accounts.models import Customer
                customer = Customer.objects.get(id=customer_id)
                context['preselected_customer'] = customer
                context['customer_preselected'] = True
            except Customer.DoesNotExist:
                pass
        
        # Process item photos for form if editing existing loan or restoring from failed POST
        if self.object and self.object.item_photos:
            context['item_photos_list'] = process_item_photos_for_display(self.object.item_photos)
        elif self.request.method == 'POST':
            post_item_photos = self.request.POST.get('item_photos', '')
            if post_item_photos:
                context['item_photos_list'] = process_item_photos_for_display(post_item_photos)
            post_customer_face = self.request.POST.get('customer_face_capture', '')
            if post_customer_face:
                context['submitted_customer_face_capture'] = post_customer_face
        return context
    
    def form_valid(self, form):
        # Handle photo processing during loan creation
        item_photos_data = self.request.POST.get('item_photos', '')
        customer_face_capture = self.request.POST.get('customer_face_capture', '')
        
        # Save photos directly to database
        if item_photos_data:
            try:
                # Attempt to parse as JSON array
                photos_list = json.loads(item_photos_data)
                # Ensure it's a list and remove duplicates while preserving order
                if isinstance(photos_list, list):
                    unique_photos = []
                    seen = set()
                    for p in photos_list:
                        if p not in seen:
                            unique_photos.append(p)
                            seen.add(p)
                    form.instance.item_photos = json.dumps(unique_photos)
                else:
                    # If not a list, treat as single photo
                    form.instance.item_photos = item_photos_data
            except json.JSONDecodeError:
                # Not a JSON string, treat as single photo
                form.instance.item_photos = item_photos_data
        if customer_face_capture:
            form.instance.customer_face_capture = customer_face_capture
            
        # Set the branch and created_by
        # Assign branch: use user's branch if set, else fall back to first
        # branch in the user's organization (covers superusers / admin accounts
        # that are not tied to a specific branch).
        if self.request.user.branch:
            form.instance.branch = self.request.user.branch
        elif not hasattr(form.instance, 'branch') or form.instance.branch_id is None:
            from branches.models import Branch
            user = self.request.user
            fallback_branch = None
            if hasattr(user, 'organization') and user.organization:
                fallback_branch = Branch.objects.filter(
                    organization=user.organization, is_active=True
                ).first()
            if fallback_branch is None and user.is_superuser:
                fallback_branch = Branch.objects.filter(is_active=True).first()
            if fallback_branch:
                form.instance.branch = fallback_branch
        form.instance.created_by = self.request.user
        
        # Ensure interest_rate is set from the cleaned data
        if 'interest_rate' in form.cleaned_data and form.cleaned_data['interest_rate']:
            form.instance.interest_rate = form.cleaned_data['interest_rate']
        elif form.cleaned_data.get('scheme'):
            # Fallback: Set interest rate from scheme if not in cleaned data
            form.instance.interest_rate = form.cleaned_data['scheme'].interest_rate
        else:
            # Last fallback: Use default value from model
            form.instance.interest_rate = Decimal('12.00')

        # Loan Creation Maker-Checker & OTP Workflow
        form.instance.maker = self.request.user
        form.instance.status = 'pending_approval'
        form.instance.is_otp_verified = False
        form.instance.generate_otp(save=False)
        
        response = super().form_valid(form)
        try:
            from accounts.models import LoanEditLog
            try:
                from django.forms.models import model_to_dict
                new_data = model_to_dict(
                    self.object,
                    exclude=['item_photos', 'customer_face_capture', 'loan_document'],
                )
                new_data = {k: str(v) for k, v in new_data.items()}
            except Exception:
                new_data = None
            LoanEditLog.objects.create(
                loan=self.object,
                edited_by=self.request.user,
                change_type='create',
                description=f'Loan initiated by Maker {self.request.user.get_full_name() or self.request.user.username} (Pending Customer OTP & Manager Approval)',
                changes={'new': new_data} if new_data is not None else None
            )
        except Exception:
            pass

        # Dispatch automated customer OTP WhatsApp message in background
        try:
            from transactions.services_whatsapp_automator import send_loan_otp_whatsapp_async
            send_loan_otp_whatsapp_async(self.object.id, user_id=self.request.user.id)
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to spawn background loan OTP dispatch: %s", e)

        messages.success(
            self.request,
            f"Gold Loan Application #{self.object.loan_number} initiated! A 6-digit identity OTP has been dispatched to {self.object.customer.full_name}'s mobile ({self.object.customer.phone}). Please verify customer OTP before manager approval."
        )
        return response


class LoanUpdateView(LoginRequiredMixin, RoleBranchAccessMixin, UpdateView):
    model = Loan
    form_class = LoanForm
    template_name = 'transactions/loan_form.html'
    slug_field = 'loan_number'
    slug_url_kwarg = 'loan_number'
    
    def get_success_url(self):
        return reverse('loan_detail', kwargs={'loan_number': self.object.loan_number})
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        if self.object:
            dist_val = self.object.distribution_amount
            if dist_val is None and self.object.principal_amount is not None:
                dist_val = self.object.principal_amount - (self.object.processing_fee or 0)
            initial['processing_fee'] = self.object.processing_fee or 0
            initial['distribution_amount'] = dist_val
            deduct_val = self.object.distribution_amount_with_deduction
            if deduct_val is not None:
                try:
                    deduct_val = int(round(float(deduct_val)))
                except (ValueError, TypeError):
                    pass
            initial['distribution_amount_with_deduction'] = deduct_val
        return initial

        # Process item photos for form editing or restoring from failed POST
        if self.object and self.object.item_photos:
            context['item_photos_list'] = process_item_photos_for_display(self.object.item_photos)
        elif self.request.method == 'POST':
            post_item_photos = self.request.POST.get('item_photos', '')
            if post_item_photos:
                context['item_photos_list'] = process_item_photos_for_display(post_item_photos)
            post_customer_face = self.request.POST.get('customer_face_capture', '')
            if post_customer_face:
                context['submitted_customer_face_capture'] = post_customer_face
        return context
    
    def form_valid(self, form):
        # Handle photo processing during loan update
        item_photos_data = self.request.POST.get('item_photos', '')
        customer_face_capture = self.request.POST.get('customer_face_capture', '')
        
        # Save photos directly to database
        if item_photos_data:
            form.instance.item_photos = item_photos_data
        if customer_face_capture:
            form.instance.customer_face_capture = customer_face_capture
        
        # Track who is editing the loan
        form.instance._edited_by = self.request.user
            
        # Capture previous state for description and field diffs
        try:
            orig = Loan.objects.get(pk=form.instance.pk)
        except Exception:
            orig = None

        # Save the form (updates the loan)
        response = super().form_valid(form)
        try:
            from accounts.models import LoanEditLog
            desc = 'Loan updated'
            if orig:
                desc = f'Loan updated by {self.request.user.get_full_name() or self.request.user.username}'

            # Build field-level diff using form.changed_data when available
            changes = None
            try:
                changed_fields = getattr(form, 'changed_data', None)
                if changed_fields:
                    changes = {}
                    for field in changed_fields:
                        try:
                            old_val = getattr(orig, field)
                        except Exception:
                            old_val = None
                        try:
                            new_val = getattr(self.object, field)
                        except Exception:
                            new_val = None
                        # Convert to serializable strings
                        changes[field] = {
                            'old': str(old_val) if old_val is not None else None,
                            'new': str(new_val) if new_val is not None else None,
                        }
            except Exception:
                changes = None

            LoanEditLog.objects.create(
                loan=self.object,
                edited_by=self.request.user,
                change_type='update',
                description=desc,
                changes=changes
            )
        except Exception:
            pass

        messages.success(self.request, 'Loan updated successfully!')
        return response

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        # enforce branch access
        self.check_object_branch_access(obj, branch_attr='branch')
        return obj

class LoanDeleteView(LoginRequiredMixin, ManagerPermissionMixin, RoleBranchAccessMixin, DeleteView):
    model = Loan
    template_name = 'transactions/loan_confirm_delete.html'
    slug_field = 'loan_number'
    slug_url_kwarg = 'loan_number'
    context_object_name = 'loan'
    success_url = reverse_lazy('loan_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        loan_number = self.object.loan_number
        # Log deletion
        try:
            from accounts.models import LoanEditLog
            try:
                from django.forms.models import model_to_dict
                old_data = model_to_dict(self.object)
            except Exception:
                old_data = None
            LoanEditLog.objects.create(
                loan=self.object,
                edited_by=request.user,
                change_type='delete',
                description=f'Loan deleted by {request.user.get_full_name() or request.user.username}',
                changes={'old': old_data} if old_data is not None else None
            )
        except Exception:
            pass

        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'Loan {loan_number} has been deleted successfully.')
        return response


class LoanEditLogsView(LoginRequiredMixin, RoleBranchAccessMixin, DetailView):
    """Display edit history for a loan"""
    model = Loan
    template_name = 'transactions/loan_edit_logs.html'
    slug_field = 'loan_number'
    slug_url_kwarg = 'loan_number'
    context_object_name = 'loan'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from accounts.models import LoanEditLog
        
        # Get all edit logs for this loan, ordered by date descending
        edit_logs = LoanEditLog.objects.filter(loan=self.object).order_by('-edited_at')
        context['edit_logs'] = edit_logs
        context['total_edits'] = edit_logs.count()
        
        return context

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        # enforce branch access
        self.check_object_branch_access(obj, branch_attr='branch')
        return obj


class PaymentCreateView(LoginRequiredMixin, RoleBranchAccessMixin, CreateView):
    model = Payment
    form_class = PaymentRecordForm
    template_name = 'transactions/payment_form.html'
    
    def get_initial(self):
        """Set default values for form fields"""
        initial = super().get_initial()
        # Set payment_date to today's date
        initial['payment_date'] = timezone.now().date()
        # Default payment method to cash
        initial['payment_method'] = 'cash'
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan_number = self.kwargs.get('loan_number')
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # enforce branch access
        self.check_object_branch_access(loan, branch_attr='branch')
        context['loan'] = loan

        # Today's accrued interest & net payable for live calculator
        try:
            from transactions.services_partial_release import get_loan_current_interest_due
            today_interest = get_loan_current_interest_due(loan)
            context['today_interest'] = today_interest
            context['today_net_payable'] = loan.principal_amount + today_interest
            context['loan_principal'] = loan.principal_amount
            context['remaining_balance'] = loan.principal_amount + today_interest
        except Exception:
            context['today_interest'] = Decimal('0.00')
            context['today_net_payable'] = loan.principal_amount
            context['loan_principal'] = loan.principal_amount
            context['remaining_balance'] = loan.principal_amount

        # Payment history
        context['payments'] = loan.payments.order_by('-payment_date')[:10]

        return context
    
    def form_valid(self, form):
        loan_number = self.kwargs.get('loan_number')
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # enforce branch access
        self.check_object_branch_access(loan, branch_attr='branch')
        
        # Check if loan can accept payments
        if loan.status not in ['active', 'overdue']:
            messages.error(self.request, f'Cannot record payment for loan {loan_number}. Current status: {loan.get_status_display()}')
            return redirect('loan_detail', loan_number=loan_number)
        
        # Section 269ST Compliance: Daily cash repayment ceiling of ₹1,99,999 per customer across all branches
        payment_method = form.cleaned_data.get('payment_method')
        payment_date = form.cleaned_data.get('payment_date') or timezone.now().date()
        payment_amount = form.cleaned_data.get('amount') or Decimal('0.00')

        if str(payment_method).lower() == 'cash':
            from django.db.models import Sum
            same_day_cash = Payment.objects.filter(
                loan__customer=loan.customer,
                payment_date=payment_date,
                payment_method__iexact='cash'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            if same_day_cash + Decimal(str(payment_amount)) >= Decimal('200000.00'):
                max_allowed = max(Decimal('0.00'), Decimal('199999.00') - same_day_cash)
                form.add_error(
                    'payment_method',
                    f"Section 269ST Statutory Violation: Total daily cash repayments from a customer across all branches cannot reach or exceed ₹2,00,000 (Statutory maximum cash allowed per day is ₹1,99,999). "
                    f"Today's existing cash repayments for {loan.customer.full_name}: ₹{same_day_cash:,.2f}. "
                    f"Maximum cash remaining for today: ₹{max_allowed:,.2f}. "
                    f"Please select a digital payment mode (Bank Transfer, UPI, Cheque, or NetBanking)."
                )
                return self.form_invalid(form)

        form.instance.loan = loan
        form.instance.received_by = self.request.user
        
        # Calculate remaining balance before this payment and prevent excess payment
        try:
            from transactions.services_partial_release import get_loan_current_interest_due
            current_interest_due = get_loan_current_interest_due(loan)
            remaining_balance = loan.principal_amount + current_interest_due
            if payment_amount > remaining_balance:
                form.add_error(
                    'amount',
                    f"Payment amount of ₹{payment_amount:,.2f} exceeds the outstanding balance of ₹{remaining_balance:,.2f}. "
                    f"Maximum payable amount is ₹{remaining_balance:,.2f}."
                )
                return self.form_invalid(form)
            
            # Check if this payment will fully settle the loan
            will_close_loan = (payment_amount == remaining_balance and remaining_balance > 0)
        except Exception:
            will_close_loan = False
            remaining_balance = Decimal('0.00')

        try:
            from transactions.services_partial_release import get_loan_current_interest_due
            current_interest_due = get_loan_current_interest_due(loan)

            interest_paid = min(payment_amount, current_interest_due)
            principal_paid = max(Decimal('0.00'), payment_amount - current_interest_due)

            if not form.instance.notes:
                form.instance.notes = f"Part Payment (Interest: ₹{interest_paid:,.2f}, Principal: ₹{principal_paid:,.2f})"

            # Save the payment first
            response = super().form_valid(form)

            # Update Loan Financials: reduce principal_amount if payment exceeded accrued interest
            old_principal = loan.principal_amount
            if principal_paid > Decimal('0.00'):
                loan.principal_amount = max(Decimal('0.00'), loan.principal_amount - principal_paid)
                if interest_paid > Decimal('0.00'):
                    loan.accrued_interest = max(Decimal('0.00'), Decimal(str(loan.accrued_interest)) - interest_paid)
            elif interest_paid > Decimal('0.00'):
                loan.accrued_interest = max(Decimal('0.00'), Decimal(str(loan.accrued_interest)) - interest_paid)

            # If payment fully settles the loan (or principal reduced to 0), close it
            if will_close_loan or loan.principal_amount <= Decimal('0.00'):
                loan.status = 'closed'
                loan.closure_date = timezone.now().date()
                loan.closed_by = self.request.user
                loan.save()

                try:
                    from accounts.models import LoanEditLog
                    LoanEditLog.objects.create(
                        loan=loan,
                        edited_by=self.request.user,
                        change_type='payment',
                        description=f'Loan closed by full payment of ₹{payment_amount:,.2f}',
                        changes={
                            'status': {'old': 'active', 'new': 'closed'},
                            'principal_amount': {'old': str(old_principal), 'new': '0.00'},
                            'payment_amount': {'old': None, 'new': str(payment_amount)}
                        }
                    )
                except Exception:
                    pass

                messages.success(
                    self.request,
                    f'Payment of ₹{payment_amount:,.2f} recorded successfully! Loan {loan_number} has been fully settled and closed.'
                )
            else:
                loan.save()
                try:
                    from accounts.models import LoanEditLog
                    LoanEditLog.objects.create(
                        loan=loan,
                        edited_by=self.request.user,
                        change_type='payment',
                        description=f'Part Payment of ₹{payment_amount:,.2f} (Interest: ₹{interest_paid:,.2f}, Principal: ₹{principal_paid:,.2f})',
                        changes={
                            'principal_amount': {'old': str(old_principal), 'new': str(loan.principal_amount)},
                            'payment_amount': {'old': None, 'new': str(payment_amount)}
                        }
                    )
                except Exception:
                    pass

                messages.success(
                    self.request,
                    f'Part Payment of ₹{payment_amount:,.2f} recorded! Interest cleared: ₹{interest_paid:,.2f}, Principal reduced from ₹{old_principal:,.2f} to ₹{loan.principal_amount:,.2f}.'
                )

            return response
            
        except Exception as e:
            messages.error(self.request, f'Error processing payment: {str(e)}')
            return redirect('loan_detail', loan_number=loan_number)
    
    def get_success_url(self):
        return reverse('loan_detail', kwargs={'loan_number': self.kwargs.get('loan_number')})


class PaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = 'transactions/interest_paid_list.html'
    context_object_name = 'payments'
    paginate_by = 20


class PaymentDetailView(LoginRequiredMixin, DetailView):
    model = Payment
    template_name = 'transactions/payment_detail.html'
    context_object_name = 'payment'


class LoanExtensionCreateView(LoginRequiredMixin, RoleBranchAccessMixin, CreateView):
    model = LoanExtension
    form_class = LoanExtensionForm
    template_name = 'transactions/loan_extension_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan_number = self.kwargs.get('loan_number')
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # enforce branch access
        self.check_object_branch_access(loan, branch_attr='branch')
        context['loan'] = loan
        return context
    
    def form_valid(self, form):
        loan_number = self.kwargs.get('loan_number')
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # enforce branch access
        self.check_object_branch_access(loan, branch_attr='branch')
        form.instance.loan = loan
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Loan extension created successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('loan_detail', kwargs={'loan_number': self.kwargs.get('loan_number')})


class LoanForecloseView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    def get(self, request, loan_number):
        """Handle GET request - show confirmation page"""
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # enforce branch access
        self.check_object_branch_access(loan, branch_attr='branch')

        # Check if loan can be foreclosed
        if loan.status not in ['active', 'overdue']:
            messages.error(request, f'Loan {loan_number} cannot be foreclosed. Current status: {loan.get_status_display()}')
            return redirect('loan_detail', loan_number=loan_number)

        context = {
            'loan': loan,
            'confirm_action': 'foreclose'
        }
        return render(request, 'transactions/loan_foreclose_confirm.html', context)

    def post(self, request, loan_number):
        """Handle POST request - actually foreclose the loan"""
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # enforce branch access
        self.check_object_branch_access(loan, branch_attr='branch')

        # Check if loan can be foreclosed
        if loan.status not in ['active', 'overdue']:
            messages.error(request, f'Loan {loan_number} cannot be foreclosed. Current status: {loan.get_status_display()}')
            return redirect('loan_detail', loan_number=loan_number)

        # Update loan status
        loan.status = 'foreclosed'
        loan.foreclosure_date = timezone.now().date()
        loan.foreclosed_by = request.user
        loan.save()

        # Log foreclose action
        try:
            from accounts.models import LoanEditLog
            LoanEditLog.objects.create(
                loan=loan,
                edited_by=request.user,
                change_type='foreclose',
                description=f'Loan foreclosed by {request.user.get_full_name() or request.user.username}',
                changes={'status': {'old': 'active', 'new': 'foreclosed'}}
            )
        except Exception:
            pass

        messages.success(request, f'Loan {loan_number} has been successfully foreclosed.')
        return redirect('loan_detail', loan_number=loan_number)


class LoanDocumentView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    def get(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # enforce branch access
        self.check_object_branch_access(loan, branch_attr='branch')
        # Keep original agreement layout; prefer Chromium rendering for reliable Tamil glyph shaping.
        try:
            return self._generate_browser_pdf(request, loan)
        except Exception as e:
            print(f"Browser PDF generation failed, falling back to xhtml2pdf: {e}")
            return self._generate_xhtml2pdf(request, loan)

    def _find_browser_executable(self):
        """Find an installed Chromium-based browser executable."""
        candidates = [
            shutil.which('chrome'),
            shutil.which('msedge'),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    def _generate_browser_pdf(self, request, loan):
        """Render loan agreement HTML via headless Chromium to get proper Tamil rendering."""
        current_language = getattr(request, 'LANGUAGE_CODE', 'en')
        # Process item photos for PDF using centralized function
        processed_photos = process_item_photos_for_display(loan.item_photos)
        item_photos = []
        for photo in processed_photos:
            if photo.startswith('data:image/'):
                base64_data = photo.split(',')[1] if ',' in photo else photo
                item_photos.append(base64_data)
            else:
                item_photos.append(photo)

        customer_photo = None
        if loan.customer_face_capture:
            if loan.customer_face_capture.startswith('data:image/'):
                customer_photo = loan.customer_face_capture.split(',')[1]
            else:
                customer_photo = loan.customer_face_capture

        loan_items = loan.loanitem_set.exclude(status='released')
        language_context = build_loan_pdf_language_context(loan, current_language)

        # Same filename logic used by template-based method
        from django.utils.text import slugify
        import re

        customer_name = ""
        if loan.customer:
            customer_name = f"{loan.customer.first_name}_{loan.customer.last_name}"
            customer_name = slugify(customer_name).replace('-', '_')

        item_names = []
        for loan_item in loan_items:
            if loan_item.item and loan_item.item.name:
                item_names.append(slugify(loan_item.item.name).replace('-', '_'))
        if not item_names:
            if hasattr(loan, 'item_name') and loan.item_name:
                item_names = [slugify(loan.item_name).replace('-', '_')]
            else:
                item_names = ['gold_item']
        items_part = '_'.join(item_names[:2])

        if customer_name and items_part:
            filename_base = f"{customer_name}_{items_part}_{loan.loan_number}_agreement"
        elif customer_name:
            filename_base = f"{customer_name}_{loan.loan_number}_agreement"
        else:
            filename_base = f"loan_{loan.loan_number}_agreement"
        filename_base = re.sub(r'[^a-zA-Z0-9_-]', '_', filename_base)[:200]
        detailed_filename = f"{filename_base}.pdf"

        context = {
            'loan': loan,
            'loan_items': loan_items,
            'item_photos': item_photos,
            'customer_photo': customer_photo,
            'tamil_font_file_uri': f"file:///{str((settings.BASE_DIR / 'static' / 'fonts' / 'NotoSansTamil-Regular.ttf')).replace(os.sep, '/')}",
            'pdf_renderer': 'browser',
            **language_context,
        }

        template = get_template('transactions/loan_document_pdf.html')
        html = template.render(context)

        browser = self._find_browser_executable()
        if not browser:
            raise RuntimeError("No Chrome/Edge executable found on system")

        tmp_dir = tempfile.mkdtemp(prefix='loan_pdf_')
        html_path = os.path.join(tmp_dir, 'loan_document.html')
        pdf_path = os.path.join(tmp_dir, 'loan_document.pdf')
        profile_dir = os.path.join(tmp_dir, 'profile')
        os.makedirs(profile_dir, exist_ok=True)

        try:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)

            cmd = [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                f"--user-data-dir={profile_dir}",
                "--allow-file-access-from-files",
                "--disable-web-security",
                "--print-to-pdf-no-header",
                f"--print-to-pdf={pdf_path}",
                f"file:///{html_path.replace(os.sep, '/')}",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if result.returncode != 0 or not os.path.exists(pdf_path):
                raise RuntimeError(f"Chromium PDF render failed: {result.stderr or result.stdout}")

            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            if not pdf_bytes:
                raise RuntimeError("Generated PDF is empty")

            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{detailed_filename}"'
            response.write(pdf_bytes)
            return response
        finally:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def _generate_xhtml2pdf(self, request, loan):
        """Fallback method using xhtml2pdf"""
        current_language = getattr(request, 'LANGUAGE_CODE', 'en')
        
        # Process item photos for PDF using centralized function
        processed_photos = process_item_photos_for_display(loan.item_photos)
        
        # Convert photos to base64 format for PDF embedding
        item_photos = []
        for photo in processed_photos:
            if photo.startswith('data:image/'):
                # Extract just the base64 data part (remove data:image/jpeg;base64, prefix)
                base64_data = photo.split(',')[1] if ',' in photo else photo
                item_photos.append(base64_data)
            else:
                # If it's already base64 without prefix, use directly
                item_photos.append(photo)
        
        # Debug: Print photo information
        print(f"Processing loan {loan.loan_number}: Found {len(processed_photos)} processed photos")
        print(f"Raw item_photos data: {loan.item_photos[:100] if loan.item_photos else 'None'}...")
        print(f"Final item_photos for template: {len(item_photos)} photos")
        
        # Process customer photo
        customer_photo = None
        if loan.customer_face_capture:
            if loan.customer_face_capture.startswith('data:image/'):
                customer_photo = loan.customer_face_capture.split(',')[1]
            else:
                customer_photo = loan.customer_face_capture
        
        # Ensure we have loan items (active pledged items)
        loan_items = loan.loanitem_set.exclude(status='released')
        language_context = build_loan_pdf_language_context(loan, current_language)
        print(f"Found {loan_items.count()} loan items")
        
        # Generate detailed filename with customer name and item details
        def generate_loan_document_filename(loan):
            from django.utils.text import slugify
            import re
            
            # Get customer name (clean it for filename)
            customer_name = ""
            if loan.customer:
                customer_name = f"{loan.customer.first_name}_{loan.customer.last_name}"
                customer_name = slugify(customer_name).replace('-', '_')
            
            # Get item names from loan items
            item_names = []
            loan_items = loan.loanitem_set.all()
            for loan_item in loan_items:
                if loan_item.item and loan_item.item.name:
                    item_name = slugify(loan_item.item.name).replace('-', '_')
                    item_names.append(item_name)
            
            # If no items found, use item_name from loan model or default
            if not item_names:
                if hasattr(loan, 'item_name') and loan.item_name:
                    item_name = slugify(loan.item_name).replace('-', '_')
                    item_names = [item_name]
                else:
                    item_names = ['gold_item']
            
            # Combine item names (limit to first 2 items to avoid very long filenames)
            items_part = '_'.join(item_names[:2])
            
            # Create filename: CustomerName_ItemNames_LoanNumber_agreement.pdf
            if customer_name and items_part:
                filename_base = f"{customer_name}_{items_part}_{loan.loan_number}_agreement"
            elif customer_name:
                filename_base = f"{customer_name}_{loan.loan_number}_agreement"
            else:
                filename_base = f"loan_{loan.loan_number}_agreement"
            
            # Clean filename for filesystem compatibility
            filename_base = re.sub(r'[^a-zA-Z0-9_-]', '_', filename_base)
            
            # Limit filename length to avoid filesystem issues
            if len(filename_base) > 200:
                filename_base = filename_base[:200]
            
            return f"{filename_base}.pdf"
        
        context = {
            'loan': loan,
            'loan_items': loan_items,
            'item_photos': item_photos,
            'customer_photo': customer_photo,
            'pdf_renderer': 'xhtml2pdf',
            **language_context,
        }
        
        # Render PDF
        template = get_template('transactions/loan_document_pdf.html')
        html = template.render(context)
        
        response = HttpResponse(content_type='application/pdf')
        
        # Generate detailed filename
        detailed_filename = generate_loan_document_filename(loan)
        response['Content-Disposition'] = f'attachment; filename="{detailed_filename}"'
        
        def link_callback(uri, rel):
            """
            Resolve static/media URIs to absolute filesystem paths for xhtml2pdf.
            Required so Tamil font files under /static/fonts can be loaded.
            """
            parsed = urlparse(uri)
            path = parsed.path or uri
            if path.startswith(settings.STATIC_URL):
                return os.path.join(settings.BASE_DIR, 'static', path.replace(settings.STATIC_URL, '', 1))
            if path.startswith(settings.MEDIA_URL):
                return os.path.join(settings.MEDIA_ROOT, path.replace(settings.MEDIA_URL, '', 1))
            if path.startswith('/static/'):
                return os.path.join(settings.BASE_DIR, 'static', path.replace('/static/', '', 1))
            if path.startswith('/media/'):
                return os.path.join(settings.MEDIA_ROOT, path.replace('/media/', '', 1))
            return uri

        # Register Tamil font directly with reportlab to avoid xhtml2pdf @font-face temp-file issues on Windows.
        try:
            tamil_font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'NotoSansTamil-Regular.ttf')
            if os.path.exists(tamil_font_path):
                pdfmetrics.registerFont(TTFont('NotoSansTamil', tamil_font_path))
        except Exception:
            pass

        pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
        if pisa_status.err:
            return HttpResponse('Error generating PDF', status=500)
        
        return response


class LoanPaymentHistoryDownloadView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    def get(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # enforce branch access
        self.check_object_branch_access(loan, branch_attr='branch')
        format_type = request.GET.get('format', 'csv')
        
        if format_type == 'csv':
            return self.export_csv(loan)
        elif format_type == 'excel':
            return self.export_excel(loan)
        elif format_type == 'pdf':
            return self.export_pdf(loan)
        else:
            return self.export_csv(loan)
    
    def export_csv(self, loan):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="loan_{loan.loan_number}_payment_history.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'Amount', 'Method', 'Reference', 'Notes'])
        
        for payment in loan.payments.all().order_by('-payment_date'):
            writer.writerow([
                payment.payment_date.strftime('%Y-%m-%d'),
                payment.amount,
                payment.get_payment_method_display(),
                payment.reference_number or '',
                payment.notes or ''
            ])
        
        return response
    
    def export_excel(self, loan):
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = f"Loan {loan.loan_number} Payments"
        
        # Headers
        headers = ['Date', 'Amount', 'Method', 'Reference', 'Notes']
        for col, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        
        # Data
        for row_idx, payment in enumerate(loan.payments.all().order_by('-payment_date'), 2):
            worksheet.cell(row=row_idx, column=1, value=payment.payment_date.strftime('%Y-%m-%d'))
            worksheet.cell(row=row_idx, column=2, value=float(payment.amount))
            worksheet.cell(row=row_idx, column=3, value=payment.get_payment_method_display())
            worksheet.cell(row=row_idx, column=4, value=payment.reference_number or '')
            worksheet.cell(row=row_idx, column=5, value=payment.notes or '')
        
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="loan_{loan.loan_number}_payment_history.xlsx"'
        
        return response
    
    def export_pdf(self, loan):
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from datetime import datetime
        import os
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="payment_history_{loan.loan_number}_{datetime.now().strftime("%Y%m%d")}.pdf"'
        
        # Create PDF document with better margins
        doc = SimpleDocTemplate(
            response, 
            pagesize=A4,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        elements = []
        styles = getSampleStyleSheet()
        
        # Register Unicode font for better currency symbol support
        try:
            possible_fonts = [
                '/System/Library/Fonts/Arial.ttf',  # macOS
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
                'C:/Windows/Fonts/arial.ttf',  # Windows
            ]
            
            for font_path in possible_fonts:
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                    custom_font = 'CustomFont'
                    break
            else:
                custom_font = 'Helvetica'
        except:
            custom_font = 'Helvetica'
        
        # Create custom styles
        company_style = ParagraphStyle(
            'CompanyStyle',
            parent=styles['Normal'],
            fontSize=16,
            fontName='Helvetica-Bold',
            alignment=1,  # Center
            spaceAfter=5,
            textColor=colors.HexColor('#2C3E50')
        )
        
        address_style = ParagraphStyle(
            'AddressStyle',
            parent=styles['Normal'],
            fontSize=10,
            fontName=custom_font,
            alignment=1,  # Center
            spaceAfter=10,
            textColor=colors.HexColor('#7F8C8D')
        )
        
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=18,
            fontName='Helvetica-Bold',
            alignment=1,  # Center
            spaceAfter=20,
            textColor=colors.HexColor('#34495E'),
            borderWidth=2,
            borderColor=colors.HexColor('#3498DB'),
            borderPadding=10,
            backColor=colors.HexColor('#ECF0F1')
        )
        
        section_style = ParagraphStyle(
            'SectionStyle',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            spaceAfter=10,
            textColor=colors.HexColor('#2C3E50')
        )
        
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=10,
            fontName=custom_font,
            spaceAfter=5,
            textColor=colors.HexColor('#34495E')
        )
        
        # Company Header
        company_name = "PAWNSHOP MANAGEMENT SYSTEM"
        
        # Get branch details if available
        if loan.branch:
            branch_info = loan.branch
            company_name = f"{branch_info.name.upper()}"
            
            # Add company/branch name
            elements.append(Paragraph(company_name, company_style))
            
            # Add branch address if available
            address_parts = []
            if hasattr(branch_info, 'address') and branch_info.address:
                address_parts.append(branch_info.address)
            if hasattr(branch_info, 'city') and branch_info.city:
                address_parts.append(branch_info.city)
            if hasattr(branch_info, 'state') and branch_info.state:
                address_parts.append(branch_info.state)
            if hasattr(branch_info, 'pincode') and branch_info.pincode:
                address_parts.append(f"PIN: {branch_info.pincode}")
                
            if address_parts:
                elements.append(Paragraph(", ".join(address_parts), address_style))
            
            # Add contact details
            contact_parts = []
            branch_header_phones = get_branch_bill_header_phones(branch_info)
            if branch_header_phones:
                contact_parts.append(f"Phone: {branch_header_phones}")
            if hasattr(branch_info, 'email') and branch_info.email:
                contact_parts.append(f"Email: {branch_info.email}")
                
            if contact_parts:
                elements.append(Paragraph(" | ".join(contact_parts), address_style))
        else:
            elements.append(Paragraph(company_name, company_style))
            elements.append(Paragraph("Professional Pawnshop Services", address_style))
        
        # Add horizontal line
        elements.append(Spacer(1, 10))
        
        # Document Title
        elements.append(Paragraph("PAYMENT HISTORY REPORT", title_style))
        elements.append(Spacer(1, 20))
        
        # Loan Information Section
        elements.append(Paragraph("LOAN INFORMATION", section_style))
        
        # Create loan info table
        loan_data = [
            ['Loan Number:', loan.loan_number],
            ['Customer Name:', f"{loan.customer.first_name} {loan.customer.last_name}"],
            ['Customer Phone:', getattr(loan.customer, 'phone', 'N/A')],
            ['Principal Amount:', f"Rs {loan.principal_amount:,.2f}"],
            ['Issue Date:', loan.issue_date.strftime('%d %B %Y')],
            ['Due Date:', loan.due_date.strftime('%d %B %Y')],
            ['Loan Status:', loan.get_status_display()],
        ]
        
        loan_info_table = Table(loan_data, colWidths=[2*inch, 4*inch])
        loan_info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), custom_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
        ]))
        
        elements.append(loan_info_table)
        elements.append(Spacer(1, 20))
        
        # Payment Summary
        total_payments = loan.payments.count()
        total_amount_paid = sum(payment.amount for payment in loan.payments.all())
        
        elements.append(Paragraph("PAYMENT SUMMARY", section_style))
        
        # Calculate remaining balance - ensure it's never negative (0 for fully paid loans)
        remaining_balance = max(0, loan.total_payable_till_date)
        
        summary_data = [
            ['Total Payments Made:', str(total_payments)],
            ['Total Amount Paid:', f"Rs {total_amount_paid:,.2f}"],
            ['Remaining Balance:', f"Rs {remaining_balance:,.2f}"],
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), custom_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F6F3')),
            ('BACKGROUND', (1, -1), (1, -1), colors.HexColor('#FADBD8')),  # Highlight remaining balance
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 20))
        
        # Payment Details Section
        elements.append(Paragraph("PAYMENT DETAILS", section_style))
        
        if loan.payments.exists():
            # Payment history table headers
            payment_headers = ['S.No.', 'Date', 'Amount (Rs)', 'Method', 'Reference No.', 'Received By', 'Notes']
            payment_data = [payment_headers]
            
            # Add payment rows
            for idx, payment in enumerate(loan.payments.all().order_by('-payment_date'), 1):
                row = [
                    str(idx),
                    payment.payment_date.strftime('%d-%m-%Y'),
                    f"{payment.amount:,.2f}",
                    payment.get_payment_method_display(),
                    payment.reference_number or '-',
                    f"{payment.received_by.first_name} {payment.received_by.last_name}" if payment.received_by else 'N/A',
                    payment.notes[:30] + '...' if payment.notes and len(payment.notes) > 30 else (payment.notes or '-')
                ]
                payment_data.append(row)
            
            payment_table = Table(payment_data, colWidths=[0.5*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1.2*inch, 1.3*inch])
            payment_table.setStyle(TableStyle([
                # Header style
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data rows style
                ('FONTNAME', (0, 1), (-1, -1), custom_font),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # S.No center
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # Date center
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),   # Amount right
                ('ALIGN', (3, 1), (-1, -1), 'LEFT'),   # Rest left
                
                # General styling
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                
                # Grid and alternating colors
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
                
                # Amount column highlighting
                ('BACKGROUND', (2, 1), (2, -1), colors.HexColor('#E8F8F5')),
            ]))
            
            elements.append(payment_table)
        else:
            elements.append(Paragraph("No payments recorded for this loan.", info_style))
        
        elements.append(Spacer(1, 30))
        
        # Footer section
        footer_style = ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=8,
            fontName=custom_font,
            alignment=1,  # Center
            textColor=colors.HexColor('#7F8C8D')
        )
        
        # Add generation info
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y at %I:%M %p')}", footer_style))
        elements.append(Paragraph("This is a computer-generated document and does not require a signature.", footer_style))
        
        # Add disclaimer
        elements.append(Spacer(1, 10))
        disclaimer_style = ParagraphStyle(
            'DisclaimerStyle',
            parent=styles['Normal'],
            fontSize=7,
            fontName=custom_font,
            alignment=4,  # Justify
            textColor=colors.HexColor('#95A5A6'),
            leftIndent=20,
            rightIndent=20
        )
        
        disclaimer_text = ("This payment history is provided for informational purposes only. "
                          "All payment details are subject to verification. For any discrepancies, "
                          "please contact the branch office immediately.")
        elements.append(Paragraph(disclaimer_text, disclaimer_style))
        
        # Build PDF
        doc.build(elements)
        return response

class LoanTieredScheduleDownloadView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """
    Renders/Downloads the combined 'Scheme Rate Tiers Definition' and
    'Closing Total Amount Schedule (Monthly vs Delayed)' document for a loan.
    """
    def get(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        self.check_object_branch_access(loan, branch_attr='branch')
        
        display_tiers = loan.get_tiered_rate_structure_display()
        schedule_data = loan.get_tiered_schedule()
        
        context = {
            'loan': loan,
            'display_tiers': display_tiers,
            'schedule_data': schedule_data,
            'current_date': timezone.now().date(),
        }
        
        if request.GET.get('format') == 'pdf':
            try:
                return self._generate_pdf(request, context)
            except Exception as e:
                print(f"PDF generation error: {e}")
                
        return render(request, 'transactions/tiered_schedule_document.html', context)

    def _generate_pdf(self, request, context):
        from django.template.loader import render_to_string
        html_string = render_to_string('transactions/tiered_schedule_document.html', context, request=request)
        try:
            from xhtml2pdf import pisa
            import io
            result = io.BytesIO()
            pisa.CreatePDF(html_string, dest=result)
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Tiered_Schedule_{context["loan"].loan_number}.pdf"'
            return response
        except Exception:
            return HttpResponse(html_string)


class LoanScheduleView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """Generate a month-by-month interest schedule from current month to due month.
    CSV download is available via ?download=csv
    """
    def get(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # enforce branch access
        self.check_object_branch_access(loan, branch_attr='branch')

        # Basic inputs (use Decimal for precise currency arithmetic)
        # Principal should be Distribution Amount + Processing Fee when available
        dist_amt = getattr(loan, 'distribution_amount', None)
        proc_fee = getattr(loan, 'processing_fee', None)
        try:
            dist_amt_d = Decimal(str(dist_amt)) if dist_amt is not None else Decimal('0')
        except Exception:
            dist_amt_d = Decimal('0')
        try:
            proc_fee_d = Decimal(str(proc_fee)) if proc_fee is not None else Decimal('0')
        except Exception:
            proc_fee_d = Decimal('0')

        # Current outstanding principal (reduced by part payments)
        current_principal_d = Decimal(str(getattr(loan, 'principal_amount', 0) or 0))
        # Interest base = min(original distribution, current outstanding principal)
        interest_base_d = min(dist_amt_d, current_principal_d) if dist_amt_d > 0 and current_principal_d > 0 else dist_amt_d

        if dist_amt_d > Decimal('0'):
            principal = (dist_amt_d + proc_fee_d).quantize(Decimal('0.01'))
        else:
            principal = current_principal_d

        rate_annual = Decimal(str(getattr(loan, 'interest_rate', 0) or 0))
        today = timezone.now().date()
        due = getattr(loan, 'due_date', None)
        if not due or principal <= 0 or rate_annual <= 0:
            return HttpResponse('Loan missing principal, due date, or interest rate', status=400)

        # start from beginning of current month
        start = today.replace(day=1)
        # iterate months until due month inclusive
        months = []
        cur = start
        while cur <= due:
            months.append(cur)
            # advance to next month
            year = cur.year + (cur.month // 12)
            month = (cur.month % 12) + 1
            cur = cur.replace(year=year, month=month, day=1)

        monthly_rate = (rate_annual / Decimal('100')) / Decimal('12')

        rows = []
        remaining_principal = principal

        num_months = max(1, len(months))
        # Distribute principal evenly using Decimal; adjust last month to absorb rounding
        principal_per_month = (principal / Decimal(num_months)).quantize(Decimal('0.01'))
        last_month_principal = (principal - principal_per_month * (num_months - 1)).quantize(Decimal('0.01'))

        # Interest is calculated on current outstanding amount (not original if reduced by part payments)
        monthly_interest_const = (interest_base_d * monthly_rate).quantize(Decimal('0.01'))

        # Log diagnostics for inspection
        try:
            logger.info(
                "LoanSchedule diagnostics: loan=%s principal=%s distribution_amount=%s processing_fee=%s num_months=%s principal_per_month=%s last_month_principal=%s monthly_interest_const=%s",
                loan.loan_number,
                str(principal),
                str(dist_amt_d),
                str(proc_fee_d),
                str(num_months),
                str(principal_per_month),
                str(last_month_principal),
                str(monthly_interest_const),
            )
        except Exception:
            pass

        # Build rows: principal shown as full principal (distribution+processing_fee) each month,
        # interest constant, total = principal + cumulative interest up to that month.
        for idx, m in enumerate(months):
            month_index = Decimal(idx + 1)
            cumulative_interest = (monthly_interest_const * month_index).quantize(Decimal('0.01'))
            total_amount = (principal + cumulative_interest).quantize(Decimal('0.01'))

            # Prepare principal display with breakdown e.g., 35354(35000+354)
            dist_display = dist_amt_d.quantize(Decimal('0.01'))
            proc_display = proc_fee_d.quantize(Decimal('0.01'))
            # Format amounts as integer if no cents, else two decimals
            def fmt(a: Decimal):
                a_q = a.quantize(Decimal('0.01'))
                if a_q == a_q.to_integral():
                    return str(int(a_q))
                return format(a_q, '0.2f')

            principal_display = f"{fmt(principal)}({fmt(dist_display)}+{fmt(proc_display)})"

            rows.append({
                'month': m.strftime('%b-%Y'),
                'principal': principal,
                'principal_display': principal_display,
                'interest': monthly_interest_const,
                'total_amount': total_amount,
            })

        # final row: totals
        total_interest = (monthly_interest_const * Decimal(num_months)).quantize(Decimal('0.01'))
        final_row = {
            'month': 'TOTAL',
            'interest': total_interest,
            'principal': principal.quantize(Decimal('0.01')),
            'total_amount': (principal + total_interest).quantize(Decimal('0.01')),
            'payoff_amount': (principal + Decimal('0.00') + monthly_interest_const).quantize(Decimal('0.01')),
        }

        download = request.GET.get('download')
        if download == 'csv':
            # return CSV with new columns
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="loan_{loan.loan_number}_schedule.csv"'
            writer = csv.writer(response)
            writer.writerow(['Month', 'Principal', 'Monthly Interest', 'Total Amount'])
            for idx, r in enumerate(rows, start=1):
                # cumulative interest = monthly_interest * idx
                cum_interest = round(r['interest'] * Decimal(idx))
                writer.writerow([r['month'], r.get('principal_display') or format(round(r['principal']), 'd'), format(round(r['interest']), 'd'), format(round(r['total_amount']), 'd')])
            writer.writerow([final_row['month'], format(round(final_row['principal']), 'd'), format(round(final_row['interest']), 'd'), format(round(final_row['total_amount']), 'd')])
            return response

        if download == 'pdf':
            # Generate a simple PDF schedule using ReportLab
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch

            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="loan_{loan.loan_number}_schedule.pdf"'

            doc = SimpleDocTemplate(
                response,
                pagesize=landscape(A4),
                rightMargin=0.3*inch,
                leftMargin=0.3*inch,
                topMargin=0.25*inch,
                bottomMargin=0.25*inch,
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('Title', parent=styles['Heading2'], alignment=1, fontSize=12, spaceAfter=6)
            header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold')
            copy_type_style = ParagraphStyle('CopyType', parent=styles['Normal'], fontSize=14, fontName='Helvetica-Bold', alignment=1, textColor=colors.HexColor('#C0504D'), spaceAfter=8)
            normal = styles['Normal']

            elements = []
            
            # Get copy type from request parameter (default to showing both)
            copy_type = request.GET.get('copy_type', 'both')  # both, customer, or office
            
            # Function to add copy section
            def add_copy_section(copy_label, is_customer=False):
                section_elements = []
                section_elements.append(Paragraph(f"*** {copy_label} ***", copy_type_style))
                section_elements.append(Paragraph(f"Loan Schedule - {loan.loan_number}", title_style))
                section_elements.append(Spacer(1, 6))
                
                # Add customer details at the top
                customer_name = f"{loan.customer.first_name} {loan.customer.last_name}"
                principal_amount = f"Rs {loan.principal_amount:,.0f}"
                loan_date = loan.issue_date.strftime('%d-%m-%Y')
                due_date = loan.due_date.strftime('%d-%m-%Y')

                # Create customer details table
                customer_details = [
                    ['Customer Name:', customer_name, 'Loan Date:', loan_date],
                    ['Principal Amount:', principal_amount, 'Due Date:', due_date],
                ]
                
                customer_table = Table(customer_details, colWidths=[1.5*inch, 2.5*inch, 1.5*inch, 2.5*inch])
                customer_table.setStyle(TableStyle([
                    ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                    ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('LEFTPADDING', (0,0), (-1,-1), 5),
                    ('RIGHTPADDING', (0,0), (-1,-1), 5),
                    ('TOPPADDING', (0,0), (-1,-1), 5),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#E8F0F7')),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ]))
                
                section_elements.append(customer_table)
                section_elements.append(Spacer(1, 6))

                table_data = [[ 'S.No.', 'Month', 'Principal(Dist+Prc)', 'Monthly Interest', 'Customer Signature', 'Office Sign & Seal' ]]
                for idx, r in enumerate(rows, start=1):
                    table_data.append([str(idx), r['month'], r.get('principal_display') or format(round(r['principal']), 'd'), f"{round(r['interest']):,}", '', ''])

                col_widths = [0.6*inch, 1.0*inch, 1.6*inch, 1.4*inch, 1.9*inch, 1.9*inch]
                table = Table(table_data, colWidths=col_widths, rowHeights=[0.35*inch] + [0.9*inch]*(len(table_data)-1))

                # Build table style and add alternating row backgrounds for readability
                style_list = [
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#366092')),
                    ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                    ('ALIGN',(0,0),(0,-1),'CENTER'),
                    ('ALIGN',(1,1),(3,-1),'RIGHT'),
                    ('ALIGN',(4,0),(-1,-1),'CENTER'),
                    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                    ('GRID',(0,0),(-1,-1),0.5,colors.grey),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,0), 10),
                    ('FONTSIZE', (0,1), (-1,-1), 9),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                    ('TOPPADDING', (0,0), (-1,-1), 12),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                ]

                # Apply zebra striping to data rows (row index starts at 0 for header)
                for row_idx in range(1, len(table_data)):
                    if row_idx % 2 == 0:
                        # even data rows -> light blue background
                        style_list.append(('BACKGROUND', (0, row_idx), (3, row_idx), colors.HexColor('#f6f9ff')))
                    # Signature columns always have white background with border
                    style_list.append(('BACKGROUND', (4, row_idx), (-1, row_idx), colors.white))

                table.setStyle(TableStyle(style_list))
                section_elements.append(table)
                
                return section_elements
            
            # Add copies based on request parameter
            if copy_type == 'customer':
                elements.extend(add_copy_section('CUSTOMER COPY', is_customer=True))
            elif copy_type == 'office':
                elements.extend(add_copy_section('OFFICE COPY', is_customer=False))
            else:  # default to customer copy only
                elements.extend(add_copy_section('CUSTOMER COPY', is_customer=True))
            doc.build(elements)
            return response

        context = {
            'loan': loan,
            'rows': rows,
            'final_row': final_row,
            'diagnostics': {
                'principal': str(principal),
                'distribution_amount': str(dist_amt_d),
                'processing_fee': str(proc_fee_d),
                'num_months': num_months,
                'principal_per_month': str(principal_per_month),
                'last_month_principal': str(last_month_principal),
                'monthly_interest_const': str(monthly_interest_const),
            },
        }
        return render(request, 'transactions/loan_schedule.html', context)
    
    def export_excel(self, loan):
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = f"Loan {loan.loan_number} Payments"
        
        # Headers
        headers = ['Date', 'Amount', 'Method', 'Reference', 'Notes']
        for col, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        
        # Data
        for row_idx, payment in enumerate(loan.payments.all().order_by('-payment_date'), 2):
            worksheet.cell(row=row_idx, column=1, value=payment.payment_date.strftime('%Y-%m-%d'))
            worksheet.cell(row=row_idx, column=2, value=float(payment.amount))
            worksheet.cell(row=row_idx, column=3, value=payment.get_payment_method_display())
            worksheet.cell(row=row_idx, column=4, value=payment.reference_number or '')
            worksheet.cell(row=row_idx, column=5, value=payment.notes or '')
        
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="loan_{loan.loan_number}_payment_history.xlsx"'
        
        return response
    
    def export_pdf(self, loan):
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from datetime import datetime
        import os
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="payment_history_{loan.loan_number}_{datetime.now().strftime("%Y%m%d")}.pdf"'
        
        # Create PDF document with better margins
        doc = SimpleDocTemplate(
            response, 
            pagesize=A4,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        elements = []
        styles = getSampleStyleSheet()
        
        # Register Unicode font for better currency symbol support
        try:
            possible_fonts = [
                '/System/Library/Fonts/Arial.ttf',  # macOS
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
                'C:/Windows/Fonts/arial.ttf',  # Windows
            ]
            
            for font_path in possible_fonts:
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                    custom_font = 'CustomFont'
                    break
            else:
                custom_font = 'Helvetica'
        except:
            custom_font = 'Helvetica'
        
        # Create custom styles
        company_style = ParagraphStyle(
            'CompanyStyle',
            parent=styles['Normal'],
            fontSize=16,
            fontName='Helvetica-Bold',
            alignment=1,  # Center
            spaceAfter=5,
            textColor=colors.HexColor('#2C3E50')
        )
        
        address_style = ParagraphStyle(
            'AddressStyle',
            parent=styles['Normal'],
            fontSize=10,
            fontName=custom_font,
            alignment=1,  # Center
            spaceAfter=10,
            textColor=colors.HexColor('#7F8C8D')
        )
        
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=18,
            fontName='Helvetica-Bold',
            alignment=1,  # Center
            spaceAfter=20,
            textColor=colors.HexColor('#34495E'),
            borderWidth=2,
            borderColor=colors.HexColor('#3498DB'),
            borderPadding=10,
            backColor=colors.HexColor('#ECF0F1')
        )
        
        section_style = ParagraphStyle(
            'SectionStyle',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            spaceAfter=10,
            textColor=colors.HexColor('#2C3E50')
        )
        
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=10,
            fontName=custom_font,
            spaceAfter=5,
            textColor=colors.HexColor('#34495E')
        )
        
        # Company Header
        company_name = "PAWNSHOP MANAGEMENT SYSTEM"
        
        # Get branch details if available
        if loan.branch:
            branch_info = loan.branch
            company_name = f"{branch_info.name.upper()}"
            
            # Add company/branch name
            elements.append(Paragraph(company_name, company_style))
            
            # Add branch address if available
            address_parts = []
            if hasattr(branch_info, 'address') and branch_info.address:
                address_parts.append(branch_info.address)
            if hasattr(branch_info, 'city') and branch_info.city:
                address_parts.append(branch_info.city)
            if hasattr(branch_info, 'state') and branch_info.state:
                address_parts.append(branch_info.state)
            if hasattr(branch_info, 'pincode') and branch_info.pincode:
                address_parts.append(f"PIN: {branch_info.pincode}")
                
            if address_parts:
                elements.append(Paragraph(", ".join(address_parts), address_style))
            
            # Add contact details
            contact_parts = []
            branch_header_phones = get_branch_bill_header_phones(branch_info)
            if branch_header_phones:
                contact_parts.append(f"Phone: {branch_header_phones}")
            if hasattr(branch_info, 'email') and branch_info.email:
                contact_parts.append(f"Email: {branch_info.email}")
                
            if contact_parts:
                elements.append(Paragraph(" | ".join(contact_parts), address_style))
        else:
            elements.append(Paragraph(company_name, company_style))
            elements.append(Paragraph("Professional Pawnshop Services", address_style))
        
        # Add horizontal line
        elements.append(Spacer(1, 10))
        
        # Document Title
        elements.append(Paragraph("PAYMENT HISTORY REPORT", title_style))
        elements.append(Spacer(1, 20))
        
        # Loan Information Section
        elements.append(Paragraph("LOAN INFORMATION", section_style))
        
        # Create loan info table
        loan_data = [
            ['Loan Number:', loan.loan_number],
            ['Customer Name:', f"{loan.customer.first_name} {loan.customer.last_name}"],
            ['Customer Phone:', getattr(loan.customer, 'phone', 'N/A')],
            ['Principal Amount:', f"Rs {loan.principal_amount:,.2f}"],
            ['Issue Date:', loan.issue_date.strftime('%d %B %Y')],
            ['Due Date:', loan.due_date.strftime('%d %B %Y')],
            ['Loan Status:', loan.get_status_display()],
        ]
        
        loan_info_table = Table(loan_data, colWidths=[2*inch, 4*inch])
        loan_info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), custom_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
        ]))
        
        elements.append(loan_info_table)
        elements.append(Spacer(1, 20))
        
        # Payment Summary
        total_payments = loan.payments.count()
        total_amount_paid = sum(payment.amount for payment in loan.payments.all())
        
        elements.append(Paragraph("PAYMENT SUMMARY", section_style))
        
        # Calculate remaining balance - ensure it's never negative (0 for fully paid loans)
        remaining_balance = max(0, loan.total_payable_till_date)
        
        summary_data = [
            ['Total Payments Made:', str(total_payments)],
            ['Total Amount Paid:', f"Rs {total_amount_paid:,.2f}"],
            ['Remaining Balance:', f"Rs {remaining_balance:,.2f}"],
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), custom_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F6F3')),
            ('BACKGROUND', (1, -1), (1, -1), colors.HexColor('#FADBD8')),  # Highlight remaining balance
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 20))
        
        # Payment Details Section
        elements.append(Paragraph("PAYMENT DETAILS", section_style))
        
        if loan.payments.exists():
            # Payment history table headers
            payment_headers = ['S.No.', 'Date', 'Amount (Rs)', 'Method', 'Reference No.', 'Received By', 'Notes']
            payment_data = [payment_headers]
            
            # Add payment rows
            for idx, payment in enumerate(loan.payments.all().order_by('-payment_date'), 1):
                row = [
                    str(idx),
                    payment.payment_date.strftime('%d-%m-%Y'),
                    f"{payment.amount:,.2f}",
                    payment.get_payment_method_display(),
                    payment.reference_number or '-',
                    f"{payment.received_by.first_name} {payment.received_by.last_name}" if payment.received_by else 'N/A',
                    payment.notes[:30] + '...' if payment.notes and len(payment.notes) > 30 else (payment.notes or '-')
                ]
                payment_data.append(row)
            
            payment_table = Table(payment_data, colWidths=[0.5*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1.2*inch, 1.3*inch])
            payment_table.setStyle(TableStyle([
                # Header style
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data rows style
                ('FONTNAME', (0, 1), (-1, -1), custom_font),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # S.No center
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # Date center
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),   # Amount right
                ('ALIGN', (3, 1), (-1, -1), 'LEFT'),   # Rest left
                
                # General styling
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                
                # Grid and alternating colors
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
                
                # Amount column highlighting
                ('BACKGROUND', (2, 1), (2, -1), colors.HexColor('#E8F8F5')),
            ]))
            
            elements.append(payment_table)
        else:
            elements.append(Paragraph("No payments recorded for this loan.", info_style))
        
        elements.append(Spacer(1, 30))
        
        # Footer section
        footer_style = ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=8,
            fontName=custom_font,
            alignment=1,  # Center
            textColor=colors.HexColor('#7F8C8D')
        )
        
        # Add generation info
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y at %I:%M %p')}", footer_style))
        elements.append(Paragraph("This is a computer-generated document and does not require a signature.", footer_style))
        
        # Add disclaimer
        elements.append(Spacer(1, 10))
        disclaimer_style = ParagraphStyle(
            'DisclaimerStyle',
            parent=styles['Normal'],
            fontSize=7,
            fontName=custom_font,
            alignment=4,  # Justify
            textColor=colors.HexColor('#95A5A6'),
            leftIndent=20,
            rightIndent=20
        )
        
        disclaimer_text = ("This payment history is provided for informational purposes only. "
                          "All payment details are subject to verification. For any discrepancies, "
                          "please contact the branch office immediately.")
        elements.append(Paragraph(disclaimer_text, disclaimer_style))
        
        # Build PDF
        doc.build(elements)
        return response


class LoanEMIScheduleView(LoginRequiredMixin, RoleBranchAccessMixin, View):
    """Generate EMI (Equal Monthly Installment) schedule for the total loan term."""
    
    def get(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        self.check_object_branch_access(loan, branch_attr='branch')
        
        # Get loan details
        dist_amt = getattr(loan, 'distribution_amount', None)
        proc_fee = getattr(loan, 'processing_fee', None)
        
        try:
            dist_amt_d = Decimal(str(dist_amt)) if dist_amt is not None else Decimal('0')
        except Exception:
            dist_amt_d = Decimal('0')
        try:
            proc_fee_d = Decimal(str(proc_fee)) if proc_fee is not None else Decimal('0')
        except Exception:
            proc_fee_d = Decimal('0')
        
        # Current outstanding principal (reflects part payments)
        current_principal_d = Decimal(str(getattr(loan, 'principal_amount', 0) or 0))
        # Interest base = min(original distribution, current outstanding principal)
        interest_base_d = min(dist_amt_d, current_principal_d) if dist_amt_d > 0 and current_principal_d > 0 else dist_amt_d

        # Total principal = distribution + processing fee
        if dist_amt_d > Decimal('0'):
            principal = (dist_amt_d + proc_fee_d).quantize(Decimal('0.01'))
        else:
            principal = current_principal_d
        
        rate_annual = Decimal(str(getattr(loan, 'interest_rate', 0) or 0))
        issue_date = getattr(loan, 'issue_date', None)
        due_date = getattr(loan, 'due_date', None)
        
        if not due_date or not issue_date or principal <= 0 or rate_annual <= 0:
            return HttpResponse('Loan missing required data', status=400)
        
        # Calculate number of months from issue to due date
        months_diff = (due_date.year - issue_date.year) * 12 + (due_date.month - issue_date.month)
        num_months = max(1, months_diff)
        
        monthly_rate = (rate_annual / Decimal('100')) / Decimal('12')
        
        # Calculate EMI using formula: EMI = P * r * (1+r)^n / ((1+r)^n - 1)
        # where P = principal (distribution amount for interest calculation)
        # r = monthly interest rate, n = number of months
        one_plus_r = Decimal('1') + monthly_rate
        one_plus_r_n = one_plus_r ** num_months
        
        # EMI calculation based on current outstanding interest base (tracks part payments)
        emi_interest = (interest_base_d * monthly_rate * one_plus_r_n / (one_plus_r_n - Decimal('1'))).quantize(Decimal('0.01'))
        
        # Add prorated processing fee to each EMI
        processing_fee_per_month = (proc_fee_d / Decimal(num_months)).quantize(Decimal('0.01'))
        emi_total = emi_interest + processing_fee_per_month
        
        # Generate schedule
        rows = []
        remaining_principal = interest_base_d
        remaining_proc_fee = proc_fee_d
        total_interest_paid = Decimal('0')
        
        cur_date = issue_date.replace(day=1)
        
        for month_num in range(1, num_months + 1):
            # Advance to next month
            if month_num > 1:
                year = cur_date.year + (cur_date.month // 12)
                month = (cur_date.month % 12) + 1
                cur_date = cur_date.replace(year=year, month=month, day=1)
            
            # Interest for this month on remaining principal
            interest_component = (remaining_principal * monthly_rate).quantize(Decimal('0.01'))
            
            # Principal component of EMI
            principal_component = (emi_interest - interest_component).quantize(Decimal('0.01'))
            
            # Adjust for last month to account for rounding
            if month_num == num_months:
                principal_component = remaining_principal
                processing_fee_per_month = remaining_proc_fee
                emi_total = principal_component + interest_component + processing_fee_per_month
            
            remaining_principal = (remaining_principal - principal_component).quantize(Decimal('0.01'))
            remaining_proc_fee = (remaining_proc_fee - processing_fee_per_month).quantize(Decimal('0.01'))
            total_interest_paid = (total_interest_paid + interest_component).quantize(Decimal('0.01'))
            
            rows.append({
                'month_num': month_num,
                'month': cur_date.strftime('%b-%Y'),
                'emi': emi_total.quantize(Decimal('0.01')),
                'principal_component': principal_component,
                'interest_component': interest_component,
                'processing_fee_component': processing_fee_per_month,
                'remaining_principal': remaining_principal,
            })
        
        # Summary row
        total_amount_paid = (dist_amt_d + proc_fee_d + total_interest_paid).quantize(Decimal('0.01'))
        
        context = {
            'loan': loan,
            'rows': rows,
            'num_months': num_months,
            'emi_amount': emi_total.quantize(Decimal('0.01')),
            'distribution_amount': dist_amt_d.quantize(Decimal('0.01')),
            'processing_fee': proc_fee_d.quantize(Decimal('0.01')),
            'total_principal': principal.quantize(Decimal('0.01')),
            'total_interest': total_interest_paid,
            'total_amount': total_amount_paid,
            'issue_date': issue_date,
            'due_date': due_date,
        }
        
        download = request.GET.get('download')
        if download == 'pdf':
            return self.export_pdf(context)
        
        return render(request, 'transactions/loan_emi_schedule.html', context)
    
    def export_pdf(self, context):
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from datetime import datetime
        
        response = HttpResponse(content_type='application/pdf')
        loan = context['loan']
        response['Content-Disposition'] = f'attachment; filename="emi_schedule_{loan.loan_number}_{datetime.now().strftime("%Y%m%d")}.pdf"'
        
        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
        elements.append(Paragraph(f"EMI Schedule - Loan {loan.loan_number}", title_style))
        elements.append(Spacer(1, 12))
        
        # Loan info
        info_style = styles['Normal']
        elements.append(Paragraph(f"<b>Customer:</b> {loan.customer.full_name}", info_style))
        elements.append(Paragraph(f"<b>Loan Number:</b> {loan.loan_number}", info_style))
        elements.append(Paragraph(f"<b>Loan Date:</b> {context['issue_date'].strftime('%d/%m/%Y')}", info_style))
        elements.append(Paragraph(f"<b>Due Date:</b> {context['due_date'].strftime('%d/%m/%Y')}", info_style))
        elements.append(Paragraph(f"<b>Principal Amount:</b> Rs: {context['total_principal']}", info_style))
        elements.append(Paragraph(f"<b>Distribution Amount:</b> Rs: {context['distribution_amount']}", info_style))
        elements.append(Paragraph(f"<b>Processing Fee:</b> Rs: {context['processing_fee']}", info_style))
        elements.append(Paragraph(f"<b>Interest Rate:</b> {loan.interest_rate}% per annum", info_style))
        elements.append(Paragraph(f"<b>EMI Amount:</b> Rs: {context['emi_amount']}", info_style))
        elements.append(Paragraph(f"<b>Number of Months:</b> {context['num_months']}", info_style))
        elements.append(Spacer(1, 12))
        
        # Table
        table_data = [['Month', 'Month', 'EMI', 'Principal', 'Interest', 'Proc. Fee', 'Balance']]
        table_data[0] = ['#', 'Month', 'EMI', 'Principal', 'Interest', 'Proc. Fee', 'Balance']
        
        for row in context['rows']:
            table_data.append([
                str(row['month_num']),
                row['month'],
                f"Rs: {row['emi']}",
                f"Rs: {row['principal_component']}",
                f"Rs: {row['interest_component']}",
                f"Rs: {row['processing_fee_component']}",
                f"Rs: {row['remaining_principal']}",
            ])
        
        # Totals row
        table_data.append([
            '', 'TOTAL',
            f"Rs: {context['total_amount']}",
            f"Rs: {context['distribution_amount']}",
            f"Rs: {context['total_interest']}",
            f"Rs: {context['processing_fee']}",
            '---',
        ])
        
        table = Table(table_data, colWidths=[0.5*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        doc.build(elements)
        return response


class PaymentReceiptView(LoginRequiredMixin, View):
    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        loan = payment.loan
        bill_details = get_branch_bill_details(getattr(loan, 'branch', None))
        
        # Prepare amount in words (English) and Tamil
        amount_in_words = amount_to_english_words(payment.amount)
        amount_in_words_tamil = number_to_tamil_words(payment.amount)

        # Keep receipt generation fast by avoiding runtime network translation.
        payment.notes_tamil = payment.notes or ''

        # Extract interest paid and principal paid for THIS specific payment from notes.
        # Notes are stored as: "Part Payment (Interest: Rs.X, Principal: Rs.Y)"
        import re as _re
        this_payment_interest = Decimal('0.00')
        this_payment_principal = Decimal('0.00')
        if payment.notes:
            int_match = _re.search(r'Interest[:\s]+(?:Rs\.?|₹)\s*([\d,]+\.?\d*)', payment.notes, _re.IGNORECASE)
            pri_match = _re.search(r'Principal[:\s]+(?:Rs\.?|₹)\s*([\d,]+\.?\d*)', payment.notes, _re.IGNORECASE)
            if int_match:
                this_payment_interest = Decimal(int_match.group(1).replace(',', ''))
            if pri_match:
                this_payment_principal = Decimal(pri_match.group(1).replace(',', ''))
        # Fallback: if notes don't have breakdown, treat full amount as principal
        if this_payment_interest == Decimal('0.00') and this_payment_principal == Decimal('0.00'):
            this_payment_principal = payment.amount

        # Calculate total paid till date (including this payment) and remaining balance.
        # Sum all payments for this loan up to and including this payment's date.
        from django.db.models import Sum as _Sum
        total_paid_till_this = loan.payments.filter(
            payment_date__lte=payment.payment_date, id__lte=payment.id
        ).aggregate(total=_Sum('amount'))['total'] or Decimal('0.00')

        # Remaining balance: after this payment was recorded, what was left?
        # For closed loans it's 0; for active, use current principal + current interest.
        from transactions.services_partial_release import get_loan_current_interest_due
        current_interest_due = get_loan_current_interest_due(loan)
        is_closed = loan.status in ['closed', 'repaid', 'foreclosed'] or (loan.principal_amount or 0) <= 0
        payment_type = 'full' if is_closed else 'partial'
        remaining_balance = Decimal('0.00') if is_closed else (loan.principal_amount + current_interest_due)

        # Customer display name
        customer_name_display = ""
        if loan.customer:
            customer_name_display = f"{loan.customer.first_name or ''} {loan.customer.last_name or ''}".strip()
            if not customer_name_display and hasattr(loan.customer, 'full_name'):
                customer_name_display = str(loan.customer.full_name or '')

        context = {
            'payment': payment,
            'loan': loan,
            'customer_name_display': customer_name_display,
            'payment_type': payment_type,
            'interest_amount': this_payment_interest,
            'principal_amount_paid': this_payment_principal,
            'total_paid': total_paid_till_this,
            'remaining_balance': remaining_balance,
            'date_today': timezone.now(),
            'branch_phone_display': get_branch_bill_header_phones(getattr(loan, 'branch', None)),
            'branch_address_display': bill_details.get('address', ''),
            'bill_shop_name': bill_details.get('shop_name', ''),
            'bill_address_display': bill_details.get('address', ''),
            'bill_phone_display': bill_details.get('phone', ''),
            'bill_email_display': bill_details.get('email', ''),
            'bill_logo_url': bill_details.get('logo_url', ''),
            'total_items_count': get_loan_total_items_count(loan),
            'amount_in_words': amount_in_words,
            'amount_in_words_tamil': amount_in_words_tamil,
            'tamil_font_file_uri': f"file:///{str((settings.BASE_DIR / 'static' / 'fonts' / 'NotoSansTamil-Regular.ttf')).replace(os.sep, '/')}",
        }
        
        # Render PDF
        template = get_template('transactions/payment_receipt_pdf.html')
        html = template.render(context)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="payment_receipt_{payment.id}.pdf"'
        
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse('Error generating PDF', status=500)
        
        return response


class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'transactions/sale_list.html'
    context_object_name = 'sales'
    paginate_by = 20


class SaleCreateView(LoginRequiredMixin, CreateView):
    model = Sale
    form_class = SaleForm
    template_name = 'transactions/sale_form.html'
    success_url = reverse_lazy('sale_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user

        # Assign branch: use user's branch if set, else fall back to first
        # branch in the user's organization (covers superusers / admin accounts
        # that are not tied to a specific branch).
        if self.request.user.branch:
            form.instance.branch = self.request.user.branch
        else:
            from branches.models import Branch
            user = self.request.user
            fallback_branch = None
            if hasattr(user, 'organization') and user.organization:
                fallback_branch = Branch.objects.filter(
                    organization=user.organization, is_active=True
                ).first()
            if fallback_branch is None and user.is_superuser:
                fallback_branch = Branch.objects.filter(is_active=True).first()

            if fallback_branch:
                form.instance.branch = fallback_branch
            else:
                form.add_error(
                    None,
                    'No branch is assigned to your account. Please contact an administrator.'
                )
                return self.form_invalid(form)

        messages.success(self.request, 'Sale created successfully!')
        return super().form_valid(form)


class SaleDetailView(LoginRequiredMixin, DetailView):
    model = Sale
    template_name = 'transactions/sale_detail.html'
    context_object_name = 'sale'


class SaleUpdateView(LoginRequiredMixin, UpdateView):
    model = Sale
    form_class = SaleForm
    template_name = 'transactions/sale_form.html'
    
    def get_success_url(self):
        return reverse('sale_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Sale updated successfully!')
        return super().form_valid(form)


class SaleCancelView(LoginRequiredMixin, View):
    def post(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        sale.status = 'cancelled'
        sale.save()
        messages.success(request, f'Sale #{sale.id} has been cancelled.')
        return redirect('sale_detail', pk=pk)


class SaleCompleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        sale.status = 'completed'
        sale.save()
        messages.success(request, f'Sale #{sale.id} has been completed.')
        return redirect('sale_detail', pk=pk)


class SaleReceiptView(LoginRequiredMixin, View):
    def get(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        bill_details = get_branch_bill_details(getattr(sale, 'branch', None))
        
        # Compute English and Tamil amount-in-words for the sale total
        try:
            total_amount = sale.total_amount
        except Exception:
            total_amount = getattr(sale, 'total_amount', 0)

        sale.total_amount_in_words = amount_to_english_words(total_amount)
        sale.total_amount_in_words_tamil = number_to_tamil_words(total_amount)

        context = {
            'sale': sale,
            'branch_phone_display': get_branch_bill_header_phones(getattr(sale, 'branch', None)),
            'branch_address_display': bill_details.get('address', ''),
            'bill_shop_name': bill_details.get('shop_name', ''),
            'bill_address_display': bill_details.get('address', ''),
            'bill_phone_display': bill_details.get('phone', ''),
            'bill_email_display': bill_details.get('email', ''),
            'bill_logo_url': bill_details.get('logo_url', ''),
            'total_items_count': 1,
            'now': timezone.now(),
            'tamil_font_file_uri': f"file:///{str((settings.BASE_DIR / 'static' / 'fonts' / 'NotoSansTamil-Regular.ttf')).replace(os.sep, '/')}",
        }
        
        # Render PDF
        template = get_template('transactions/sale_receipt_pdf.html')
        html = template.render(context)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="sale_receipt_{sale.id}.pdf"'
        
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse('Error generating PDF', status=500)
        
        return response


def number_to_words(request, number):
    """Utility view to convert numbers to words"""
    try:
        words = num2words(float(number), lang='en_IN').title()
        return JsonResponse({'words': words})
    except (ValueError, TypeError):
        return JsonResponse({'words': 'Invalid number'}, status=400)


def get_customer_bank_details(request, customer_id):
    """API endpoint to fetch customer's bank details for auto-populating loan form"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        from accounts.models import Customer
        customer = Customer.objects.get(pk=customer_id)
        return JsonResponse({
            'success': True,
            'bank_account_number': customer.bank_account_number or '',
            'bank_ifsc_code': customer.bank_ifsc_code or '',
            'bank_name': customer.bank_name or '',
            'bank_beneficiary_name': customer.bank_beneficiary_name or customer.full_name or '',
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=404)


# ==============================================================================
# Task 2.1: Tiered Maker-Checker Loan Approval Workflow & Approval Queue
# ==============================================================================
class LoanApprovalQueueView(LoginRequiredMixin, View):
    """
    Real-time Loan Approval Queue for Branch Managers, Regional Managers & Head Office.
    Provides appraisal dossier, KYC verification, gold valuation metrics, and digital sign-off.
    """
    template_name = 'transactions/loan_approval_queue.html'

    def get_accessible_loans(self, request):
        user = request.user
        role = getattr(user, 'role', None)
        role_type = getattr(role, 'role_type', None) if role else str(getattr(user, 'role', ''))

        qs = Loan.objects.select_related('customer', 'branch', 'scheme', 'maker', 'checker_bm', 'checker_ro', 'checker_ho').all()

        # Role-based hierarchy scoping
        if user.is_superuser or role_type in ['admin', 'headoffice', 'finance_manager']:
            # Enterprise-wide
            pass
        elif role_type == 'regional_manager':
            # Regional Manager: scoped to user's assigned regions
            if hasattr(user, 'regions') and user.regions.exists():
                qs = qs.filter(branch__region__in=user.regions.all())
            elif user.branch and user.branch.region:
                qs = qs.filter(branch__region=user.branch.region)
            # RM sees Tier 2 & Tier 3 loans
            qs = qs.filter(approval_tier__in=[2, 3])
        elif role_type == 'branch_manager' or (user.branch and user == user.branch.manager):
            # Branch Manager: scoped to their branch
            if user.branch:
                qs = qs.filter(branch=user.branch)
        else:
            # Frontline staff/appraisers only see loans they created
            qs = qs.filter(maker=user)

        return qs

    def get(self, request):
        base_qs = self.get_accessible_loans(request)
        tab = request.GET.get('tab', 'pending')
        tier = request.GET.get('tier')
        branch_id = request.GET.get('branch_id')

        # Filter by tab
        if tab == 'pending':
            loans = base_qs.filter(status='pending_approval')
        elif tab == 'approved':
            loans = base_qs.filter(status='approved')
        elif tab == 'rejected':
            loans = base_qs.filter(status='rejected')
        elif tab == 'disbursed':
            loans = base_qs.filter(status='active')
        else:
            loans = base_qs.filter(status__in=['pending_approval', 'approved', 'rejected'])

        if tier and tier.isdigit():
            loans = loans.filter(approval_tier=int(tier))
        if branch_id and branch_id.isdigit():
            loans = loans.filter(branch_id=int(branch_id))

        loans = loans.order_by('-created_at')

        # Metrics for badges
        pending_count = base_qs.filter(status='pending_approval').count()
        approved_count = base_qs.filter(status='approved').count()
        rejected_count = base_qs.filter(status='rejected').count()
        
        tier1_pending = base_qs.filter(status='pending_approval', approval_tier=1).count()
        tier2_pending = base_qs.filter(status='pending_approval', approval_tier=2).count()
        tier3_pending = base_qs.filter(status='pending_approval', approval_tier=3).count()

        from branches.models import Branch
        all_branches = Branch.objects.filter(is_active=True)

        context = {
            'loans': loans,
            'tab': tab,
            'pending_count': pending_count,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'tier1_pending': tier1_pending,
            'tier2_pending': tier2_pending,
            'tier3_pending': tier3_pending,
            'all_branches': all_branches,
            'selected_branch': branch_id,
            'selected_tier': tier,
        }
        return render(request, self.template_name, context)


class LoanApproveActionView(LoginRequiredMixin, View):
    """Action to approve loan application for current tier"""
    def post(self, request, pk):
        loan = get_object_or_404(Loan, pk=pk)
        if not loan.can_user_approve(request.user):
            messages.error(request, f"Permission Denied: You are not authorized to approve Tier {loan.approval_tier} for Loan #{loan.loan_number}.")
            return redirect('loan_approval_queue')

        notes = request.POST.get('approval_notes', '')
        new_status = loan.approve(request.user, notes)

        if new_status == 'approved':
            messages.success(request, f"Loan #{loan.loan_number} (₹{loan.principal_amount:,.2f}) has received FINAL APPROVAL and is now READY FOR DISBURSAL.")
        else:
            messages.info(request, f"Tier Approval granted for Loan #{loan.loan_number}. Advanced to next checker level.")

        return redirect('loan_approval_queue')


class LoanRejectActionView(LoginRequiredMixin, View):
    """Action to reject loan application with mandatory reason"""
    def post(self, request, pk):
        loan = get_object_or_404(Loan, pk=pk)
        reason = request.POST.get('rejection_reason', '').strip()
        if not reason:
            messages.error(request, "Rejection reason is mandatory when declining a loan application.")
            return redirect('loan_approval_queue')

        loan.reject(request.user, reason)
        messages.warning(request, f"Loan application #{loan.loan_number} has been officially REJECTED. Reason recorded.")
        return redirect('loan_approval_queue')


class LoanReappraisalActionView(LoginRequiredMixin, View):
    """Action to send loan back for physical re-appraisal / weight re-verification"""
    def post(self, request, pk):
        loan = get_object_or_404(Loan, pk=pk)
        notes = request.POST.get('reappraisal_notes', '').strip()
        if not notes:
            messages.error(request, "Re-appraisal notes / instructions are required.")
            return redirect('loan_approval_queue')

        loan.request_reappraisal(request.user, notes)
        messages.info(request, f"Loan #{loan.loan_number} sent back to Appraiser for physical re-appraisal.")
        return redirect('loan_approval_queue')


# ==============================================================================
# Customer OTP Identity Verification & Post-Approval Disbursal Actions
# ==============================================================================

class LoanVerifyOTPView(LoginRequiredMixin, View):
    """
    Validates customer 6-digit OTP code before loan approval.
    """
    def post(self, request, pk):
        loan = get_object_or_404(Loan, pk=pk)
        entered_otp = request.POST.get('otp_code', '').strip()
        if not entered_otp:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Please enter the 6-digit OTP code.'}, status=400)
            messages.error(request, 'Please enter the 6-digit OTP code.')
            return redirect('loan_detail', loan_number=loan.loan_number)

        success, msg = loan.verify_otp(entered_otp, user=request.user)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': success, 'message': msg})

        if success:
            messages.success(request, f"✅ {msg}")
        else:
            messages.error(request, f"❌ {msg}")
        return redirect('loan_detail', loan_number=loan.loan_number)


class LoanResendOTPView(LoginRequiredMixin, View):
    """
    Regenerates a fresh 6-digit OTP and dispatches it via background WhatsApp worker.
    """
    def post(self, request, pk):
        loan = get_object_or_404(Loan, pk=pk)
        new_otp = loan.generate_otp(save=True)
        from transactions.services_whatsapp_automator import send_loan_otp_whatsapp_async
        send_loan_otp_whatsapp_async(loan.id, user_id=request.user.id)

        wa_link = loan.get_otp_whatsapp_link()
        msg = f"Fresh 6-digit OTP generated and sent to {loan.customer.full_name}'s mobile ({loan.customer.phone})."

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': msg,
                'otp_code': new_otp,
                'whatsapp_link': wa_link
            })

        messages.info(request, f"📲 {msg}")
        return redirect('loan_detail', loan_number=loan.loan_number)


class LoanDisburseActionView(LoginRequiredMixin, View):
    """
    Executes money payout/disbursement to the customer after manager approval.
    Transitions loan status from 'approved' to 'active'.
    Enforces Income Tax Section 269SS cash disbursement caps (< ₹20,000).
    """
    def post(self, request, pk):
        loan = get_object_or_404(Loan, pk=pk)

        if loan.status != 'approved' or not loan.is_approved_for_disbursal:
            messages.error(
                request,
                f"Disbursal Blocked: Loan #{loan.loan_number} is currently '{loan.get_status_display()}'. "
                f"Full Manager Approval is required before disbursing money."
            )
            return redirect('loan_detail', loan_number=loan.loan_number)

        payment_mode = request.POST.get('disbursement_mode', 'CASH').upper()
        account_number = request.POST.get('account_number', '').strip()
        ifsc_code = request.POST.get('ifsc_code', '').strip().upper()
        bank_name = request.POST.get('bank_name', '').strip()
        beneficiary_name = request.POST.get('beneficiary_name', '').strip() or loan.customer.full_name
        utr_number = request.POST.get('utr_number', '').strip()
        notes = request.POST.get('notes', '').strip()

        disbursal_amt = loan.distribution_amount
        if disbursal_amt is None:
            disbursal_amt = (loan.principal_amount or Decimal('0')) - (loan.processing_fee or Decimal('0'))

        # Sec 269SS statutory validation
        if payment_mode == 'CASH' and Decimal(str(disbursal_amt)) >= Decimal('20000.00'):
            messages.error(
                request,
                "Section 269SS Violation: Cash disbursals of ₹20,000 or more are prohibited by Income Tax law. "
                "Please select Bank Transfer, UPI, or Cheque."
            )
            return redirect('loan_detail', loan_number=loan.loan_number)

        if payment_mode in ['BANK_TRANSFER', 'NEFT', 'IMPS', 'RTGS']:
            if not account_number or not ifsc_code:
                messages.error(request, "Bank Account Number and IFSC Code are required for Bank Transfer disbursals.")
                return redirect('loan_detail', loan_number=loan.loan_number)

        # Update or create processed DisbursementTransaction
        disb, _ = DisbursementTransaction.objects.update_or_create(
            loan=loan,
            defaults={
                'payment_mode': payment_mode,
                'amount': disbursal_amt,
                'account_number': account_number,
                'ifsc_code': ifsc_code,
                'bank_name': bank_name,
                'beneficiary_name': beneficiary_name,
                'utr_number': utr_number,
                'disbursed_by': request.user,
                'disbursed_at': timezone.now(),
                'bank_status': 'PROCESSED',
                'notes': notes
            }
        )

        # Transition loan to active
        loan.status = 'active'
        loan.save(update_fields=['status'])

        # Auto-create Payment record for processing fee if collected upfront
        try:
            if loan.is_processing_fee_paid and loan.processing_fee and loan.processing_fee > 0:
                Payment.objects.get_or_create(
                    loan=loan,
                    notes=f'Processing Fee collected upfront at loan creation (Loan #{loan.loan_number})',
                    defaults={
                        'amount': Decimal(str(loan.processing_fee)),
                        'payment_date': loan.issue_date,
                        'payment_method': 'cash',
                        'received_by': request.user,
                    }
                )
        except Exception as e:
            logging.getLogger(__name__).warning("Error creating upfront processing fee payment on disbursal: %s", e)

        # Auto-create Payment record for 1st month interest if collected upfront
        try:
            if loan.is_first_month_interest_paid:
                monthly_info = loan.monthly_interest
                interest_amount = Decimal(str(monthly_info.get('amount', 0))) if isinstance(monthly_info, dict) else Decimal('0')
                if interest_amount > 0:
                    Payment.objects.get_or_create(
                        loan=loan,
                        notes=f'1st Month Interest collected upfront at loan creation (Loan #{loan.loan_number})',
                        defaults={
                            'amount': interest_amount,
                            'payment_date': loan.issue_date,
                            'payment_method': 'cash',
                            'received_by': request.user,
                        }
                    )
        except Exception as e:
            logging.getLogger(__name__).warning("Error creating upfront 1st month interest payment on disbursal: %s", e)

        # Audit log
        try:
            from accounts.models import LoanEditLog
            LoanEditLog.objects.create(
                loan=loan,
                edited_by=request.user,
                change_type='disbursed',
                description=f"Loan disbursed (₹{disbursal_amt:,.2f} via {payment_mode}) by {request.user.get_full_name() or request.user.username}. Loan is now ACTIVE."
            )
        except Exception:
            pass

        messages.success(
            request,
            f"🎉 Money Disbursed Successfully! ₹{disbursal_amt:,.2f} handed over / transferred to {loan.customer.full_name}. Loan #{loan.loan_number} is now ACTIVE."
        )
        return redirect('loan_detail', loan_number=loan.loan_number)




