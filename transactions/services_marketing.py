"""
transactions/services_marketing.py
Marketing and WhatsApp Broadcast Campaign services for Pawnshop Management.
Provides customer segmentation, bilingual marketing templates, dynamic variable
injection, and background PyWhatKit automated blast queues.
"""

import os
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import re
import logging
import time
import threading
import urllib.parse
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from accounts.models import Customer
from transactions.models import Loan
from transactions.services_whatsapp import normalize_phone_number, get_clean_phone_for_url

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pre-Built Marketing Templates (Bilingual English & Tamil)
# ---------------------------------------------------------------------------

MARKETING_TEMPLATES = {
    'festival_offer': {
        'title_en': '🎉 Festival Special Low Interest Offer (0.99%)',
        'title_ta': '🎉 திருவிழா சிறப்பு குறைவான வட்டி சலுகை (0.99%)',
        'category': 'Festival',
        'badge': 'Hot Promo',
        'body_en': (
            "✨ *FESTIVAL GOLD LOAN MELA - {organization_name}* ✨\n\n"
            "Dear *{customer_name}*,\n"
            "Celebrate this festive season with the *Lowest Gold Loan Interest Rate* in town!\n\n"
            "🌟 *Exclusive Festival Benefits:*\n"
            "• *Special Interest Rate:* Starting from just *0.99% per month*\n"
            "• *Maximum Value:* Up to *85% gold valuation* per gram\n"
            "• *Zero Processing Fee* & Instant Cash in 5 minutes\n"
            "• *Safe & Insured* bank-grade vault storage\n\n"
            "📍 Visit your nearest branch: *{branch_name}*\n"
            "📞 Contact us: *{branch_phone}*\n\n"
            "Hurry! Limited period festive offer. T&C Apply."
        ),
        'body_ta': (
            "✨ *பண்டிகை கால தங்கக் கடன் மேளா - {organization_name}* ✨\n\n"
            "அன்புள்ள *{customer_name}*,\n"
            "இந்த பண்டிகை காலத்தில் எங்கள் சிறப்பு குறைவான வட்டி சலுகையை பயன்படுத்திக் கொள்ளுங்கள்!\n\n"
            "🌟 *சிறப்பு சலுகைகள்:*\n"
            "• *குறைந்த வட்டி:* மாதம் *0.99%* மட்டுமே!\n"
            "• *அதிகபட்ச கடன் மதிப்பு:* கிராமுக்கு அதிக கடன் தொகை\n"
            "• *கட்டணம் இல்லை:* ஆவண கட்டணம் முற்றிலும் இலவசம்\n"
            "• *5 நிமிடங்களில் உடனடி ரொக்கம்!*\n"
            "• 100% பாதுகாப்பான பெட்டக வசதி\n\n"
            "📍 உங்கள் கிளை: *{branch_name}*\n"
            "📞 தொடர்பு கொள்ள: *{branch_phone}*\n\n"
            "இன்றே வருகை தந்து பலன் பெறுங்கள்! விதிமுறைகளுக்கு உட்பட்டது."
        ),
    },
    'akshaya_tritiya': {
        'title_en': '🪙 Akshaya Tritiya / Deepavali Gold Mela',
        'title_ta': '🪙 அட்சய திருதியை / தீபாவளி தங்கக் கடன் திருவிழா',
        'category': 'Seasonal',
        'badge': 'Highest Per Gram',
        'body_en': (
            "🪙 *SPECIAL GOLD LOAN UTSAV - {organization_name}* 🪙\n\n"
            "Dear *{customer_name}*,\n"
            "Get the *Highest Cash per Gram* for your gold ornaments this auspicious season!\n\n"
            "💎 *Why Choose {organization_name}?*\n"
            "• *Highest Per-Gram Rate:* ₹{gold_rate}/g valuation\n"
            "• *Flexible Repayments:* Monthly / Bullet interest schemes\n"
            "• *No Hidden Charges:* 100% transparent weighing\n"
            "• Part-release of ornaments allowed anytime!\n\n"
            "🏢 Branch: *{branch_name}* | 📞 Phone: *{branch_phone}*\n"
            "Bring your gold and walk out with instant cash in hand!"
        ),
        'body_ta': (
            "🪙 *அட்சய திருதியை / தீபாவளி சிறப்பு தங்கக் கடன் திருவிழா* 🪙\n\n"
            "அன்புள்ள *{customer_name}*,\n"
            "உங்கள் பழைய தங்க நகைகளுக்கு *கிராமுக்கு அதிகபட்ச கடன்* வழங்கும் சிறப்பு சலுகை!\n\n"
            "💎 *எங்களின் சிறப்பம்சங்கள்:*\n"
            "• *அதிகபட்ச கடன் தொகை:* கிராமுக்கு சிறந்த சந்தை மதிப்பு\n"
            "• *எளிய வட்டி திட்டம்:* உங்கள் வசதிக்கேற்ப மாதாந்திர தவணை\n"
            "• *மறைமுக கட்டணம் இல்லை:* வெளிப்படையான எடை மற்றும் பரிவர்த்தனை\n"
            "• எப்போது வேண்டுமானாலும் பகுதி நகைகளை மீட்கும் வசதி\n\n"
            "🏢 கிளை: *{branch_name}* | 📞 தொடர்பு: *{branch_phone}*\n"
            "{organization_name} - உங்கள் நம்பிக்கைக்குரிய நிதி கூட்டாளி!"
        ),
    },
    'welcome_back': {
        'title_en': '🤝 Welcome Back Loyalty Offer (For Past Borrowers)',
        'title_ta': '🤝 பழைய வாடிக்கையாளர் சிறப்பு வரவேற்பு சலுகை',
        'category': 'Re-engagement',
        'badge': 'VIP Privilege',
        'body_en': (
            "🤝 *WELCOME BACK PRIVILEGE OFFER - {organization_name}* 🤝\n\n"
            "Dear *{customer_name}*,\n"
            "We value your relationship with us! As our esteemed past customer, you are pre-approved for our *VIP Loyalty Gold Loan*.\n\n"
            "🎁 *Exclusive VIP Benefits For You:*\n"
            "• *Discounted Interest:* 0.25% lower interest rate\n"
            "• *Priority Counter:* Zero wait-time processing\n"
            "• *Top-Up Facility:* Higher loan eligibility on any gold jewellery\n\n"
            "We look forward to welcoming you again at *{branch_name}*.\n"
            "📞 Call your dedicated branch: *{branch_phone}*"
        ),
        'body_ta': (
            "🤝 *மதிப்புமிக்க வாடிக்கையாளர் சிறப்பு சலுகை - {organization_name}* 🤝\n\n"
            "அன்புள்ள *{customer_name}*,\n"
            "எங்களின் விசுவாசமான வாடிக்கையாளராக இருந்த உங்களுக்கு மீண்டும் ஒரு பிரத்யேக தங்கக் கடன் சலுகை!\n\n"
            "🎁 *உங்களுக்கான சிறப்பு நன்மைகள்:*\n"
            "• *வட்டி சலுகை:* வழக்கமான வட்டியில் 0.25% கூடுதல் தள்ளுபடி\n"
            "• *முன்னுரிமை சேவை:* காத்திருக்காமல் உடனடி கடன் பட்டுவாடா\n"
            "• *அதிகபட்ச தொகை:* உங்கள் நகைகளுக்கு அதிக கடன் வரம்பு\n\n"
            "உங்கள் வருகையை அன்புடன் வரவேற்கிறோம்!\n"
            "🏢 கிளை: *{branch_name}* | 📞 தொலைபேசி: *{branch_phone}*"
        ),
    },
    'instant_topup': {
        'title_en': '⚡ Instant Emergency Cash & Loan Top-Up Scheme',
        'title_ta': '⚡ அவசர உடனடி பண உதவி & கூடுதல் கடன் திட்டம்',
        'category': 'Urgent Funds',
        'badge': 'Instant Cash',
        'body_en': (
            "⚡ *INSTANT CASH ON GOLD - {organization_name}* ⚡\n\n"
            "Dear *{customer_name}*,\n"
            "In need of urgent funds for business, medical, or family requirements?\n\n"
            "Get *Instant Cash against Gold Jewellery* in just 5 minutes!\n\n"
            "✅ *Key Highlights:*\n"
            "• Instant cash transfer or spot cash\n"
            "• Minimal KYC documents required\n"
            "• Easy partial-release of jewellery anytime\n\n"
            "📍 Visit: *{branch_name}*\n"
            "📞 Helpline: *{branch_phone}*"
        ),
        'body_ta': (
            "⚡ *அவசர உடனடி தங்கக் கடன் - {organization_name}* ⚡\n\n"
            "அன்புள்ள *{customer_name}*,\n"
            "மருத்துவம், கல்வி அல்லது வியாபார அவசர பணத் தேவையா?\n\n"
            "உங்கள் தங்க நகைகளை வைத்து *5 நிமிடங்களில் உடனடி ரொக்கம்* பெறுங்கள்!\n\n"
            "✅ *முக்கிய சிறப்பம்சங்கள்:*\n"
            "• உடனடி வங்கி கணக்கு பரிமாற்றம் அல்லது நேரடி ரொக்கம்\n"
            "• எளிய ஆவணங்கள் மட்டும் போதும்\n"
            "• பகுதி கட்டணம் செலுத்தி நகைகளை தேவைக்கேற்ப மீட்கலாம்\n\n"
            "📍 கிளை: *{branch_name}*\n"
            "📞 தொடர்பு: *{branch_phone}*"
        ),
    },
    'ots_settlement': {
        'title_en': '🛡️ One-Time Settlement (OTS) & Interest Discount',
        'title_ta': '🛡️ ஒரே முறை தீர்வு (OTS) & வட்டி தள்ளுபடி சலுகை',
        'category': 'Settlement',
        'badge': 'Discount Offer',
        'body_en': (
            "🛡️ *SPECIAL ONE-TIME SETTLEMENT (OTS) SCHEME* 🛡️\n"
            "*{organization_name}*\n\n"
            "Dear *{customer_name}*,\n"
            "We are pleased to offer you a *Special Interest Waiver & Settlement Scheme* on your gold loan account.\n\n"
            "💡 *Limited Period Opportunity:*\n"
            "• Avail up to *50% waiver on overdue interest & late charges*\n"
            "• Settle in easy installments or single payment\n"
            "• Securely redeem all your pledged ornaments without legal or auction action\n\n"
            "Please visit your branch manager today:\n"
            "🏢 *{branch_name}* | 📞 *{branch_phone}*"
        ),
        'body_ta': (
            "🛡️ *சிறப்பு வட்டி தள்ளுபடி & ஒரே முறை தீர்வு (OTS) திட்டம்* 🛡️\n"
            "*{organization_name}*\n\n"
            "அன்புள்ள *{customer_name}*,\n"
            "உங்கள் தங்கக் கடன் கணக்கை எளிதாக முடித்து நகைகளை மீட்க சிறப்பு வட்டி தள்ளுபடி திட்டம் அறிவிக்கப்பட்டுள்ளது!\n\n"
            "💡 *சிறப்பு சலுகை விவரங்கள்:*\n"
            "• *அபராத கட்டணம் மற்றும் வட்டித் தொகையில் 50% வரை தள்ளுபடி*\n"
            "• எவ்வித ஏல நடவடிக்கையுமின்றி நகைகளை முழுமையாக மீட்கலாம்\n"
            "• எளிய தவணை முறையில் செலுத்த வாய்ப்பு\n\n"
            "உடனடியாக கிளை மேலாளரை அணுகவும்:\n"
            "🏢 *{branch_name}* | 📞 *{branch_phone}*"
        ),
    },
    'referral_promo': {
        'title_en': '🎁 Refer a Friend & Earn ₹500 Cash Reward',
        'title_ta': '🎁 நண்பரை அறிமுகம் செய்து ₹500 பரிசு பெறுங்கள்',
        'category': 'Referral',
        'badge': 'Earn Cash',
        'body_en': (
            "🎁 *REFER & EARN ₹500 REWARD - {organization_name}* 🎁\n\n"
            "Dear *{customer_name}*,\n"
            "Love our gold loan service? Introduce your friends, family, or neighbours to {organization_name} and get rewarded!\n\n"
            "💰 *How It Works:*\n"
            "1. Refer anyone looking for a Gold Loan\n"
            "2. When their loan is disbursed, YOU get an instant *₹500 Cash Reward / Account Credit*!\n"
            "3. Your friend gets *Special Discounted Interest Rates*!\n\n"
            "Unlimited referrals = Unlimited cash rewards! 🚀\n"
            "Share this with your friends and contact *{branch_name}* at *{branch_phone}*."
        ),
        'body_ta': (
            "🎁 *நண்பரை அறிமுகம் செய்து ₹500 பரிசு பெறுங்கள்!* 🎁\n"
            "*{organization_name}*\n\n"
            "அன்புள்ள *{customer_name}*,\n"
            "எங்களின் சிறந்த தங்கக் கடன் சேவையை உங்கள் நண்பர்கள், உறவினர்கள் அல்லது அண்டை வீட்டாருக்கு பரிந்துரை செய்யுங்கள்!\n\n"
            "💰 *சலுகை விவரம்:*\n"
            "1. தங்கக் கடன் தேவைப்படும் ஒருவரை அறிமுகம் செய்யுங்கள்\n"
            "2. அவர்களின் கடன் நிறைவேறும் போது உங்களுக்கு உடனடி *₹500 ரொக்கப் பரிசு* கிடைக்கும்!\n"
            "3. உங்கள் நண்பருக்கும் *குறைந்த வட்டி சலுகை* வழங்கப்படும்!\n\n"
            "எத்தனை பேரை வேண்டுமானாலும் அறிமுகம் செய்து வரம்பற்ற பரிசுகளை வெல்லுங்கள்! 🚀\n\n"
            "🏢 கிளை: *{branch_name}* | 📞 *{branch_phone}*"
        ),
    }
}


