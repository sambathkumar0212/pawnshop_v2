"""
transactions/services_marketing.py
Marketing and WhatsApp Broadcast Campaign services for Pawnshop Management.
Provides customer segmentation, bilingual marketing templates, dynamic variable
injection, and background PyWhatKit automated blast queues.
"""

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
# Audience Segmentation Engine
# ---------------------------------------------------------------------------

def get_segmented_audience(segment_type='all', branch_id=None, organization=None):
    """
    Returns a list of customer/prospect dictionaries matching the segment criteria:
    - 'all': All registered customers with phone numbers
    - 'active_borrowers': Customers who have at least one active loan
    - 'closed_loans': Customers who had loans that are now closed/foreclosed (re-engagement prospects)
    - 'overdue': Customers who have overdue active loans
    - 'high_value': Customers with total principal > ₹1,00,000
    - 'new_prospects': External new leads imported via CSV or added manually
    """
    if segment_type in ('new_prospects', 'imported_leads', 'leads'):
        from transactions.models import MarketingLead
        lead_qs = MarketingLead.objects.all()
        if branch_id:
            lead_qs = lead_qs.filter(branch_id=branch_id)
        
        audience = []
        for lead in lead_qs:
            raw_phone = lead.phone or ''
            norm_phone = lead.norm_phone or normalize_phone_number(raw_phone)
            branch = lead.branch
            branch_name = getattr(branch, 'name', '') if branch else ''
            branch_phone = getattr(branch, 'phone', '') if branch else ''

            audience.append({
                'customer_id': f"LEAD-{lead.id}",
                'lead_id': lead.id,
                'name': lead.name or 'Valued Customer',
                'raw_phone': raw_phone,
                'norm_phone': norm_phone,
                'is_valid_whatsapp': bool(norm_phone),
                'city': lead.city or '',
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

        audience.append({
            'customer_id': c.id,
            'lead_id': None,
            'name': full_name,
            'raw_phone': raw_phone,
            'norm_phone': norm_phone,
            'is_valid_whatsapp': bool(norm_phone),
            'city': getattr(c, 'city', '') or '',
            'branch_name': branch_name,
            'branch_phone': branch_phone,
            'active_loans_count': active_loans_count,
            'total_borrowed': total_borrowed,
            'is_external_lead': False,
            'source': 'customer_directory',
        })

    return audience


# ---------------------------------------------------------------------------
# External Lead Import & Management
# ---------------------------------------------------------------------------

def import_leads_from_csv(file_obj, branch_id=None, user=None, save_as_customer=False):
    """
    Parses a CSV file containing external prospect leads (name, phone, city)
    and saves them to MarketingLead (and optionally Customer model).
    Returns (imported_count, skipped_count, error_messages).
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

    decoded = file_obj.read().decode('utf-8-sig', errors='replace')
    reader = csv.reader(io.StringIO(decoded))
    
    rows = list(reader)
    if not rows:
        return 0, 0, ["CSV file is empty."]

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

        # Create or update MarketingLead
        MarketingLead.objects.update_or_create(
            norm_phone=norm_phone,
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

    return imported_count, skipped_count, errors


def add_single_lead(name, phone_raw, city=None, notes=None, branch_id=None, user=None, save_as_customer=False):
    """
    Adds a single prospect lead manually.
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

    lead, _ = MarketingLead.objects.update_or_create(
        norm_phone=norm_phone,
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

    return lead


def clear_all_marketing_leads(branch_id=None):
    """
    Deletes all imported marketing prospect leads.
    """
    from transactions.models import MarketingLead
    qs = MarketingLead.objects.all()
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
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

    org_name = getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold')
    gr_str = f"{gold_rate:,.0f}" if gold_rate else "6,850"

    replacements = {
        '{customer_name}': customer_dict.get('name', 'Valued Customer'),
        '{branch_name}': customer_dict.get('branch_name', '') or org_name,
        '{branch_phone}': customer_dict.get('branch_phone', '') or getattr(settings, 'COMPANY_PHONE', 'Customer Care'),
        '{organization_name}': org_name,
        '{gold_rate}': gr_str,
        '{city}': customer_dict.get('city', ''),
    }

    msg = raw_template
    for placeholder, val in replacements.items():
        msg = msg.replace(placeholder, str(val))

    return msg


def build_broadcast_queue(audience_list, template_key='festival_offer', use_tamil=False, custom_body=None, gold_rate=None):
    """
    Takes an audience list and generates personalized messages + 1-click WhatsApp links for each.
    """
    queue = []
    for cust in audience_list:
        if not cust.get('is_valid_whatsapp'):
            continue
        msg = render_campaign_message(template_key, cust, use_tamil=use_tamil, custom_body=custom_body, gold_rate=gold_rate)
        digits = get_clean_phone_for_url(cust['norm_phone'])
        encoded_text = urllib.parse.quote(msg)
        wa_url = f"https://wa.me/{digits}?text={encoded_text}"

        queue.append({
            'customer_id': cust['customer_id'],
            'name': cust['name'],
            'phone': cust['norm_phone'],
            'city': cust['city'],
            'branch_name': cust['branch_name'],
            'active_loans_count': cust['active_loans_count'],
            'message': msg,
            'whatsapp_url': wa_url,
        })
    return queue



# ---------------------------------------------------------------------------
# Background PyWhatKit Bulk Broadcast Runner
# ---------------------------------------------------------------------------

def _run_pywhatkit_bulk_broadcast(broadcast_queue, delay_seconds=20, image_path=None, send_mode='message_and_image'):
    """
    Sequentially sends WhatsApp messages or images with safe delay interval.
    Runs in a background daemon thread. Supports:
    - 'message_and_image': Sends promotional flyer image with personalized message as caption
    - 'image_only': Sends image flyer alone
    - 'message_only': Standard text message
    """
    try:
        import os
        import pywhatkit
        total = len(broadcast_queue)
        has_valid_image = bool(image_path and os.path.exists(image_path))
        logger.info(
            "Starting PyWhatKit bulk broadcast for %d contacts (delay: %ds, mode: %s, image: %s)...",
            total, delay_seconds, send_mode, has_valid_image
        )

        for idx, item in enumerate(broadcast_queue, start=1):
            phone = item['phone']
            msg = item['message']
            try:
                logger.info("[%d/%d] Dispatching WhatsApp campaign to %s (mode: %s)...", idx, total, phone, send_mode)
                
                if has_valid_image and send_mode == 'image_only':
                    # Send image alone without text caption
                    pywhatkit.sendwhats_image(
                        receiver=phone,
                        img_path=image_path,
                        caption="",
                        wait_time=15,
                        tab_close=True,
                        close_time=3
                    )
                elif has_valid_image and send_mode in ('message_and_image', 'image_with_caption'):
                    # Send image with personalized message as caption
                    pywhatkit.sendwhats_image(
                        receiver=phone,
                        img_path=image_path,
                        caption=msg,
                        wait_time=15,
                        tab_close=True,
                        close_time=3
                    )
                else:
                    # Message only
                    pywhatkit.sendwhatmsg_instantly(
                        phone_no=phone,
                        message=msg,
                        wait_time=15,
                        tab_close=True,
                        close_time=3
                    )
                logger.info("[%d/%d] Successfully dispatched to %s.", idx, total, phone)
            except Exception as exc:
                logger.warning("[%d/%d] Failed to send to %s: %s", idx, total, phone, exc)

            if idx < total:
                time.sleep(delay_seconds)

        logger.info("PyWhatKit bulk broadcast completed successfully for %d contacts.", total)
    except Exception as exc:
        logger.error("PyWhatKit bulk broadcast runner error: %s", exc)


def launch_pywhatkit_broadcast_async(broadcast_queue, delay_seconds=20, image_path=None, send_mode='message_and_image'):
    """
    Launches the background broadcast runner thread with image attachment support.
    """
    if not broadcast_queue:
        return False

    t = threading.Thread(
        target=_run_pywhatkit_bulk_broadcast,
        args=(broadcast_queue, delay_seconds, image_path, send_mode),
        daemon=True,
        name="pywhatkit-bulk-broadcast-worker"
    )
    t.start()
    return True



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
