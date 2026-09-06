"""
transactions/services_gemini.py
Google Gemini AI integration (Free Tier) for generating marketing offers,
campaign templates, WhatsApp broadcast messages, SMS, and social media ad copies.
"""

import json
import logging
import re
from decimal import Decimal
from typing import Dict, Any, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Google Gemini API endpoint and free tier models
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODELS = [
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
]


def get_configured_gemini_api_key(custom_key: Optional[str] = None) -> str:
    """
    Retrieve Gemini API key from custom parameter, settings, or environment.
    """
    if custom_key and str(custom_key).strip():
        return str(custom_key).strip()
    return getattr(settings, 'GEMINI_API_KEY', '') or ''


def build_gemini_prompt(params: Dict[str, Any]) -> str:
    """
    Construct a high-converting system and task prompt for gold loan marketing.
    """
    offer_type = params.get('offer_type', 'festival_offer')
    festival_name = params.get('festival_name', '').strip()
    language = params.get('language', 'ta')  # 'ta', 'en', 'tanglish', 'bilingual'
    tone = params.get('tone', 'festive')  # 'festive', 'professional', 'urgent', 'friendly'
    interest_rate = params.get('interest_rate', '0.99%')
    gold_rate = params.get('gold_rate', '₹6,850/g')
    bonus_offer = params.get('bonus_offer', '').strip()
    custom_instructions = params.get('custom_instructions', '').strip()
    organization_name = params.get('organization_name', 'First Money Gold')

    lang_desc = {
        'ta': 'pure Tamil (தமிழ்) with rich cultural warmth and clear financial terms',
        'en': 'clear professional English with punchy headlines and bullet points',
        'tanglish': 'Tanglish (Tamil spoken in English script/alphabet, e.g. "Ungalukku thanga kadan thevaiya")',
        'bilingual': 'Bilingual (First section in Tamil, followed by English summary)',
    }.get(language, 'Tamil and English')

    tone_desc = {
        'festive': 'Celebratory, joyful, auspicious, and welcoming',
        'professional': 'Trustworthy, transparent, official, and prestigious',
        'urgent': 'High urgency, limited time discount, FOMO, fast cash',
        'friendly': 'Caring, conversational, relationship-focused, and accessible',
    }.get(tone, 'Enthusiastic and persuasive')

    prompt = f"""
You are an expert digital marketing copywriter and gold loan / pawnshop financial consultant specializing in WhatsApp marketing, SMS, and social media campaigns for '{organization_name}'.

Generate a high-converting gold loan marketing campaign based on the following specifications:

--- SPECIFICATIONS ---
1. Campaign Type: {offer_type}
2. Festival / Occasion: {festival_name if festival_name else 'General / Seasonal'}
3. Language: {lang_desc}
4. Tone & Style: {tone_desc}
5. Key Interest Rate: {interest_rate} per month
6. Gold Rate / Max Valuation: {gold_rate} per gram
7. Special Perk / Bonus: {bonus_offer if bonus_offer else 'Zero processing charges & 5-minute instant spot cash'}
8. Extra Custom Details: {custom_instructions if custom_instructions else 'Highlight insured safe vault storage and transparent weighing'}
9. Required Placeholders to include in the WhatsApp body (DO NOT replace them, keep them EXACTLY as shown):
   - {{customer_name}}
   - {{branch_name}}
   - {{branch_phone}}
   - {{organization_name}}
   - {{gold_rate}}

--- OUTPUT REQUIREMENTS ---
Return ONLY a valid JSON object (no extra commentary, markdown headers, or explanations) matching this EXACT JSON schema:

{{
  "campaign_title": "Short catchy campaign title with emojis (max 60 chars)",
  "whatsapp_message": "Complete WhatsApp marketing message with bold *headings*, bullet points, emojis (🌟, 🪙, 💰, 📍, 📞), clear CTA, and all required placeholders verbatim.",
  "sms_message": "Punchy SMS version under 160 characters mentioning {organization_name}, {interest_rate}, and call-to-action.",
  "social_caption": "Engaging Instagram/Facebook caption with bullet points, CTA, and 8 relevant trending hashtags (like #GoldLoan #TamilNadu #GoldJewellery #DiwaliOffers etc.)",
  "key_highlights": [
    "Highlight 1 (e.g. 0.99% Lowest Monthly Interest)",
    "Highlight 2 (e.g. Instant Cash in 5 Minutes)",
    "Highlight 3 (e.g. 100% Insured Bank-grade Safe Vault)"
  ]
}}
"""
    return prompt.strip()