# ---------------------------------------------------------------------------
# Audience Segmentation & Group Engine
# ---------------------------------------------------------------------------

def get_all_marketing_groups(branch_id=None):
    """
    Returns all marketing groups with lead count.
    """
    from transactions.models import MarketingGroup
    from django.db.models import Count

    qs = MarketingGroup.objects.all()
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    return qs.annotate(lead_count=Count('leads')).order_by('-created_at')


def get_segmented_audience(segment_type='all', branch_id=None, group_id=None, organization=None):
    """
    Returns a list of customer/prospect dictionaries matching the segment or group criteria:
    - 'all': All registered customers with phone numbers
    - 'active_borrowers': Customers who have at least one active loan
    - 'closed_loans': Customers who had loans that are now closed/foreclosed (re-engagement prospects)
    - 'overdue': Customers who have overdue active loans
    - 'high_value': Customers with total principal > ₹1,00,000
    - 'new_prospects' / 'leads': External leads
    - 'group_<id>': All leads in a specific MarketingGroup
    """
    from transactions.models import MarketingLead

    # Handle Group Segment selection
    target_group_id = group_id
    if segment_type.startswith('group_'):
        try:
            target_group_id = int(segment_type.replace('group_', ''))
        except ValueError:
            target_group_id = None

    known_non_wa = get_known_non_whatsapp_phones()

    if target_group_id or segment_type in ('new_prospects', 'imported_leads', 'leads', 'group'):
        lead_qs = MarketingLead.objects.all().select_related('branch', 'group')
        if branch_id:
            lead_qs = lead_qs.filter(branch_id=branch_id)
        if target_group_id:
            lead_qs = lead_qs.filter(group_id=target_group_id)

        audience = []
        for lead in lead_qs:
            raw_phone = lead.phone or ''
            norm_phone = lead.norm_phone or normalize_phone_number(raw_phone)
            branch = lead.branch
            branch_name = getattr(branch, 'name', '') if branch else ''
            branch_phone = getattr(branch, 'phone', '') if branch else ''
            group_name = lead.group.name if lead.group else ''

            is_valid, status_msg, status_code = get_phone_whatsapp_status(raw_phone, norm_phone, known_non_wa)

            audience.append({
                'customer_id': f"LEAD-{lead.id}",
                'lead_id': lead.id,
                'name': lead.name or 'Valued Customer',
                'raw_phone': raw_phone,
                'norm_phone': norm_phone,
                'is_valid_whatsapp': is_valid,
                'whatsapp_status_msg': status_msg,
                'whatsapp_status_code': status_code,
                'city': lead.city or '',
                'group_id': lead.group_id,
                'group_name': group_name,
                'branch_name': branch_name,
                'branch_phone': branch_phone,
                'active_loans_count': 0,
                'total_borrowed': Decimal('0.00'),
                'is_external_lead': True,
                'source': lead.source,
            })
        return audience

    qs = Customer.objects.all().select_related('branch')
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    elif organization:
        qs = qs.filter(branch__organization=organization)

    today = timezone.now().date()

    if segment_type == 'active_borrowers':
        active_cust_ids = Loan.objects.filter(status='active').values_list('customer_id', flat=True).distinct()
        qs = qs.filter(id__in=active_cust_ids)
    elif segment_type == 'closed_loans':
        # Customers with closed/foreclosed loans and NO current active loans
        closed_cust_ids = Loan.objects.filter(status__in=['closed', 'foreclosed', 'completed']).values_list('customer_id', flat=True).distinct()
        active_cust_ids = Loan.objects.filter(status='active').values_list('customer_id', flat=True).distinct()
        qs = qs.filter(id__in=closed_cust_ids).exclude(id__in=active_cust_ids)
    elif segment_type == 'overdue':
        overdue_cust_ids = Loan.objects.filter(status='active', due_date__lt=today).values_list('customer_id', flat=True).distinct()
        qs = qs.filter(id__in=overdue_cust_ids)
    elif segment_type == 'high_value':
        # Borrowers with loan amount >= 100000
        high_val_cust_ids = Loan.objects.filter(principal_amount__gte=100000).values_list('customer_id', flat=True).distinct()
        qs = qs.filter(id__in=high_val_cust_ids)

    audience = []
    for c in qs:
        raw_phone = getattr(c, 'phone', '') or ''
        norm_phone = normalize_phone_number(raw_phone)
        full_name = getattr(c, 'full_name', None) or f"{getattr(c, 'first_name', '')} {getattr(c, 'last_name', '')}".strip() or 'Valued Customer'
        branch = getattr(c, 'branch', None)
        branch_name = getattr(branch, 'name', '') if branch else ''
        branch_phone = getattr(branch, 'phone', '') if branch else ''

        active_loans_count = c.loans.filter(status='active').count() if hasattr(c, 'loans') else 0
        total_borrowed = sum(l.principal_amount for l in c.loans.all()) if hasattr(c, 'loans') else Decimal('0.00')

        is_valid, status_msg, status_code = get_phone_whatsapp_status(raw_phone, norm_phone, known_non_wa)

        audience.append({
            'customer_id': c.id,
            'lead_id': None,
            'name': full_name,
            'raw_phone': raw_phone,
            'norm_phone': norm_phone,
            'is_valid_whatsapp': is_valid,
            'whatsapp_status_msg': status_msg,
            'whatsapp_status_code': status_code,
            'city': getattr(c, 'city', '') or '',
            'group_id': None,
            'group_name': '',
            'branch_name': branch_name,
            'branch_phone': branch_phone,
            'active_loans_count': active_loans_count,
            'total_borrowed': total_borrowed,
            'is_external_lead': False,
            'source': 'customer_directory',
        })

    return audience


