from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.http import Http404, HttpResponse, JsonResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
import csv
from .models import Loan, Payment, LoanExtension, Sale
from .forms import LoanForm, SaleForm, LoanExtensionForm
from .utils import ManagerPermissionMixin
from django.db.models import Q
from num2words import num2words
from django.core.files.base import ContentFile
from decimal import Decimal
import base64
import json
import ast
import os
import shutil
import subprocess
import tempfile
import re
from django.conf import settings
from urllib.parse import urlparse
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from utils.download_utils import DownloadMixin
from utils.translation import translate_text


def translate_text_for_pdf(text, target_lang='ta'):
    """Translate a short piece of text for PDF output, with safe fallbacks."""
    if not text:
        return ''

    if target_lang == 'en':
        return text

    try:
        import requests

        response = requests.get(
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
            timeout=10,
        )
        response.raise_for_status()
        payload = json.loads(response.content.decode('utf-8', errors='replace'))
        translated = ''.join(part[0] for part in payload[0] if part and part[0]).strip()
        if translated and translated.replace('?', '').strip():
            return translated
    except Exception:
        pass

    translated = translate_text(text, target_lang=target_lang)
    if translated:
        return translated

    return text


def format_mobile_number(value):
    """Format to '85758 69850' from phone-like input."""
    digits = re.sub(r'\D', '', str(value or ''))
    if len(digits) >= 10:
        digits = digits[-10:]
    return f"{digits[:5]} {digits[5:]}" if len(digits) == 10 else digits