def call_gemini_api(api_key: str, prompt: str, model_name: str = 'gemini-1.5-flash') -> Dict[str, Any]:
    """
    Call Google Gemini Free Tier REST endpoint.
    """
    url = f"{GEMINI_API_BASE_URL}/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95,
            "maxOutputTokens": 1500,
        }
    }

    response = requests.post(url, headers=headers, json=payload, timeout=25)
    if response.status_code != 200:
        error_msg = f"Gemini API returned HTTP {response.status_code}: {response.text}"
        logger.error(error_msg)
        raise Exception(error_msg)

    data = response.json()
    candidates = data.get('candidates', [])
    if not candidates:
        raise Exception("Gemini API returned no candidates.")

    first_part = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
    if not first_part:
        raise Exception("Empty response text from Gemini API.")

    return parse_gemini_json_response(first_part)


def parse_gemini_json_response(raw_text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from Gemini's response (handles code fences, trailing commas, etc.).
    """
    cleaned = raw_text.strip()
    # Strip markdown code fences if present
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\n?', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\n?```$', '', cleaned)
        cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Match outermost json { ... }
        match = re.search(r'(\{[\s\S]*\})', cleaned)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

    # If parsing fails, create structured fallback wrapper
    return {
        "campaign_title": "✨ Special Gold Loan Offer",
        "whatsapp_message": cleaned,
        "sms_message": f"Special Gold Loan Offer at {getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold')}. Visit our nearest branch for instant cash!",
        "social_caption": cleaned[:300] + "\n\n#GoldLoan #FirstMoneyGold",
        "key_highlights": [
            "Special Low Interest Rate",
            "Instant Cash in 5 Minutes",
            "Safe Gold Custody"
        ]
    }


def generate_fallback_campaign(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Smart algorithmic fallback campaign generator when Gemini API key is not configured.
    Ensures 100% uninterrupted experience.
    """
    lang = params.get('language', 'ta')
    festival = params.get('festival_name', 'பண்டிகை').strip() or 'சிறப்பு'
    interest = params.get('interest_rate', '0.99%')
    gold_val = params.get('gold_rate', '₹6,850/g')
    org = params.get('organization_name', 'First Money Gold')
    perk = params.get('bonus_offer', 'ஆவண கட்டணம் முற்றிலும் இலவசம்')

    if lang == 'en':
        title = f"🎉 {festival.title()} Special Gold Loan Offer ({interest})"
        wa_msg = (
            f"✨ *{festival.upper()} MEGA GOLD LOAN UTSAV - {{organization_name}}* ✨\n\n"
            f"Dear *{{customer_name}}*,\n"
            f"Celebrate this auspicious occasion with our exclusive low-interest gold loan scheme!\n\n"
            f"🌟 *Exclusive Offer Highlights:*\n"
            f"• *Lowest Monthly Interest:* Starting from just *{interest}*\n"
            f"• *Highest Gold Valuation:* Up to *{gold_val}* per gram\n"
            f"• *Special Perk:* {perk}\n"
            f"• *Instant Cash:* Approval & spot cash in just 5 minutes\n"
            f"• *Safe & Insured:* 100% bank-grade high security vault\n\n"
            f"📍 *Nearest Branch:* {{branch_name}}\n"
            f"📞 *Call / WhatsApp:* {{branch_phone}}\n\n"
            f"Hurry! Limited period festive scheme. Visit us today!"
        )
        sms = f"{festival} Gold Loan Mela at {org}! Lowest interest {interest}/pm, highest cash/g. Instant cash in 5 mins! Call {{branch_phone}}."
        social = (
            f"✨ Celebrate {festival} with {org} Gold Loans!\n\n"
            f"💰 Lowest Interest from {interest}/month\n"
            f"🪙 Highest Cash per gram ({gold_val})\n"
            f"⚡ Instant cash in 5 minutes with zero hassle!\n\n"
            f"Visit our branch {{branch_name}} or call {{branch_phone}} today!\n\n"
            f"#GoldLoan #InstantCash #JewelleryLoan #FestiveOffers #{festival.replace(' ', '')} #{org.replace(' ', '')}"
        )
    else:
        title = f"🎉 {festival} சிறப்பு தங்கக் கடன் பெருவிழா ({interest})"
        wa_msg = (
            f"✨ *{festival} சிறப்பு தங்கக் கடன் பெருவிழா - {{organization_name}}* ✨\n\n"
            f"அன்புள்ள *{{customer_name}}*,\n"
            f"இந்த நன்னாளில் உங்கள் பணத்தேவைகளை எளிதில் பூர்த்தி செய்ய எங்கள் பிரத்யேக குறைந்த வட்டி தங்கக் கடன் திட்டம்!\n\n"
            f"🌟 *சிறப்பு சலுகைகள்:*\n"
            f"• *குறைந்த வட்டி:* மாதம் *{interest}* மட்டுமே!\n"
            f"• *அதிகபட்ச கடன் மதிப்பு:* கிராமுக்கு அதிக கடன் தொகை ({gold_val})\n"
            f"• *சிறப்பு போனஸ்:* {perk}\n"
            f"• *உடனடி ரொக்கம்:* வெறும் 5 நிமிடங்களில் பணப்பட்டுவாடா\n"
            f"• *100% பாதுகாப்பு:* காப்பீடு செய்யப்பட்ட பாதுகாப்பான வங்கி பெட்டக வசதி\n\n"
            f"📍 *உங்கள் கிளை:* {{branch_name}}\n"
            f"📞 *தொடர்புக்கு:* {{branch_phone}}\n\n"
            f"இன்றே வருகை தந்து பலன் பெறுங்கள்! விதிமுறைகளுக்கு உட்பட்டது."
        )
        sms = f"{festival} சிறப்பு தங்கக் கடன்: மாதம் {interest} வட்டி, கிராமுக்கு அதிக கடன்! 5 நிமிடங்களில் ரொக்கம். அழைக்க: {{branch_phone}}."
        social = (
            f"✨ {festival} சிறப்பு தங்கக் கடன் பெருவிழா - {org}!\n\n"
            f"🪙 குறைந்த வட்டி மாதம் {interest} மட்டுமே!\n"
            f"💰 கிராமுக்கு அதிகபட்ச கடன் மதிப்பு ({gold_val})\n"
            f"⚡ 5 நிமிடங்களில் உடனடி ரொக்கப் பட்டுவாடா!\n\n"
            f"இன்றே உங்கள் அருகிலுள்ள கிளையை {{branch_name}} அணுகவும்: {{branch_phone}}\n\n"
            f"#GoldLoan #PawnshopTamilNadu #TamilNaduGold #GoldLoanOffer #{festival.replace(' ', '')} #{org.replace(' ', '')}"
        )

    return {
        "campaign_title": title,
        "whatsapp_message": wa_msg,
        "sms_message": sms,
        "social_caption": social,
        "key_highlights": [
            f"Lowest Monthly Interest starting at {interest}",
            f"Highest Valuation up to {gold_val}",
            f"Instant 5-Minute Spot Cash Disbursement"
        ],
        "is_fallback": True,
    }


def generate_campaign_content(params: Dict[str, Any], custom_api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entrypoint: Generates campaign content using Google Gemini API (Free Tier).
    Attempts multiple free models; falls back smoothly if key is missing or quota exceeded.
    """
    api_key = get_configured_gemini_api_key(custom_api_key)
    prompt = build_gemini_prompt(params)

    if not api_key:
        logger.info("No Gemini API key provided. Using intelligent algorithmic campaign generator.")
        result = generate_fallback_campaign(params)
        result['note'] = "Generated via Built-in Smart Marketing Engine. Add a free Google Gemini API Key for custom generative AI."
        return result

    # Try configured models in order
    last_error = None
    for model_name in DEFAULT_MODELS:
        try:
            logger.info(f"Attempting Gemini generation using model '{model_name}'...")
            result = call_gemini_api(api_key, prompt, model_name=model_name)
            result['model_used'] = model_name
            result['is_ai_generated'] = True
            return result
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Failed generation with {model_name}: {e}. Trying next model...")

    logger.error(f"All Gemini models failed. Last error: {last_error}. Returning fallback.")
    fallback = generate_fallback_campaign(params)
    fallback['error'] = last_error
    fallback['note'] = f"Gemini API returned error ({last_error}). Displaying smart fallback template."
    return fallback