# ---------------------------------------------------------------------------
# External Lead & Contact Group Management
# ---------------------------------------------------------------------------

def get_or_create_marketing_group(group_id=None, new_group_name=None, group_description=None, branch_id=None, user=None):
    """
    Resolves or creates a MarketingGroup instance based on input.
    Prioritizes existing group lookup when group_id is provided,
    and prevents duplicate group creation by checking name case-insensitively.
    """
    from transactions.models import MarketingGroup
    from branches.models import Branch

    branch = None
    if branch_id:
        try:
            branch = Branch.objects.get(id=branch_id)
        except Exception:
            branch = None

    if group_id:
        try:
            return MarketingGroup.objects.get(id=group_id)
        except Exception:
            pass

    if new_group_name and str(new_group_name).strip():
        name_clean = str(new_group_name).strip()
        existing_qs = MarketingGroup.objects.filter(name__iexact=name_clean)
        if branch:
            existing_qs = existing_qs.filter(branch=branch)
        existing_group = existing_qs.first()
        if existing_group:
            if group_description and not existing_group.description:
                existing_group.description = group_description.strip()
                existing_group.save()
            return existing_group

        group = MarketingGroup.objects.create(
            name=name_clean,
            description=(group_description or '').strip(),
            branch=branch,
            created_by=user if user and user.is_authenticated else None,
        )
        return group

    return None


def import_leads_from_csv(file_obj, branch_id=None, user=None, save_as_customer=False, group_id=None, new_group_name=None, group_description=None):
    """
    Parses a CSV file containing external prospect leads (name, phone, city)
    and saves them to MarketingLead (appended to new or existing MarketingGroup).
    Returns (imported_count, skipped_count, error_messages, group_instance).
    """
    import csv
    import io
    from transactions.models import MarketingLead
    from branches.models import Branch

    branch = None
    if branch_id:
        try:
            branch = Branch.objects.get(id=branch_id)
        except Exception:
            branch = None

    group = get_or_create_marketing_group(
        group_id=group_id,
        new_group_name=new_group_name,
        group_description=group_description,
        branch_id=branch_id,
        user=user
    )

    decoded = file_obj.read().decode('utf-8-sig', errors='replace')
    reader = csv.reader(io.StringIO(decoded))
    
    rows = list(reader)
    if not rows:
        return 0, 0, ["CSV file is empty."], group

    # Header identification
    first_row = [c.strip().lower() for c in rows[0]]
    has_header = any(h in first_row for h in ('name', 'phone', 'mobile', 'customer', 'customer_name', 'phone_number', 'contact', 'city'))
    
    name_idx, phone_idx, city_idx, notes_idx = 0, 1, 2, 3
    data_rows = rows
    if has_header:
        data_rows = rows[1:]
        for idx, col in enumerate(first_row):
            if col in ('name', 'customer_name', 'full_name', 'customer', 'lead_name', 'பெயர்'):
                name_idx = idx
            elif col in ('phone', 'mobile', 'phone_number', 'mobile_no', 'contact', 'whatsapp', 'தொலைபேசி'):
                phone_idx = idx
            elif col in ('city', 'place', 'location', 'address', 'ஊர்'):
                city_idx = idx
            elif col in ('notes', 'note', 'remarks', 'scheme'):
                notes_idx = idx

    imported_count = 0
    skipped_count = 0
    errors = []

    for line_num, row in enumerate(data_rows, start=2 if has_header else 1):
        if not row or not any(row):
            continue
        
        name = row[name_idx].strip() if len(row) > name_idx else f"Prospect {imported_count+1}"
        phone_raw = row[phone_idx].strip() if len(row) > phone_idx else ''
        city = row[city_idx].strip() if len(row) > city_idx else ''
        notes = row[notes_idx].strip() if len(row) > notes_idx else ''

        if not name:
            name = f"Customer {phone_raw[-4:]}" if len(phone_raw) >= 4 else "Valued Customer"

        norm_phone = normalize_phone_number(phone_raw)
        if not norm_phone:
            skipped_count += 1
            errors.append(f"Row {line_num}: Invalid phone number '{phone_raw}' for '{name}'.")
            continue

        # Create or update MarketingLead scoped to this specific group
        lead, _ = MarketingLead.objects.update_or_create(
            norm_phone=norm_phone,
            group=group,
            defaults={
                'name': name,
                'phone': phone_raw,
                'city': city,
                'branch': branch,
                'notes': notes,
                'source': 'csv_import',
                'created_by': user if user and user.is_authenticated else None,
            }
        )
        imported_count += 1

        # Optionally also register as customer prospect in customer directory
        if save_as_customer:
            try:
                from accounts.models import Customer
                if not Customer.objects.filter(phone=norm_phone).exists():
                    Customer.objects.create(
                        first_name=name.split()[0],
                        last_name=" ".join(name.split()[1:]) if len(name.split()) > 1 else "",
                        phone=norm_phone,
                        city=city,
                        branch=branch,
                    )
            except Exception as e:
                logger.warning("Could not auto-create customer from lead: %s", e)

    return imported_count, skipped_count, errors, group


def add_single_lead(name, phone_raw, city=None, notes=None, branch_id=None, user=None, save_as_customer=False, group_id=None, new_group_name=None, group_description=None):
    """
    Adds a single prospect lead manually to a new or existing group (appended to existing contacts).
    """
    from transactions.models import MarketingLead
    from branches.models import Branch

    norm_phone = normalize_phone_number(phone_raw)
    if not norm_phone:
        raise ValueError(f"Invalid phone number '{phone_raw}'. Must be a valid 10-digit mobile number.")

    branch = None
    if branch_id:
        try:
            branch = Branch.objects.get(id=branch_id)
        except Exception:
            branch = None

    group = get_or_create_marketing_group(
        group_id=group_id,
        new_group_name=new_group_name,
        group_description=group_description,
        branch_id=branch_id,
        user=user
    )

    lead, _ = MarketingLead.objects.update_or_create(
        norm_phone=norm_phone,
        group=group,
        defaults={
            'name': name.strip() or 'Valued Customer',
            'phone': phone_raw.strip(),
            'city': (city or '').strip(),
            'notes': (notes or '').strip(),
            'branch': branch,
            'source': 'manual_entry',
            'created_by': user if user and user.is_authenticated else None,
        }
    )

    if save_as_customer:
        try:
            from accounts.models import Customer
            if not Customer.objects.filter(phone=norm_phone).exists():
                Customer.objects.create(
                    first_name=name.split()[0],
                    last_name=" ".join(name.split()[1:]) if len(name.split()) > 1 else "",
                    phone=norm_phone,
                    city=city,
                    branch=branch,
                )
        except Exception as e:
            logger.warning("Could not create customer: %s", e)

    return lead, group


def delete_marketing_group(group_id, delete_leads=True):
    """
    Deletes a MarketingGroup and optionally its assigned leads.
    """
    from transactions.models import MarketingGroup, MarketingLead

    try:
        group = MarketingGroup.objects.get(id=group_id)
        if delete_leads:
            group.leads.all().delete()
        group_name = group.name
        group.delete()
        return True, group_name
    except Exception as exc:
        logger.warning("Error deleting marketing group %s: %s", group_id, exc)
        return False, str(exc)


def clear_all_marketing_leads(branch_id=None, group_id=None):
    """
    Deletes imported marketing prospect leads.
    """
    from transactions.models import MarketingLead
    qs = MarketingLead.objects.all()
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    if group_id:
        qs = qs.filter(group_id=group_id)
    count, _ = qs.delete()
    return count



# ---------------------------------------------------------------------------
# Message Rendering & Link Generator
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Template Retrieval & Persistence (Database + Built-in Presets)
# ---------------------------------------------------------------------------