def build_loan_pdf_language_context(loan, current_language):
    use_tamil = str(current_language).startswith('ta')
    customer = loan.customer
    loan_items = list(loan.loanitem_set.select_related('item'))
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
    branch_phone_display = format_mobile_number(branch.phone) if branch and getattr(branch, 'phone', None) else ''

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
        'issue_date': 'Issue Date',
        'due_date': 'Due Date',
        'gold_items_details': 'Gold Items Details',
        'item_description': 'Item Description',
        'gold_karat': 'Gold Karat',
        'gross_weight': 'Gross Weight (g)',
        'net_weight': 'Net Weight (g)',
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
            'gold_items_details': 'தங்கப் பொருட்கள் விவரம்',
            'item_description': 'பொருள் விவரம்',
            'gold_karat': 'தங்க சுத்தம்',
            'gross_weight': 'மொத்த எடை (கி)',
            'net_weight': 'நிகர எடை (கி)',
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
        }
    else:
        labels = label_keys

    scheme_name = loan.scheme.name if loan.scheme else 'Standard Gold Loan'
    scheme_interest = loan.scheme.interest_rate if loan.scheme else loan.interest_rate
    scheme_duration = loan.scheme.loan_duration if loan.scheme and loan.scheme.loan_duration else 0
    display_scheme_name = scheme_name

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
            'content': 'The loan is repayable before the due date. If not repaid, the lender may sell the pledged article as per applicable law.'
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
            {'title': '2. கடனின் நோக்கம்:', 'content': 'இந்தக் கடன் தங்கப் பொருட்களை அடமானமாக வைத்து வழங்கப்படுகிறது.'},
            {'title': '3. தங்கம் மீட்பு:', 'content': 'முதன்மை தொகையும் வட்டியும் முழுமையாக செலுத்திய பின் தங்கம் மீட்கப்படும்.'},
            {'title': '4. KYC இணக்கம்:', 'content': 'RBI வழிகாட்டுதலின்படி KYC விவரங்கள் சரிபார்க்கப்பட்டுள்ளன.'},
            {'title': '5. நியாய நடைமுறை:', 'content': 'கடன் வழங்கல் நடைமுறைகள் நியாயமாக பின்பற்றப்படும்.'},
            {'title': '6. திருப்பிச் செலுத்தல்:', 'content': 'கடைசி தேதிக்குள் கடன் தொகை செலுத்தப்பட வேண்டும்.'},
            {'title': '7. ரசீது அவசியம்:', 'content': 'ஒவ்வொரு கட்டணத்திற்கும் ரசீது வழங்கப்படும்.'},
            {'title': '8. அறிவிப்பு:', 'content': 'மேலே உள்ள தகவல்கள் அனைத்தும் உண்மை என கடன் வாங்கியவர் அறிவிக்கிறார்.'},
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

    return {
        'current_language': current_language,
        'labels': labels,
        'localized_items': localized_items,
        'unique_item_names_count': unique_item_names_count,
        'total_items_count': total_items_count,
        'customer_name_display': customer_name_ta if use_tamil else customer_name_en,
        'customer_phone_display': customer_phone_display,
        'customer_address_display': customer_address_ta if use_tamil else customer_address_en,
        'customer_id_type_display': customer_id_label_ta if use_tamil else customer_id_label_en,
        'branch_address_display': branch_address_ta if use_tamil else branch_address_en,
        'branch_phone_display': branch_phone_display,
        'terms_list': terms,
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


def transliterate_between_english_tamil(request):
    text = (request.GET.get('text') or '').strip()
    direction = request.GET.get('direction', 'to_tamil')

    if not text:
        return JsonResponse({'result': ''})

    try:
        import requests

        source_lang = 'ta' if direction == 'to_english' else 'en'
        target_lang = 'en' if direction == 'to_english' else 'ta'
        translated_result = ''
        for _ in range(2):
            response = requests.get(
                'https://translate.googleapis.com/translate_a/single',
                params={
                    'client': 'gtx',
                    'sl': source_lang,
                    'tl': target_lang,
                    'dt': 't',
                    'q': text,
                },
                headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/json,text/plain,*/*',
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = json.loads(response.content.decode('utf-8', errors='replace'))
            translated_result = ''.join(part[0] for part in payload[0] if part and part[0]).strip()
            if translated_result and translated_result != text and translated_result.replace('?', '').strip():
                return JsonResponse({'result': translated_result})
    except Exception:
        pass

    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate

        if direction == 'to_english':
            result = transliterate(text, sanscript.TAMIL, sanscript.ITRANS)
        else:
            result = transliterate(text, sanscript.ITRANS, sanscript.TAMIL)

        return JsonResponse({'result': result})
    except Exception as exc:
        return JsonResponse({'result': text, 'error': str(exc)}, status=200)


# --- Number to words helpers (English and Tamil) ---
def amount_to_english_words(amount):
    """Convert a numeric amount to English words (rupees and paise).

    Falls back to simple formatting if num2words fails for a value.
    """
    try:
        dec = Decimal(amount)
    except Exception:
        return ''

    rupees = int(dec)
    paise = int((dec - rupees) * 100)

    try:
        # Prefer en_IN if available for Indian grouping, else en
        try:
            words_rupees = num2words(rupees, lang='en_IN')
        except Exception:
            words_rupees = num2words(rupees, lang='en')
        words = f"{words_rupees.capitalize()} rupees"
        if paise:
            words_paise = num2words(paise, lang='en')
            words += f" and {words_paise} paise"
        return words
    except Exception:
        # Fallback to simple string
        return f"{rupees} rupees{(' and ' + str(paise) + ' paise') if paise else ''}"


def _int_to_tamil_under_thousand(n):
    """Convert integer < 1000 to Tamil words."""
    ones = {
        0: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â¯Ã¢â‚¬Å¡ÃƒÂ Ã‚Â®Ã…â€œÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â¯ÃƒÂ Ã‚Â®Ã‚Â®ÃƒÂ Ã‚Â¯Ã‚Â', 1: 'ÃƒÂ Ã‚Â®Ã¢â‚¬â„¢ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚Â', 2: 'ÃƒÂ Ã‚Â®Ã¢â‚¬Â¡ÃƒÂ Ã‚Â®Ã‚Â°ÃƒÂ Ã‚Â®Ã‚Â£ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã…Â¸ÃƒÂ Ã‚Â¯Ã‚Â', 3: 'ÃƒÂ Ã‚Â®Ã‚Â®ÃƒÂ Ã‚Â¯Ã¢â‚¬Å¡ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚Â', 4: 'ÃƒÂ Ã‚Â®Ã‚Â¨ÃƒÂ Ã‚Â®Ã‚Â¾ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã¢â‚¬Â¢ÃƒÂ Ã‚Â¯Ã‚Â', 5: 'ÃƒÂ Ã‚Â®Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â¨ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â',
        6: 'ÃƒÂ Ã‚Â®Ã¢â‚¬Â ÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚Â', 7: 'ÃƒÂ Ã‚Â®Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â´ÃƒÂ Ã‚Â¯Ã‚Â', 8: 'ÃƒÂ Ã‚Â®Ã…Â½ÃƒÂ Ã‚Â®Ã…Â¸ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã…Â¸ÃƒÂ Ã‚Â¯Ã‚Â', 9: 'ÃƒÂ Ã‚Â®Ã¢â‚¬â„¢ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â', 10: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â', 11: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â®Ã‚Â¿ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã…Â ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚Â',
        12: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â®Ã‚Â¿ÃƒÂ Ã‚Â®Ã‚Â°ÃƒÂ Ã‚Â®Ã‚Â£ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã…Â¸ÃƒÂ Ã‚Â¯Ã‚Â', 13: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â®Ã‚Â¿ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â®ÃƒÂ Ã‚Â¯Ã¢â‚¬Å¡ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚Â', 14: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â®Ã‚Â¿ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â®Ã‚Â¾ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã¢â‚¬Â¢ÃƒÂ Ã‚Â¯Ã‚Â', 15: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â®Ã‚Â¿ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‹â€ ÃƒÂ Ã‚Â®Ã‚Â¨ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â',
        16: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â®Ã‚Â¿ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â®Ã‚Â¾ÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚Â', 17: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â®Ã‚Â¿ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã¢â‚¬Â¡ÃƒÂ Ã‚Â®Ã‚Â´ÃƒÂ Ã‚Â¯Ã‚Â', 18: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â®Ã‚Â¿ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã¢â‚¬Â ÃƒÂ Ã‚Â®Ã…Â¸ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã…Â¸ÃƒÂ Ã‚Â¯Ã‚Â', 19: 'ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã…Â ÃƒÂ Ã‚Â®Ã‚Â©ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â'
    }
    tens = {
        20: 'ÃƒÂ Ã‚Â®Ã¢â‚¬Â¡ÃƒÂ Ã‚Â®Ã‚Â°ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â', 30: 'ÃƒÂ Ã‚Â®Ã‚Â®ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â', 40: 'ÃƒÂ Ã‚Â®Ã‚Â¨ÃƒÂ Ã‚Â®Ã‚Â¾ÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â', 50: 'ÃƒÂ Ã‚Â®Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â®ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â', 60: 'ÃƒÂ Ã‚Â®Ã¢â‚¬Â¦ÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â',
        70: 'ÃƒÂ Ã‚Â®Ã…Â½ÃƒÂ Ã‚Â®Ã‚Â´ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â', 80: 'ÃƒÂ Ã‚Â®Ã…Â½ÃƒÂ Ã‚Â®Ã‚Â£ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã‚Â', 90: 'ÃƒÂ Ã‚Â®Ã‚Â¤ÃƒÂ Ã‚Â¯Ã…Â ÃƒÂ Ã‚Â®Ã‚Â£ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â£ÃƒÂ Ã‚Â¯Ã¢â‚¬Å¡ÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚Â'
    }

    parts = []
    if n >= 100:
        h = n // 100
        if h > 0:
            if h == 1:
                parts.append('ÃƒÂ Ã‚Â®Ã‚Â¨ÃƒÂ Ã‚Â¯Ã¢â‚¬Å¡ÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚Â')
            else:
                parts.append(ones.get(h, '') + ' ÃƒÂ Ã‚Â®Ã‚Â¨ÃƒÂ Ã‚Â¯Ã¢â‚¬Å¡ÃƒÂ Ã‚Â®Ã‚Â±ÃƒÂ Ã‚Â¯Ã‚Â')
        n = n % 100

    if n >= 20:
        t = (n // 10) * 10
        if t in tens:
            parts.append(tens[t])
            r = n % 10
            if r:
                parts.append(ones.get(r, ''))
        else:
            parts.append(ones.get(n, ''))
    elif n > 0:
        parts.append(ones.get(n, ''))

    return ' '.join([p for p in parts if p])


def number_to_tamil_words(amount):
    """Convert numeric amount to Tamil words (Indian grouping)."""
    try:
        dec = Decimal(amount)
    except Exception:
        return ''

    rupees = int(dec)
    paise = int((dec - rupees) * 100)

    if rupees == 0:
        rupees_words = 'ÃƒÂ Ã‚Â®Ã…Â¡ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã‚Â´ÃƒÂ Ã‚Â®Ã‚Â¿ÃƒÂ Ã‚Â®Ã‚Â¯ÃƒÂ Ã‚Â®Ã‚Â®ÃƒÂ Ã‚Â¯Ã‚Â'
    else:
        parts = []
        crore = rupees // 10000000
        if crore:
            parts.append(f"{_int_to_tamil_under_thousand(crore)} ÃƒÂ Ã‚Â®Ã¢â‚¬Â¢ÃƒÂ Ã‚Â¯Ã¢â‚¬Â¹ÃƒÂ Ã‚Â®Ã…Â¸ÃƒÂ Ã‚Â®Ã‚Â¿")
        rupees = rupees % 10000000

        lakh = rupees // 100000
        if lakh:
            parts.append(f"{_int_to_tamil_under_thousand(lakh)} ÃƒÂ Ã‚Â®Ã‚Â²ÃƒÂ Ã‚Â®Ã…Â¸ÃƒÂ Ã‚Â¯Ã‚ÂÃƒÂ Ã‚Â®Ã…Â¡ÃƒÂ Ã‚Â®Ã‚Â®ÃƒÂ Ã‚Â¯Ã‚Â")
        rupees = rupees % 100000

        thousand = rupees // 1000
        if thousand:
            parts.append(f"{_int_to_tamil_under_thousand(thousand)} ÃƒÂ Ã‚Â®Ã¢â‚¬Â ÃƒÂ Ã‚Â®Ã‚Â¯ÃƒÂ Ã‚Â®Ã‚Â¿ÃƒÂ Ã‚Â®Ã‚Â°ÃƒÂ Ã‚Â®Ã‚Â®ÃƒÂ Ã‚Â¯Ã‚Â")
        rupees = rupees % 1000

        if rupees:
            parts.append(_int_to_tamil_under_thousand(rupees))

        rupees_words = ' '.join([p for p in parts if p])

    result = f"{rupees_words} ÃƒÂ Ã‚Â®Ã‚Â°ÃƒÂ Ã‚Â¯Ã¢â‚¬Å¡ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â¾ÃƒÂ Ã‚Â®Ã‚Â¯ÃƒÂ Ã‚Â¯Ã‚Â"
    if paise:
        paise_words = _int_to_tamil_under_thousand(paise)
        result = f"{result} {paise_words} ÃƒÂ Ã‚Â®Ã‚ÂªÃƒÂ Ã‚Â®Ã‚Â£ÃƒÂ Ã‚Â¯Ã‹â€ "
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


class LoanExpiryNoticeView(LoginRequiredMixin, View):
    """Render a printable A4 expiry/auction notice for a loan.

    - Renders HTML suitable for printing (A4) and for PDF conversion.
    - Only shows for loans that are overdue or defaulted; other loans will show a simple page explaining status.
    """
    def get(self, request, loan_number, *args, **kwargs):
        loan = get_object_or_404(Loan, loan_number=loan_number)
        # Determine if eligible for notice
        from django.utils import timezone
        today = timezone.now().date()
        gp_end = getattr(loan, 'grace_period_end', None)
        show_notice = False
        if loan.status == 'defaulted' or (loan.status == 'active' and loan.is_overdue and gp_end and gp_end <= today):
            show_notice = True

        # company details (if configured via gst app)
        company = None
        try:
            from gst.models import CompanyGSTDetails
            company = CompanyGSTDetails.objects.first()
        except Exception:
            company = None

        # language selection
        current_language = getattr(request, 'LANGUAGE_CODE', None) or ''
        use_tamil = str(current_language).startswith('ta')

        context = {
            'loan': loan,
            'show_notice': show_notice,
            'today': today,
            'company': company,
            'use_tamil': use_tamil,
        }

        # Render HTML (printable A4). Frontend can print via browser or we can convert to PDF.
        return render(request, 'transactions/loan_expiry_notice.html', context)



# Basic placeholder views for the transactions app
# These will need to be implemented properly with the correct models

class LoanListView(LoginRequiredMixin, DownloadMixin, ListView):
    model = Loan
    template_name = 'transactions/loan_list.html'
    context_object_name = 'loans'
    paginate_by = 15
    
    def get_queryset(self):
        queryset = Loan.objects.all()
        user = self.request.user

        # First filter by organization
        if user.organization:
            queryset = queryset.filter(branch__organization=user.organization)

        # Then filter by branch if needed
        # Branch managers can only see loans from their branch
        # Regional managers and superusers can see all loans within their organization
        if not user.is_superuser and user.branch:
            if not hasattr(user, 'role') or not user.role or not user.role.name.lower() == 'regional manager':
                queryset = queryset.filter(branch=user.branch)

        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(loan_number__icontains=search) |
                Q(loanitem__item__name__icontains=search)
            ).distinct()

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

        # New filter for overdue loans
        filter_type = self.request.GET.get('filter_type')
        if filter_type == 'overdue':
            queryset = queryset.filter(status='active', due_date__lt=today)

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
        return f'loans_export_{timestamp}.{format_type}'

    def get_download_headers(self):
        """Return headers for download export"""
        all_headers = [
            ('roll_number', 'Roll Number'),
            ('loan_number', 'Loan Number'),
            ('customer_name', 'Customer Name'),
            ('phone', 'Customer Phone'),
            ('email', 'Customer Email'), 
            ('branch', 'Branch'),
            ('item_images', 'Item Images'),
            ('principal_amount', 'Principal Amount (₹)'),
            ('distribution_amount', 'Distribution Amount (₹)'),
            ('interest_rate', 'Interest Rate (%)'),
            ('issue_date', 'Issue Date'),
            ('due_date', 'Due Date'),
            ('status', 'Status'),
            ('days_since_issue', 'Days Since Issue'),
            ('days_remaining', 'Days Remaining'),
            ('item_names', 'Item Names'),
            ('total_weight', 'Total Weight (grams)'),
            ('karat', 'Gold Karat'),
            ('monthly_interest', 'Monthly Interest Amount (₹)'),
            ('total_payable', 'Total Payable Till Date (₹)'),
            ('amount_paid', 'Amount Paid (₹)'),
            ('remaining_balance', 'Remaining Balance (₹)'),
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
            
            # Calculate financial information
            try:
                monthly_interest = 0
                if hasattr(loan, 'monthly_interest_amount'):
                    monthly_interest = float(loan.monthly_interest_amount())
                
                total_payable = 0
                if hasattr(loan, 'total_payable_till_date'):
                    total_payable = float(loan.total_payable_till_date)
                
                amount_paid = 0
                if hasattr(loan, 'amount_paid'):
                    amount_paid = float(loan.amount_paid)
                
                remaining_balance = total_payable - amount_paid
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
                ', '.join(loan.item_photo_list) if hasattr(loan, 'item_photo_list') and loan.item_photo_list else '',
                float(loan.principal_amount) if loan.principal_amount else 0,
                float(loan.distribution_amount) if hasattr(loan, 'distribution_amount') and loan.distribution_amount else 0,
                float(loan.interest_rate) if loan.interest_rate else 0,
                loan.issue_date.strftime('%Y-%m-%d') if loan.issue_date else '',
                loan.due_date.strftime('%Y-%m-%d') if loan.due_date else '',
                loan.get_status_display() if hasattr(loan, 'get_status_display') else (loan.status or ''),
                days_since_issue,
                days_remaining,
                ', '.join(item_names) if item_names else '',
                total_weight,
                ', '.join(sorted(karat_info)) if karat_info else '',
                monthly_interest,
                total_payable,
                amount_paid,
                remaining_balance,
                loan.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(loan, 'created_at') and loan.created_at else '',
                f"{loan.created_by.first_name} {loan.created_by.last_name}" if hasattr(loan, 'created_by') and loan.created_by else ''
            ]
            data.append(row)
        
        return data

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
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from datetime import datetime
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="loans_export_{datetime.now().strftime("%Y%m%d")}.pdf"'
        
        doc = SimpleDocTemplate(
            response,
            pagesize=landscape(A4),
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = styles['Heading1']
        title_style.alignment = 1
        elements.append(Paragraph("LOANS EXPORT", title_style))
        elements.append(Spacer(1, 20))
        
        # Create table with loan data
        headers = self.get_download_headers()
        table_data = [headers]
        
        selected_columns = self.get_selected_columns()
        for row in self.get_download_data():
            filtered_row = self.filter_row_data(row, selected_columns)
            table_data.append(filtered_row)
        
        # Create table
        table = Table(table_data)
        table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            
            # Data rows
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BDC3C7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        # Footer
        footer_style = styles['Normal']
        footer_style.alignment = 1
        footer_style.fontSize = 8
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y at %I:%M %p')}", footer_style))
        
        # Build PDF
        doc.build(elements)
        return response

    def download_csv(self):
        return self.export_csv()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_date_range'] = self.request.GET.get('date_range', '')
        context['selected_filter_type'] = self.request.GET.get('filter_type', '') # Add this for the new filter
        context['current_sort'] = self.request.GET.get('sort', '-issue_date')
        
        # Calculate loan statistics for the cards
        user = self.request.user
        base_queryset = Loan.objects.all()
        
        # Apply same organization and branch filtering as in get_queryset
        if user.organization:
            base_queryset = base_queryset.filter(branch__organization=user.organization)
        
        if not user.is_superuser and user.branch:
            if not hasattr(user, 'role') or not user.role or not user.role.name.lower() == 'regional manager':
                base_queryset = base_queryset.filter(branch=user.branch)
        
        # Calculate statistics
        from django.utils import timezone
        from django.db.models import Sum
        from decimal import Decimal
        
        today = timezone.now().date()
        
        # Active loans count
        context['active_loans_count'] = base_queryset.filter(status='active').count()
        
        # Due today count
        context['due_today_count'] = base_queryset.filter(
            status='active',
            due_date=today
        ).count()
        
        # Overdue count
        context['overdue_count'] = base_queryset.filter(
            status='active',
            due_date__lt=today
        ).count()
        
        # Total outstanding amount
        outstanding_loans = base_queryset.filter(status='active')
        total_outstanding = Decimal('0.00')
        for loan in outstanding_loans:
            try:
                if hasattr(loan, 'total_payable_till_date'):
                    total_outstanding += loan.total_payable_till_date - loan.amount_paid
            except:
                pass
        context['total_outstanding'] = total_outstanding

        # Visibility controls: show financial summary only for admin users
        is_admin_user = bool((user.username == 'admin') or user.is_staff or user.is_superuser or getattr(user, 'is_pawnshop_admin', False) or getattr(user, 'is_organization_admin', False))
        context['show_total_outstanding'] = is_admin_user
        context['show_total_loan_lists'] = is_admin_user
        return context


class LoanDetailView(LoginRequiredMixin, DetailView):
    model = Loan
    template_name = 'transactions/loan_detail.html'
    context_object_name = 'loan'
    slug_field = 'loan_number'
    slug_url_kwarg = 'loan_number'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan = self.get_object()
        
        # Add payments and other related data to context
        context['payments'] = loan.payments.all().order_by('-payment_date')
        context['extensions'] = loan.extensions.all().order_by('-extension_date')
        context['loan_items'] = loan.loanitem_set.all()
        
        # Process item photos for the template using centralized function
        context['item_photos_list'] = process_item_photos_for_display(loan.item_photos)
        print(f"Retrieved {len(context['item_photos_list'])} item photos from database for loan {loan.loan_number}")
            
        return context


class LoanCreateView(LoginRequiredMixin, CreateView):
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
        
        # Process item photos for form if editing existing loan
        if self.object and self.object.item_photos:
            context['item_photos_list'] = process_item_photos_for_display(self.object.item_photos)
        return context
    
    def form_valid(self, form):
        # Handle photo processing during loan creation
        item_photos_data = self.request.POST.get('item_photos', '')
        customer_face_capture = self.request.POST.get('customer_face_capture', '')
        
        # Save photos directly to database
        if item_photos_data:
            form.instance.item_photos = item_photos_data
        if customer_face_capture:
            form.instance.customer_face_capture = customer_face_capture
            
        # Set the branch and created_by
        if self.request.user.branch:
            form.instance.branch = self.request.user.branch
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
        
        messages.success(self.request, 'Loan created successfully!')
        return super().form_valid(form)


class LoanUpdateView(LoginRequiredMixin, UpdateView):
    model = Loan
    form_class = LoanForm
    template_name = 'transactions/loan_form.html'
    slug_field = 'loan_number'
    slug_url_kwarg = 'loan_number'
    
    def get_success_url(self):
        return reverse('loan_detail', kwargs={'loan_number': self.object.loan_number})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Process item photos for form editing
        if self.object and self.object.item_photos:
            context['item_photos_list'] = process_item_photos_for_display(self.object.item_photos)
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
            
        messages.success(self.request, 'Loan updated successfully!')
        return super().form_valid(form)


class LoanDeleteView(LoginRequiredMixin, ManagerPermissionMixin, DeleteView):
    model = Loan
    template_name = 'transactions/loan_confirm_delete.html'
    slug_field = 'loan_number'
    slug_url_kwarg = 'loan_number'
    context_object_name = 'loan'
    success_url = reverse_lazy('loan_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        loan_number = self.object.loan_number
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'Loan {loan_number} has been deleted successfully.')
        return response


class PaymentCreateView(LoginRequiredMixin, CreateView):
    model = Payment
    template_name = 'transactions/payment_form.html'
    fields = ['amount', 'payment_date', 'payment_method', 'reference_number', 'notes']
    
    def get_initial(self):
        """Set default values for form fields"""
        initial = super().get_initial()
        # Set payment_date to today's date
        initial['payment_date'] = timezone.now().date()
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan_number = self.kwargs.get('loan_number')
        loan = get_object_or_404(Loan, loan_number=loan_number)
        context['loan'] = loan
        
        # Calculate remaining balance for full payment
        try:
            remaining_balance = loan.total_payable_till_date - loan.amount_paid
            context['remaining_balance'] = max(remaining_balance, 0)
        except:
            context['remaining_balance'] = 0
            
        return context
    
    def form_valid(self, form):
        loan_number = self.kwargs.get('loan_number')
        loan = get_object_or_404(Loan, loan_number=loan_number)
        
        # Check if loan can accept payments
        if loan.status not in ['active', 'overdue']:
            messages.error(self.request, f'Cannot record payment for loan {loan_number}. Current status: {loan.get_status_display()}')
            return redirect('loan_detail', loan_number=loan_number)
        
        form.instance.loan = loan
        form.instance.received_by = self.request.user
        
        # Calculate remaining balance before this payment
        try:
            remaining_balance = loan.total_payable_till_date - loan.amount_paid
            payment_amount = form.instance.amount
            
            # Check if this payment will fully settle the loan
            will_close_loan = payment_amount >= remaining_balance
            
            # Save the payment first
            response = super().form_valid(form)
            
            # If payment fully settles the loan, close it
            if will_close_loan and remaining_balance > 0:
                loan.status = 'closed'
                loan.closure_date = timezone.now().date()
                loan.closed_by = self.request.user
                loan.save()
                
                messages.success(
                    self.request, 
                    f'Payment recorded successfully! Loan {loan_number} has been automatically closed as the full amount has been paid.'
                )
            else:
                messages.success(self.request, 'Payment recorded successfully!')
                
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


class LoanExtensionCreateView(LoginRequiredMixin, CreateView):
    model = LoanExtension
    form_class = LoanExtensionForm
    template_name = 'transactions/loan_extension_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan_number = self.kwargs.get('loan_number')
        context['loan'] = get_object_or_404(Loan, loan_number=loan_number)
        return context
    
    def form_valid(self, form):
        loan_number = self.kwargs.get('loan_number')
        loan = get_object_or_404(Loan, loan_number=loan_number)
        form.instance.loan = loan
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Loan extension created successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('loan_detail', kwargs={'loan_number': self.kwargs.get('loan_number')})


class LoanForecloseView(LoginRequiredMixin, View):
    def get(self, request, loan_number):
        """Handle GET request - show confirmation page"""
        loan = get_object_or_404(Loan, loan_number=loan_number)
        
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
        
        # Check if loan can be foreclosed
        if loan.status not in ['active', 'overdue']:
            messages.error(request, f'Loan {loan_number} cannot be foreclosed. Current status: {loan.get_status_display()}')
            return redirect('loan_detail', loan_number=loan_number)
        
        # Update loan status
        loan.status = 'foreclosed'
        loan.foreclosure_date = timezone.now().date()
        loan.foreclosed_by = request.user
        loan.save()
        
        messages.success(request, f'Loan {loan_number} has been successfully foreclosed.')
        return redirect('loan_detail', loan_number=loan_number)


class LoanDocumentView(LoginRequiredMixin, View):
    def get(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
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

        loan_items = loan.loanitem_set.all()
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
        
        # Ensure we have loan items
        loan_items = loan.loanitem_set.all()
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


class LoanPaymentHistoryDownloadView(LoginRequiredMixin, View):
    def get(self, request, loan_number):
        loan = get_object_or_404(Loan, loan_number=loan_number)
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
            if hasattr(branch_info, 'phone') and branch_info.phone:
                contact_parts.append(f"Phone: {branch_info.phone}")
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
        remaining_balance = max(0, loan.total_payable_till_date - total_amount_paid)
        
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


class PaymentReceiptView(LoginRequiredMixin, View):
    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        loan = payment.loan
        
        # Prepare amount in words (English) and Tamil
        amount_in_words = amount_to_english_words(payment.amount)
        amount_in_words_tamil = number_to_tamil_words(payment.amount)

        # Keep receipt generation fast by avoiding runtime network translation.
        payment.notes_tamil = payment.notes or ''

        context = {
            'payment': payment,
            'loan': loan,
            'branch_phone_display': format_mobile_number(getattr(loan.branch, 'phone', '')) if getattr(loan, 'branch', None) else '',
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
        if self.request.user.branch:
            form.instance.branch = self.request.user.branch
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
        
        # Compute English and Tamil amount-in-words for the sale total
        try:
            total_amount = sale.total_amount
        except Exception:
            total_amount = getattr(sale, 'total_amount', 0)

        sale.total_amount_in_words = amount_to_english_words(total_amount)
        sale.total_amount_in_words_tamil = number_to_tamil_words(total_amount)

        context = {
            'sale': sale,
            'branch_phone_display': format_mobile_number(getattr(sale.branch, 'phone', '')) if getattr(sale, 'branch', None) else '',
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
        words = num2words(float(number))
        return JsonResponse({'words': words})
    except (ValueError, TypeError):
        return JsonResponse({'words': 'Invalid number'}, status=400)