def get_all_marketing_templates():
    """
    Returns a unified dict of marketing templates merging built-in presets
    with database-persisted / user-saved / overridden templates.
    """
    from transactions.models import MarketingCampaignTemplate

    templates = {}
    # 1. Load built-in presets as base
    for k, v in MARKETING_TEMPLATES.items():
        templates[k] = {
            'key': k,
            'title_en': v['title_en'],
            'title_ta': v['title_ta'],
            'category': v.get('category', 'General'),
            'badge': v.get('badge', 'Preset'),
            'body_en': v['body_en'],
            'body_ta': v['body_ta'],
            'is_custom': False,
            'is_overridden': False,
        }

    # 2. Merge database saved templates (overriding defaults if key matches, or appending custom)
    try:
        db_templates = MarketingCampaignTemplate.objects.all().order_by('created_at')
        for db_t in db_templates:
            k = db_t.key
            is_built_in = k in MARKETING_TEMPLATES
            templates[k] = {
                'key': k,
                'id': db_t.id,
                'title_en': db_t.title_en or (MARKETING_TEMPLATES[k]['title_en'] if is_built_in else k),
                'title_ta': db_t.title_ta or (MARKETING_TEMPLATES[k]['title_ta'] if is_built_in else k),
                'category': db_t.category or 'Custom',
                'badge': db_t.badge or ('Custom' if db_t.is_custom else 'Updated'),
                'body_en': db_t.body_en or (MARKETING_TEMPLATES[k]['body_en'] if is_built_in else ''),
                'body_ta': db_t.body_ta or (MARKETING_TEMPLATES[k]['body_ta'] if is_built_in else ''),
                'is_custom': db_t.is_custom,
                'is_overridden': is_built_in,
                'updated_at': db_t.updated_at,
            }
    except Exception as exc:
        logger.warning("Could not fetch database marketing templates: %s", exc)

    return templates


def save_or_overwrite_template(key, title_en, title_ta, body_en, body_ta, category='Custom', badge='Saved', is_custom=True, user=None):
    """
    Saves a new custom template or overwrites an existing preset template in the database.
    """
    from transactions.models import MarketingCampaignTemplate

    key = (key or '').strip().lower().replace(' ', '_')
    if not key:
        import time
        key = f"custom_template_{int(time.time())}"

    obj, created = MarketingCampaignTemplate.objects.update_or_create(
        key=key,
        defaults={
            'title_en': title_en,
            'title_ta': title_ta,
            'category': category,
            'badge': badge,
            'body_en': body_en,
            'body_ta': body_ta,
            'is_custom': is_custom,
            'created_by': user if user and user.is_authenticated else None,
        }
    )
    return obj, created


def delete_or_reset_template(key):
    """
    Deletes a custom template or resets an overridden preset template back to its default built-in version.
    """
    from transactions.models import MarketingCampaignTemplate

    deleted_count, _ = MarketingCampaignTemplate.objects.filter(key=key).delete()
    return deleted_count > 0


def is_valid_whatsapp_phone(phone_str):
    """
    Checks if a phone string is a valid mobile number eligible for WhatsApp dispatch.
    Rejects all-zeros, repeated digits, numbers not starting with 6-9 (for 10-digit Indian numbers).
    """
    if not phone_str:
        return False
    digits = re.sub(r'\D', '', str(phone_str))
    if len(digits) < 10 or len(digits) > 15:
        return False
    if len(set(digits)) <= 1:
        return False
    if len(digits) == 10 and digits[0] not in '6789':
        return False
    if len(digits) == 12 and digits.startswith('91') and digits[2] not in '6789':
        return False
    return True


def replace_dynamic_variables(raw_template, customer_dict, gold_rate=None):
    """
    Renders dynamic smart tags in text for the specific recipient.
    Supports placeholders with {tag}, {{tag}}, [tag], and case-insensitive keys:
    - customer_name, name, customer, client_name, recipient_name
    - first_name
    - branch_name, branch
    - branch_phone, contact_phone
    - organization_name, company_name, shop_name
    - gold_rate, gold_price
    - city, location
    - customer_phone, phone
    """
    if not raw_template:
        return ""

    org_name = getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold')
    gr_str = f"{gold_rate:,.0f}" if gold_rate else "6,850"

    full_name = str(customer_dict.get('name') or customer_dict.get('first_name') or 'Valued Customer').strip()
    first_name = full_name.split()[0] if full_name else 'Valued Customer'
    branch_name = str(customer_dict.get('branch_name') or org_name).strip()
    branch_phone = str(customer_dict.get('branch_phone') or getattr(settings, 'COMPANY_PHONE', 'Customer Care')).strip()
    city = str(customer_dict.get('city') or '').strip()
    cust_phone = str(customer_dict.get('raw_phone') or customer_dict.get('phone') or '').strip()

    replacements = {
        'customer_name': full_name,
        'name': full_name,
        'customer': full_name,
        'client_name': full_name,
        'recipient_name': full_name,
        'first_name': first_name,
        'branch_name': branch_name,
        'branch': branch_name,
        'branch_phone': branch_phone,
        'contact_phone': branch_phone,
        'organization_name': org_name,
        'company_name': org_name,
        'shop_name': org_name,
        'gold_rate': gr_str,
        'gold_price': gr_str,
        'city': city,
        'location': city,
        'customer_phone': cust_phone,
        'phone': cust_phone,
    }

    msg = str(raw_template)
    for key, val in replacements.items():
        pattern = re.compile(r'(\{{1,2}\s*' + re.escape(key) + r'\s*\}{1,2}|\[\s*' + re.escape(key) + r'\s*\])', re.IGNORECASE)
        msg = pattern.sub(str(val), msg)

    return msg


def render_campaign_message(template_key, customer_dict, use_tamil=False, custom_body=None, gold_rate=None):
    """
    Renders a campaign message by replacing dynamic smart tags.
    """
    if custom_body:
        raw_template = custom_body
    else:
        all_templates = get_all_marketing_templates()
        tmpl = all_templates.get(template_key, all_templates.get('festival_offer', {}))
        raw_template = tmpl.get('body_ta' if use_tamil else 'body_en', '')

    return replace_dynamic_variables(raw_template, customer_dict, gold_rate=gold_rate)


def get_known_non_whatsapp_phones():
    """
    Retrieves set of phones that were previously logged as invalid or not registered on WhatsApp.
    Queries both MarketingCampaignLog and LoanWhatsAppLog across various failure/skipped reasons.
    """
    from transactions.models import MarketingCampaignLog, LoanWhatsAppLog
    keywords = [
        'not on whatsapp', 'not registered', 'invalid phone', 'invalid number',
        'shared via url is invalid', 'url is invalid', 'phone number is invalid',
        'not a valid whatsapp', 'chat took too long to load', 'composer not found',
        'send button and chat composer not found', 'send button / chat composer not found',
        'number is unavailable', 'failed to open chat', 'not_registered', 'no whatsapp'
    ]
    non_wa = set()
    try:
        logs = MarketingCampaignLog.objects.filter(
            status__in=['skipped', 'failed']
        ).values_list('recipient_phone', 'message_snippet')
        for phone, snippet in logs:
            snip_lower = (snippet or '').lower()
            if phone and any(w in snip_lower for w in keywords):
                phone_str = str(phone).strip()
                non_wa.add(phone_str)
                digits = re.sub(r'\D', '', phone_str)
                if digits:
                    non_wa.add(digits)
                if len(digits) >= 10:
                    clean_10 = digits[-10:]
                    non_wa.add(clean_10)
                    non_wa.add(f"91{clean_10}")
                    non_wa.add(f"+91{clean_10}")
                    non_wa.add(f"0{clean_10}")
    except Exception:
        pass

    try:
        loan_logs = LoanWhatsAppLog.objects.filter(
            status__in=['failed', 'skipped', 'undelivered']
        ).values_list('recipient_phone', 'customer__phone', 'error_message')
        for rec_phone, cust_phone, err in loan_logs:
            text = (err or '').lower()
            if any(w in text for w in keywords):
                for phone in [rec_phone, cust_phone]:
                    if phone:
                        phone_str = str(phone).strip()
                        non_wa.add(phone_str)
                        digits = re.sub(r'\D', '', phone_str)
                        if digits:
                            non_wa.add(digits)
                        if len(digits) >= 10:
                            clean_10 = digits[-10:]
                            non_wa.add(clean_10)
                            non_wa.add(f"91{clean_10}")
                            non_wa.add(f"+91{clean_10}")
                            non_wa.add(f"0{clean_10}")
    except Exception:
        pass

    return non_wa


def clear_non_whatsapp_flag(phone=None, clear_all=False):
    """
    Clears cached/logged non-WhatsApp failure records for a specific phone number or all numbers,
    allowing contacts to be re-verified or re-included in WhatsApp campaigns.
    """
    from transactions.models import MarketingCampaignLog, LoanWhatsAppLog
    keywords = [
        'not on whatsapp', 'not registered', 'invalid phone', 'invalid number',
        'shared via url is invalid', 'url is invalid', 'phone number is invalid',
        'not a valid whatsapp', 'chat took too long to load', 'composer not found',
        'send button and chat composer not found', 'send button / chat composer not found',
        'number is unavailable', 'failed to open chat', 'not_registered', 'no whatsapp'
    ]
    cleared_count = 0
    try:
        if clear_all:
            # Clear all non-wa failure logs
            m_logs = MarketingCampaignLog.objects.filter(status__in=['skipped', 'failed'])
            for m in m_logs:
                snip = (m.message_snippet or '').lower()
                if any(w in snip for w in keywords):
                    m.delete()
                    cleared_count += 1

            l_logs = LoanWhatsAppLog.objects.filter(status__in=['failed', 'skipped', 'undelivered'])
            for l in l_logs:
                err = (l.error_message or '').lower()
                if any(w in err for w in keywords):
                    l.delete()
                    cleared_count += 1

        elif phone:
            phone_str = str(phone).strip()
            digits = re.sub(r'\D', '', phone_str)
            phone_variants = [phone_str]
            if digits:
                phone_variants.append(digits)
            if len(digits) >= 10:
                clean_10 = digits[-10:]
                phone_variants.extend([clean_10, f"91{clean_10}", f"+91{clean_10}", f"0{clean_10}"])

            m_logs = MarketingCampaignLog.objects.filter(
                recipient_phone__in=phone_variants,
                status__in=['skipped', 'failed']
            )
            for m in m_logs:
                snip = (m.message_snippet or '').lower()
                if any(w in snip for w in keywords):
                    m.delete()
                    cleared_count += 1

            l_logs = LoanWhatsAppLog.objects.filter(
                recipient_phone__in=phone_variants,
                status__in=['failed', 'skipped', 'undelivered']
            )
            for l in l_logs:
                err = (l.error_message or '').lower()
                if any(w in err for w in keywords):
                    l.delete()
                    cleared_count += 1

        return {'success': True, 'cleared_count': cleared_count}
    except Exception as e:
        logger.error("Error clearing non-whatsapp flag: %s", e)
        return {'success': False, 'error': str(e), 'cleared_count': 0}



def get_phone_whatsapp_status(raw_phone, norm_phone, non_whatsapp_phones_set=None):
    """
    Evaluates a phone number to check if it can receive WhatsApp messages.
    Returns tuple: (is_valid: bool, status_msg: str, status_code: str)
    """
    raw_str = str(raw_phone or '').strip()
    norm_str = str(norm_phone or '').strip()

    if not raw_str and not norm_str:
        return False, "Missing Phone Number", "missing_phone"

    digits = re.sub(r'\D', '', raw_str or norm_str)
    if not digits:
        return False, "Missing Phone Number", "missing_phone"

    if digits == '0000000000' or len(set(digits)) <= 1:
        return False, "Invalid Number (Dummy/All Zeros)", "dummy_number"

    if len(digits) < 10:
        return False, f"Incomplete Mobile ({digits})", "too_short"

    if len(digits) == 10 and digits[0] not in '6789':
        return False, f"Invalid Mobile (+91-{digits})", "invalid_prefix"

    if len(digits) == 12 and digits.startswith('91') and digits[2] not in '6789':
        return False, f"Invalid Mobile (+{digits})", "invalid_prefix"

    if not norm_str or not is_valid_whatsapp_phone(norm_str):
        return False, "Invalid Format (Not on WhatsApp)", "invalid_format"

    if non_whatsapp_phones_set:
        clean_10 = digits[-10:] if len(digits) >= 10 else digits
        if (norm_str in non_whatsapp_phones_set or 
            clean_10 in non_whatsapp_phones_set or 
            raw_str in non_whatsapp_phones_set or
            digits in non_whatsapp_phones_set or
            f"+91{clean_10}" in non_whatsapp_phones_set or
            f"91{clean_10}" in non_whatsapp_phones_set or
            f"0{clean_10}" in non_whatsapp_phones_set):
            return False, "Not Registered on WhatsApp", "not_registered"

    return True, "WhatsApp Ready", "valid"


def build_broadcast_queue(audience_list, template_key='festival_offer', use_tamil=False, custom_body=None, gold_rate=None):
    """
    Takes an audience list and generates personalized messages + 1-click WhatsApp links for each.
    Includes validation status and warning messages for numbers not on WhatsApp.
    """
    known_non_wa = get_known_non_whatsapp_phones()
    queue = []
    for cust in audience_list:
        raw_phone = cust.get('raw_phone') or cust.get('phone') or ''
        norm_phone = cust.get('norm_phone') or normalize_phone_number(raw_phone)
        
        is_valid, status_msg, status_code = get_phone_whatsapp_status(raw_phone, norm_phone, known_non_wa)
        msg = render_campaign_message(template_key, cust, use_tamil=use_tamil, custom_body=custom_body, gold_rate=gold_rate)
        
        wa_url = ""
        if is_valid and norm_phone:
            digits = get_clean_phone_for_url(norm_phone)
            encoded_text = urllib.parse.quote(msg)
            wa_url = f"https://wa.me/{digits}?text={encoded_text}"

        queue.append({
            'customer_id': cust.get('customer_id'),
            'lead_id': cust.get('lead_id'),
            'name': cust.get('name', 'Valued Customer'),
            'phone': norm_phone or raw_phone or 'No Phone',
            'raw_phone': raw_phone,
            'is_valid_whatsapp': is_valid,
            'whatsapp_status_msg': status_msg,
            'whatsapp_status_code': status_code,
            'city': cust.get('city', ''),
            'branch_name': cust.get('branch_name', ''),
            'branch_phone': cust.get('branch_phone', ''),
            'group_id': cust.get('group_id'),
            'group_name': cust.get('group_name', ''),
            'active_loans_count': cust.get('active_loans_count', 0),
            'is_external_lead': cust.get('is_external_lead', False),
            'source': cust.get('source', ''),
            'message': msg,
            'whatsapp_url': wa_url,
        })
    return queue



# ---------------------------------------------------------------------------
# Background PyWhatKit Bulk Broadcast Runner
# ---------------------------------------------------------------------------

def _copy_image_to_clipboard_windows(image_path):
    """
    Copies an image file to the Windows clipboard in a format that Chrome/WhatsApp Web can paste.
    Uses PowerShell as primary method (most reliable for Chrome), with win32clipboard as fallback.
    Returns True if successful, False otherwise.
    """
    import subprocess
    import os

    if not image_path or not os.path.exists(image_path):
        return False

    # Method 1: PowerShell (most reliable for Chrome / WhatsApp Web)
    try:
        ps_script = (
            f"Add-Type -AssemblyName System.Windows.Forms; "
            f"Add-Type -AssemblyName System.Drawing; "
            f"$img = [System.Drawing.Image]::FromFile('{image_path}'); "
            f"[System.Windows.Forms.Clipboard]::SetImage($img); "
            f"$img.Dispose();"
        )
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', ps_script],
            capture_output=True, timeout=10
        )
        if result.returncode == 0:
            logger.info("Clipboard image set via PowerShell: %s", image_path)
            return True
        else:
            logger.warning("PowerShell clipboard set failed: %s", result.stderr.decode(errors='replace'))
    except Exception as e:
        logger.warning("PowerShell clipboard fallback triggered: %s", e)

    # Method 2: win32clipboard with CF_DIB fallback
    try:
        import win32clipboard
        from PIL import Image
        from io import BytesIO

        img = Image.open(image_path).convert("RGB")
        output = BytesIO()
        img.save(output, "BMP")
        bmp_data = output.getvalue()[14:]   # strip 14-byte BMP file header → raw DIB
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp_data)
        win32clipboard.CloseClipboard()
        logger.info("Clipboard image set via win32clipboard CF_DIB: %s", image_path)
        return True
    except ImportError:
        logger.warning("win32clipboard not available. Install pywin32: pip install pywin32")
    except Exception as e:
        logger.warning("win32clipboard clipboard set failed: %s", e)

    return False


# ---------------------------------------------------------------------------
# Global Real-Time Dispatch Status Tracking for Marketing UI
# ---------------------------------------------------------------------------

_broadcast_lock = threading.Lock()
CURRENT_BROADCAST_STATUS = {
    'is_running': False,
    'is_paused': False,
    'is_stopped': False,
    'status': 'idle',  # 'idle', 'running', 'paused', 'stopped', 'completed', 'error'
    'total': 0,
    'sent': 0,
    'failed': 0,
    'remaining': 0,
    'current_contact': '',
    'current_phone': '',
    'percent': 0,
    'details': [],
    'start_time': None,
    'error': None,
    'remaining_queue': [],
    'campaign_params': {},
}


def get_broadcast_status():
    """Returns a thread-safe snapshot of current marketing broadcast progress."""
    with _broadcast_lock:
        status_copy = dict(CURRENT_BROADCAST_STATUS)
        status_copy['logs'] = list(CURRENT_BROADCAST_STATUS.get('details', []))
        total = status_copy.get('total', 0)
        sent = status_copy.get('sent', 0)
        failed = status_copy.get('failed', 0)
        status_copy['remaining'] = max(0, total - (sent + failed))
        status_copy['remaining_queue'] = list(CURRENT_BROADCAST_STATUS.get('remaining_queue', []))
        return status_copy


def _update_broadcast_status(**kwargs):
    """Updates broadcast status state safely."""
    global CURRENT_BROADCAST_STATUS
    with _broadcast_lock:
        CURRENT_BROADCAST_STATUS.update(kwargs)
        total = CURRENT_BROADCAST_STATUS.get('total', 0)
        sent = CURRENT_BROADCAST_STATUS.get('sent', 0)
        failed = CURRENT_BROADCAST_STATUS.get('failed', 0)
        processed = sent + failed
        CURRENT_BROADCAST_STATUS['remaining'] = max(0, total - processed)
        if total > 0:
            CURRENT_BROADCAST_STATUS['percent'] = min(100, int((processed / total) * 100))
        else:
            CURRENT_BROADCAST_STATUS['percent'] = 0


def pause_automated_broadcast():
    """Pauses the active automated background broadcast."""
    with _broadcast_lock:
        if CURRENT_BROADCAST_STATUS.get('is_running'):
            CURRENT_BROADCAST_STATUS['is_paused'] = True
            CURRENT_BROADCAST_STATUS['status'] = 'paused'
            CURRENT_BROADCAST_STATUS['current_contact'] = 'Campaign Paused by User'
            logger.info("⏸️ Automated WhatsApp marketing broadcast paused.")
            return True
        return False


def resume_automated_broadcast():
    """Resumes the paused automated background broadcast."""
    with _broadcast_lock:
        if CURRENT_BROADCAST_STATUS.get('is_running'):
            CURRENT_BROADCAST_STATUS['is_paused'] = False
            CURRENT_BROADCAST_STATUS['status'] = 'running'
            CURRENT_BROADCAST_STATUS['current_contact'] = 'Resuming campaign...'
            logger.info("▶️ Automated WhatsApp marketing broadcast resumed.")
            return True
        return False


def stop_automated_broadcast():
    """Stops the active automated background broadcast completely."""
    with _broadcast_lock:
        CURRENT_BROADCAST_STATUS['is_stopped'] = True
        CURRENT_BROADCAST_STATUS['is_paused'] = False
        CURRENT_BROADCAST_STATUS['is_running'] = False
        CURRENT_BROADCAST_STATUS['status'] = 'stopped'
        CURRENT_BROADCAST_STATUS['current_contact'] = 'Campaign Stopped by User'
        logger.info("🛑 Automated WhatsApp marketing broadcast stopped by user.")
        return True


def is_broadcast_stopped():
    """Checks if the broadcast has been requested to stop."""
    with _broadcast_lock:
        return bool(CURRENT_BROADCAST_STATUS.get('is_stopped'))


def is_broadcast_paused():
    """Checks if the broadcast is currently paused."""
    with _broadcast_lock:
        return bool(CURRENT_BROADCAST_STATUS.get('is_paused'))


def resume_remaining_broadcast(user=None):
    """
    Resumes an unfinished/stopped broadcast by sending only to remaining unsent contacts.
    """
    with _broadcast_lock:
        if CURRENT_BROADCAST_STATUS.get('is_running'):
            return False, "Campaign is already running."
        remaining_queue = list(CURRENT_BROADCAST_STATUS.get('remaining_queue', []))
        if not remaining_queue:
            return False, "No unfinished contacts remaining in queue."
        params = dict(CURRENT_BROADCAST_STATUS.get('campaign_params', {}))
        total = CURRENT_BROADCAST_STATUS.get('total', len(remaining_queue))
        sent = CURRENT_BROADCAST_STATUS.get('sent', 0)
        failed = CURRENT_BROADCAST_STATUS.get('failed', 0)
        details = list(CURRENT_BROADCAST_STATUS.get('details', []))

    started = launch_pywhatkit_broadcast_async(
        broadcast_queue=remaining_queue,
        delay_seconds=params.get('delay_seconds', 5),
        image_path=params.get('image_path'),
        send_mode=params.get('send_mode', 'message_and_image'),
        user=user,
        is_resume=True,
        initial_sent=sent,
        initial_failed=failed,
        initial_total=total,
        initial_details=details,
    )
    if started:
        return True, f"Resuming campaign for {len(remaining_queue)} remaining contacts."
    return False, "Failed to resume campaign."


def _run_automated_marketing_broadcast(
    broadcast_queue,
    delay_seconds=5,
    image_path=None,
    send_mode='message_and_image',
    user=None,
    is_resume=False,
    initial_sent=0,
    initial_failed=0,
    initial_total=None,
    initial_details=None,
):
    """
    Automated Headless / Background WhatsApp Campaign Dispatcher using Playwright.
    Reuses persistent browser profile in `.whatsapp_user_data/` so QR code is scanned once.
    Sends text and image flyer attachments reliably via DOM element targeting without hijacking the desktop screen.
    """
    import os
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    import re
    import urllib.parse
    import time
    from django.db import close_old_connections
    close_old_connections()
    from playwright.sync_api import sync_playwright
    from transactions.services_whatsapp_automator import (
        get_launch_context_options,
        clean_phone_number,
        is_whatsapp_paired,
        clean_stale_locks,
    )

    total = initial_total if (is_resume and initial_total is not None) else len(broadcast_queue)
    sent_count = initial_sent if is_resume else 0
    failed_count = initial_failed if is_resume else 0
    details = list(initial_details or []) if is_resume else []
    has_valid_image = bool(image_path and os.path.exists(image_path))

    _update_broadcast_status(
        is_running=True,
        is_paused=False,
        is_stopped=False,
        status='running',
        total=total,
        sent=sent_count,
        failed=failed_count,
        remaining=len(broadcast_queue),
        remaining_queue=list(broadcast_queue),
        campaign_params={
            'delay_seconds': delay_seconds,
            'image_path': image_path,
            'send_mode': send_mode,
        },
        current_contact='Resuming campaign...' if is_resume else 'Starting campaign...',
        current_phone='',
        details=[],
        start_time=timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        error=None,
    )

    if not is_whatsapp_paired():
        err_msg = "WhatsApp Web session is not paired. Please pair WhatsApp Web from Digital Marketing/Autopilot page first."
        logger.warning(err_msg)
        _update_broadcast_status(is_running=False, status='error', error=err_msg)
        return

    logger.info(
        "🚀 Starting Automated WhatsApp Marketing Campaign for %d contacts (delay: %ds, mode: %s, image: %s)...",
        total, delay_seconds, send_mode, has_valid_image
    )

    clean_stale_locks()
    context = None
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                **get_launch_context_options(headless=True)
            )
            page = context.pages[0] if context.pages else context.new_page()

            # Pre-warm WhatsApp Web session
            try:
                page.goto("https://web.whatsapp.com/", timeout=45000)
                time.sleep(4)
            except Exception as e:
                logger.warning("WhatsApp Web pre-warm notice: %s", e)

            for offset_idx, item in enumerate(broadcast_queue, start=1):
                display_idx = (sent_count + failed_count + 1) if is_resume else offset_idx

                # ── 1. Check if user stopped the broadcast ──
                curr_status = get_broadcast_status()
                if curr_status.get('is_stopped'):
                    logger.info("🛑 Broadcast stopped by user at contact #%d/%d.", display_idx, total)
                    _update_broadcast_status(
                        is_running=False,
                        status='stopped',
                        current_contact='Campaign Stopped by User',
                        remaining_queue=list(broadcast_queue[offset_idx - 1:]),
                        remaining=len(broadcast_queue[offset_idx - 1:])
                    )
                    break

                # ── 2. Check if user paused the broadcast ──
                while True:
                    curr_status = get_broadcast_status()
                    if curr_status.get('is_stopped'):
                        break
                    if not curr_status.get('is_paused'):
                        break
                    _update_broadcast_status(
                        status='paused',
                        current_contact=f"Paused at contact [{display_idx}/{total}]",
                        remaining_queue=list(broadcast_queue[offset_idx - 1:]),
                        remaining=len(broadcast_queue[offset_idx - 1:])
                    )
                    time.sleep(1)

                if curr_status.get('is_stopped'):
                    logger.info("🛑 Broadcast stopped by user at contact #%d/%d.", display_idx, total)
                    _update_broadcast_status(
                        is_running=False,
                        status='stopped',
                        current_contact='Campaign Stopped by User',
                        remaining_queue=list(broadcast_queue[offset_idx - 1:]),
                        remaining=len(broadcast_queue[offset_idx - 1:])
                    )
                    break

                raw_phone = str(item.get('phone', '')).strip()
                phone_clean = clean_phone_number(raw_phone)
                cust_name = item.get('name', 'Valued Customer')
                # ── Ensure all dynamic variables ({customer_name}, {name}, {branch_name}, etc.) are fully rendered for this specific contact
                msg = replace_dynamic_variables(item.get('message', ''), item)

                _update_broadcast_status(
                    status='running',
                    current_contact=f"[{display_idx}/{total}] {cust_name}",
                    current_phone=phone_clean or raw_phone,
                    remaining_queue=list(broadcast_queue[offset_idx - 1:]),
                    remaining=len(broadcast_queue[offset_idx - 1:])
                )

                # Skip if contact doesn't have a valid mobile/WhatsApp number
                if not phone_clean or not is_valid_whatsapp_phone(phone_clean):
                    failed_count += 1
                    err_txt = f"Invalid Mobile Number: '{raw_phone}' is not a valid 10-digit WhatsApp number"
                    logger.info("[%d/%d] ⏭️ Skipping %s (+%s): invalid mobile number format", display_idx, total, cust_name, raw_phone)
                    details.append({'name': cust_name, 'phone': raw_phone, 'status': 'SKIPPED', 'error': err_txt})
                    _update_broadcast_status(
                        failed=failed_count,
                        details=details,
                        remaining_queue=list(broadcast_queue[offset_idx:]),
                        remaining=len(broadcast_queue[offset_idx:])
                    )

                    log_campaign_broadcast(
                        template_key=item.get('template_key', ''),
                        campaign_name=item.get('campaign_name', 'WhatsApp Campaign Auto-Blast'),
                        recipient_name=cust_name,
                        recipient_phone=raw_phone,
                        recipient_type='lead' if item.get('is_lead') else 'customer',
                        group_id=item.get('group_id'),
                        branch_id=item.get('branch_id'),
                        channel='whatsapp_blast',
                        status='skipped',
                        message_snippet=f"Failed/Skipped: {err_txt} | Msg: {msg[:200]}",
                        user=user
                    )
                    continue

                # Check if this phone number is already marked as not registered on WhatsApp
                if is_phone_marked_non_whatsapp(phone_clean):
                    failed_count += 1
                    err_txt = f"Not Registered on WhatsApp: Phone +{phone_clean} was previously verified as unavailable on WhatsApp"
                    logger.info("[%d/%d] ⏭️ Skipping %s (+%s): known non-WhatsApp number", display_idx, total, cust_name, phone_clean)
                    details.append({'name': cust_name, 'phone': phone_clean, 'status': 'SKIPPED', 'error': err_txt})
                    _update_broadcast_status(
                        failed=failed_count,
                        details=details,
                        remaining_queue=list(broadcast_queue[offset_idx:]),
                        remaining=len(broadcast_queue[offset_idx:])
                    )

                    log_campaign_broadcast(
                        template_key=item.get('template_key', ''),
                        campaign_name=item.get('campaign_name', 'WhatsApp Campaign Auto-Blast'),
                        recipient_name=cust_name,
                        recipient_phone=phone_clean,
                        recipient_type='lead' if item.get('is_lead') else 'customer',
                        group_id=item.get('group_id'),
                        branch_id=item.get('branch_id'),
                        channel='whatsapp_blast',
                        status='skipped',
                        message_snippet=f"Skipped: {err_txt}",
                        user=user
                    )
                    continue

                # ── Construct direct WhatsApp Web API URL ──
                encoded_msg = urllib.parse.quote(msg) if msg else ""
                direct_url = f"https://web.whatsapp.com/send?phone={phone_clean}&text={encoded_msg}"

                try:
                    logger.info("[%d/%d] Navigating to WhatsApp Web chat for %s (+%s)...", display_idx, total, cust_name, phone_clean)
                    page.goto(direct_url, timeout=35000)

                    # Wait for chat composer, invalid phone alert modal, or send button
                    send_btn_sel = 'button[aria-label="Send"], span[data-icon="send"], span[data-icon="wds-ic-send-filled"]'
                    composer_sel = 'div[contenteditable="true"][data-tab="10"], div[contenteditable="true"][role="textbox"], div[aria-placeholder="Type a message"]'
                    invalid_phone_modal_sel = 'div[data-animate-modal-popup="true"], div[role="dialog"]'

                    chat_loaded = False
                    sent_ok = False
                    fail_reason = ""

                    for _ in range(35):
                        if is_broadcast_stopped():
                            break

                        # ── Strict Check: "Phone number shared via url is invalid" popup modal ──
                        try:
                            invalid_modal = page.query_selector(invalid_phone_modal_sel)
                            if invalid_modal and invalid_modal.is_visible():
                                modal_text = (invalid_modal.inner_text() or "").lower()
                                if "phone number shared via url is invalid" in modal_text or "url is invalid" in modal_text:
                                    logger.warning("[%d/%d] ⚠️ WhatsApp confirmed phone +%s is NOT registered on WhatsApp: %s", display_idx, total, phone_clean, modal_text)
                                    mark_phone_as_non_whatsapp(phone_clean, reason="Phone number shared via url is invalid")
                                    fail_reason = f"Not Registered on WhatsApp: Phone +{phone_clean} is not on WhatsApp."
                                    try:
                                        ok_btn = invalid_modal.query_selector('button')
                                        if ok_btn:
                                            ok_btn.click()
                                    except Exception:
                                        pass
                                    break
                        except Exception:
                            pass

                        # Check if chat composer or send button is loaded
                        try:
                            composer = page.query_selector(composer_sel)
                            send_btn = page.query_selector(send_btn_sel)
                            if (composer and composer.is_visible()) or (send_btn and send_btn.is_visible()):
                                chat_loaded = True
                                break
                        except Exception:
                            pass

                        time.sleep(0.5)

                    if not chat_loaded and not fail_reason:
                        try:
                            invalid_modal = page.query_selector(invalid_phone_modal_sel)
                            if invalid_modal and invalid_modal.is_visible():
                                modal_text = (invalid_modal.inner_text() or "").lower()
                                if "phone number shared via url is invalid" in modal_text or "url is invalid" in modal_text:
                                    mark_phone_as_non_whatsapp(phone_clean, reason="Phone number shared via url is invalid")
                                    fail_reason = f"Not Registered on WhatsApp: Phone +{phone_clean} is not on WhatsApp."
                                else:
                                    fail_reason = f"WhatsApp Alert / Dialog: {invalid_modal.inner_text()[:100]}"
                            else:
                                fail_reason = "Send button and chat composer not found (Chat took too long to load)."
                        except Exception:
                            fail_reason = "Send button and chat composer not found (Chat took too long to load)."

                    if chat_loaded:
                        time.sleep(1.0)

                        # Mode: message_only OR (message_and_image without flyer file)
                        if send_mode == 'message_only' or not has_valid_image:
                            for _ in range(12):
                                send_btn = page.query_selector(send_btn_sel)
                                if send_btn and send_btn.is_visible():
                                    try:
                                        send_btn.click()
                                        sent_ok = True
                                        time.sleep(1.8)
                                        break
                                    except Exception:
                                        pass
                                time.sleep(0.5)

                            if not sent_ok:
                                try:
                                    page.keyboard.press("Enter")
                                    sent_ok = True
                                    time.sleep(1.8)
                                except Exception as press_e:
                                    fail_reason = f"Could not trigger Enter key: {press_e}"

                        # Mode: message_and_image OR image_only with attached flyer
                        elif has_valid_image:
                            try:
                                attach_btn_sel = 'span[data-icon="plus"], span[data-icon="attach-menu-plus"], button[title="Attach"], button[aria-label="Attach"]'
                                attach_btn = page.query_selector(attach_btn_sel)
                                if attach_btn and attach_btn.is_visible():
                                    attach_btn.click()
                                    time.sleep(0.8)

                                file_input = page.query_selector('input[type="file"]')
                                if file_input:
                                    file_input.set_input_files(image_path)
                                    time.sleep(2.0)

                                    if send_mode == 'message_and_image' and msg:
                                        caption_input_sel = 'div[contenteditable="true"][data-tab="10"], div[contenteditable="true"][role="textbox"], div[aria-placeholder="Add a caption"]'
                                        caption_el = page.query_selector(caption_input_sel)
                                        if caption_el and caption_el.is_visible():
                                            try:
                                                caption_el.fill(msg)
                                            except Exception:
                                                pass

                                    media_send_sel = 'span[data-icon="send"], span[data-icon="wds-ic-send-filled"], button[aria-label="Send"]'
                                    for _ in range(10):
                                        media_send_btn = page.query_selector(media_send_sel)
                                        if media_send_btn and media_send_btn.is_visible():
                                            media_send_btn.click()
                                            sent_ok = True
                                            time.sleep(2.5)
                                            break
                                        time.sleep(0.5)

                                    if not sent_ok:
                                        page.keyboard.press("Enter")
                                        sent_ok = True
                                        time.sleep(2.5)
                                else:
                                    fail_reason = "File attachment input not found in WhatsApp Web DOM"
                            except Exception as attach_err:
                                logger.warning("Could not attach flyer image via DOM: %s", attach_err)
                                fail_reason = f"Image attachment error: {attach_err}"

                    if not sent_ok and not fail_reason:
                        fail_reason = "Send button / chat composer not found (Chat took too long to load or number is unavailable)."

                    if sent_ok:
                        sent_count += 1
                        details.append({'name': cust_name, 'phone': phone_clean, 'status': 'SENT', 'error': ''})
                        _update_broadcast_status(
                            sent=sent_count,
                            details=details,
                            remaining_queue=list(broadcast_queue[offset_idx:]),
                            remaining=len(broadcast_queue[offset_idx:])
                        )

                        log_campaign_broadcast(
                            template_key=item.get('template_key', ''),
                            campaign_name=item.get('campaign_name', 'WhatsApp Campaign Auto-Blast'),
                            recipient_name=cust_name,
                            recipient_phone=phone_clean,
                            recipient_type='lead' if item.get('is_lead') else 'customer',
                            group_id=item.get('group_id'),
                            branch_id=item.get('branch_id'),
                            channel='whatsapp_blast',
                            status='sent',
                            message_snippet=msg[:400],
                            user=user
                        )
                    else:
                        failed_count += 1
                        details = list(get_broadcast_status().get('details', []))
                        err_txt = fail_reason or "Timeout: Send button did not respond in WhatsApp Web"
                        details.append({'name': cust_name, 'phone': phone_clean, 'status': 'FAILED', 'error': err_txt})
                        _update_broadcast_status(
                            failed=failed_count,
                            details=details,
                            remaining_queue=list(broadcast_queue[offset_idx:]),
                            remaining=len(broadcast_queue[offset_idx:])
                        )

                        log_campaign_broadcast(
                            template_key=item.get('template_key', ''),
                            campaign_name=item.get('campaign_name', 'WhatsApp Campaign Auto-Blast'),
                            recipient_name=cust_name,
                            recipient_phone=phone_clean,
                            recipient_type='lead' if item.get('is_lead') else 'customer',
                            group_id=item.get('group_id'),
                            branch_id=item.get('branch_id'),
                            channel='whatsapp_blast',
                            status='failed',
                            message_snippet=f"Failed: {err_txt} | Msg: {msg[:200]}",
                            user=user
                        )

                except Exception as send_err:
                    logger.warning("[%d/%d] Error sending to %s (+%s): %s", display_idx, total, cust_name, phone_clean, send_err)
                    failed_count += 1
                    details = list(get_broadcast_status().get('details', []))
                    err_txt = f"Page / Network Error: {type(send_err).__name__} ({str(send_err)})"
                    details.append({'name': cust_name, 'phone': phone_clean, 'status': 'FAILED', 'error': err_txt})
                    _update_broadcast_status(
                        failed=failed_count,
                        details=details,
                        remaining_queue=list(broadcast_queue[offset_idx:]),
                        remaining=len(broadcast_queue[offset_idx:])
                    )

                    log_campaign_broadcast(
                        template_key=item.get('template_key', ''),
                        campaign_name=item.get('campaign_name', 'WhatsApp Campaign Auto-Blast'),
                        recipient_name=cust_name,
                        recipient_phone=phone_clean,
                        recipient_type='lead' if item.get('is_lead') else 'customer',
                        group_id=item.get('group_id'),
                        branch_id=item.get('branch_id'),
                        channel='whatsapp_blast',
                        status='failed',
                        message_snippet=f"Failed: {err_txt} | Msg: {msg[:200]}",
                        user=user
                    )

                if offset_idx < len(broadcast_queue):
                    safe_delay = max(3, int(delay_seconds))
                    for _ in range(safe_delay):
                        curr = get_broadcast_status()
                        if curr.get('is_stopped'):
                            break
                        time.sleep(1)

    except Exception as fatal_err:
        logger.error("Fatal error during automated marketing campaign: %s", fatal_err)
        _update_broadcast_status(is_running=False, status='error', error=str(fatal_err))
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        clean_stale_locks()
        curr_final = get_broadcast_status()
        if curr_final.get('is_stopped') or curr_final.get('status') == 'stopped':
            _update_broadcast_status(is_running=False, status='stopped', current_contact='Campaign Stopped by User')
        elif curr_final.get('status') == 'error':
            _update_broadcast_status(is_running=False)
        else:
            _update_broadcast_status(
                is_running=False,
                status='completed',
                current_contact='Campaign Completed',
                remaining_queue=[],
                remaining=0
            )
        logger.info("WhatsApp marketing campaign finished.")


def launch_pywhatkit_broadcast_async(
    broadcast_queue,
    delay_seconds=5,
    image_path=None,
    send_mode='message_and_image',
    user=None,
    is_resume=False,
    initial_sent=0,
    initial_failed=0,
    initial_total=None,
    initial_details=None,
):
    """
    Launches the automated Playwright background broadcast runner thread.
    (Named launch_pywhatkit_broadcast_async for backwards compatibility).
    """
    if not broadcast_queue:
        return False

    t = threading.Thread(
        target=_run_automated_marketing_broadcast,
        args=(
            broadcast_queue,
            delay_seconds,
            image_path,
            send_mode,
            user,
            is_resume,
            initial_sent,
            initial_failed,
            initial_total,
            initial_details,
        ),
        daemon=True,
        name="automated-marketing-broadcast-worker"
    )
    t.start()
    return True


# Alias for explicit naming
launch_automated_marketing_broadcast_async = launch_pywhatkit_broadcast_async


# ---------------------------------------------------------------------------
# Campaign Logging & Analytics Services
# ---------------------------------------------------------------------------

def log_campaign_broadcast(
    template_key='',
    campaign_name='Broadcast',
    recipient_name='',
    recipient_phone='',
    recipient_type='customer',
    group_id=None,
    branch_id=None,
    channel='whatsapp_web',
    status='sent',
    message_snippet='',
    user=None
):
    """
    Records an outgoing campaign message into MarketingCampaignLog and marks
    prospect MarketingLead as contacted if applicable.
    """
    import os
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    from django.db import close_old_connections
    close_old_connections()
    from transactions.models import MarketingCampaignLog, MarketingLead, MarketingGroup
    from branches.models import Branch

    try:
        group_obj = None
        if group_id:
            try:
                group_obj = MarketingGroup.objects.get(id=group_id)
            except Exception:
                group_obj = None

        branch_obj = None
        if branch_id:
            try:
                branch_obj = Branch.objects.get(id=branch_id)
            except Exception:
                branch_obj = None

        log_entry = MarketingCampaignLog.objects.create(
            template_key=template_key or '',
            campaign_name=campaign_name or 'Broadcast Campaign',
            recipient_name=recipient_name or 'Valued Customer',
            recipient_phone=recipient_phone or '',
            recipient_type=recipient_type,
            group=group_obj,
            branch=branch_obj,
            channel=channel,
            status=status,
            message_snippet=message_snippet or '',
            sent_by=user if user and user.is_authenticated else None
        )

        # If this was sent to a MarketingLead, mark is_contacted = True
        if recipient_phone:
            norm = normalize_phone_number(recipient_phone)
            MarketingLead.objects.filter(norm_phone=norm).update(is_contacted=True)

            # Cross-log into LoanWhatsAppLog for any matching customer loans
            try:
                from transactions.models import Loan, LoanWhatsAppLog
                phone_variants = [p for p in [recipient_phone, norm, norm[-10:] if len(norm) >= 10 else ''] if p]
                matching_loans = Loan.objects.filter(
                    customer__phone__in=phone_variants
                ).select_related('customer')
                for l in matching_loans:
                    LoanWhatsAppLog.objects.create(
                        loan=l,
                        customer=l.customer,
                        recipient_phone=recipient_phone,
                        notification_type='marketing_broadcast',
                        status=status.lower() if status else 'sent',
                        message_content=f"[{campaign_name}] {message_snippet or ''}",
                        channel=channel or 'whatsapp_blast',
                        sent_by=user if user and user.is_authenticated else None,
                    )
            except Exception:
                pass

        return log_entry
    except Exception as db_err:
        logger.warning("Error logging campaign broadcast to database: %s", db_err)
        return None


def get_campaign_analytics(branch_id=None, limit=100):
    """
    Calculates aggregated analytics and fetches recent execution history for the marketing hub.
    """
    from django.db.models import Count, Q
    from django.utils import timezone
    from transactions.models import MarketingCampaignLog

    qs = MarketingCampaignLog.objects.all()
    if branch_id:
        qs = qs.filter(branch_id=branch_id)

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_sent = qs.filter(status='sent').count()
    total_today = qs.filter(status='sent', created_at__gte=today_start).count()
    total_this_month = qs.filter(status='sent', created_at__gte=month_start).count()
    total_failed = qs.filter(status='failed').count()

    whatsapp_count = qs.filter(channel__in=['whatsapp_web', 'pywhatkit', 'api']).count()
    sms_count = qs.filter(channel='sms').count()

    recent_logs = qs.select_related('group', 'branch', 'sent_by').order_by('-created_at')[:limit]

    return {
        'total_sent': total_sent,
        'total_today': total_today,
        'total_this_month': total_this_month,
        'total_failed': total_failed,
        'whatsapp_count': whatsapp_count,
        'sms_count': sms_count,
        'recent_logs': recent_logs,
    }


# ---------------------------------------------------------------------------
# Social Media Copy Generator
# ---------------------------------------------------------------------------

def get_social_media_ad_copies(organization_name=None, phone=None, gold_rate=None):
    """
    Generates ready-to-copy social media ad captions for Instagram, Facebook, and WhatsApp Status.
    """
    org = organization_name or getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold')
    ph = phone or 'Customer Care'
    rate = f"{gold_rate:,.0f}" if gold_rate else "6,850"

    return {
        'instagram_en': (
            f"✨ Instant Gold Loans with Lowest Interest Rates at {org}! ✨\n\n"
            f"💰 Max Valuation: ₹{rate}/g\n"
            f"⏱️ 5-Minute Cash Disbursement\n"
            f"🔒 100% Vault Safe Storage\n"
            f"📉 Interest rates starting from just 0.99%/mo\n\n"
            f"Visit our nearest branch or call {ph} today! 🚀\n\n"
            f"#GoldLoan #InstantCash #LowInterest #Pawnshop #{org.replace(' ', '')} #FinancialFreedom"
        ),
        'instagram_ta': (
            f"✨ உங்கள் பழைய நகைகளுக்கு உடனடி ரொக்கக் கடன் - {org}! ✨\n\n"
            f"💰 கிராமுக்கு அதிக கடன் மதிப்பு\n"
            f"⏱️ 5 நிமிடங்களில் கடன் பட்டுவாடா\n"
            f"🔒 100% பாதுகாப்பான வங்கி பெட்டகம்\n"
            f"📉 எளிய மற்றும் குறைந்த வட்டி திட்டங்கள்\n\n"
            f"இன்றே கிளையை அணுகவும் அல்லது அழைக்கவும்: {ph} 🚀\n\n"
            f"#தங்கக்கடன் #தங்கநகைக்கடன் #{org.replace(' ', '')} #உடனடிரொக்கம் #சேமிப்பு"
        ),
        'whatsapp_status_en': (
            f"🪙 Need Quick Cash? Get Instant Gold Loan at {org}!\n"
            f"⚡ 5 Min Approval | Highest Per Gram Rate | Low 0.99% Interest\n"
            f"📞 Call: {ph}"
        ),
        'whatsapp_status_ta': (
            f"🪙 அவசர பணத் தேவையா? {org} -இல் உடனடி தங்கக் கடன்!\n"
            f"⚡ 5 நிமிடங்களில் பணம் | அதிக கிராம் மதிப்பு | குறைந்த வட்டி\n"
            f"📞 தொடர்பு: {ph}"
        )
    }
