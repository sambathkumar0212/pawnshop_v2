"""
Customer Portal Authentication & Automated Credential Services
Handles automated user account generation, randomized PIN generation, and bilingual WhatsApp message deep-links.
"""

import re
import secrets
import string
import urllib.parse
import logging
from django.utils import timezone
from django.conf import settings
from accounts.models import CustomUser, Role

logger = logging.getLogger(__name__)


def generate_secure_temp_pin(length: int = 8) -> str:
    """
    Generates an 8-character temporary PIN/password containing clear, unambiguous
    alphanumeric characters (avoiding 0, O, 1, I, l for readability).
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    # Ensure at least 4 letters and 4 digits for high entropy
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    
    chars = [secrets.choice(letters) for _ in range(4)] + [secrets.choice(digits) for _ in range(4)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def derive_customer_username(customer, base_prefix: str = "fm_") -> str:
    """
    Derives unique customer username: fm_ + last 10 digits of phone.
    Handles duplicate fallback cleanly (fm_<phone>_1, etc.).
    """
    raw_phone = customer.phone or ""
    digits_only = re.sub(r"\D", "", str(raw_phone))
    
    if len(digits_only) >= 10:
        phone_suffix = digits_only[-10:]
    elif digits_only:
        phone_suffix = digits_only.zfill(10)
    else:
        phone_suffix = str(customer.id or secrets.randbelow(1000000)).zfill(10)
    
    base_username = f"{base_prefix}{phone_suffix}"
    username = base_username
    counter = 1
    
    # Check uniqueness against existing users (excluding user already attached to this customer)
    while CustomUser.objects.filter(username=username).exclude(pk=customer.user_id if customer.user_id else None).exists():
        username = f"{base_username}_{counter}"
        counter += 1
        
    return username


def get_or_create_customer_role() -> Role:
    """Retrieves or creates the default Role for self-service customers."""
    role, _ = Role.objects.get_or_create(
        role_type=Role.CUSTOMER,
        defaults={
            "name": "Customer Portal User",
            "category": Role.CUSTOMER,
            "description": "Self-service customer portal user with view-only loan & payment permissions",
        }
    )
    return role


def provision_customer_portal_credentials(customer, reset_by=None, force_new_password: bool = True) -> tuple[CustomUser, str]:
    """
    Provisions or synchronizes a CustomUser account for the given Customer instance.
    Generates a secure temporary password/PIN and attaches it to the customer.
    
    Returns:
        tuple (CustomUser instance, plain_temp_password string)
    """
    temp_password = generate_secure_temp_pin(8) if force_new_password else (customer.temp_password_plain or generate_secure_temp_pin(8))
    username = derive_customer_username(customer)
    customer_role = get_or_create_customer_role()
    
    branch = customer.branch
    org = branch.organization if branch else None
    
    if customer.user:
        user = customer.user
        if not user.username:
            user.username = username
        user.first_name = customer.first_name
        user.last_name = customer.last_name
        user.phone = customer.phone
        user.email = customer.email or ""
        user.branch = branch
        user.organization = org
        user.role = customer_role
        user.is_active = customer.portal_active
        if force_new_password:
            user.set_password(temp_password)
        user.save()
    else:
        # Check if user with that username already exists
        existing_user = CustomUser.objects.filter(username=username).first()
        if existing_user:
            user = existing_user
            user.first_name = customer.first_name
            user.last_name = customer.last_name
            user.phone = customer.phone
            user.branch = branch
            user.organization = org
            user.role = customer_role
            user.is_active = customer.portal_active
            if force_new_password:
                user.set_password(temp_password)
            user.save()
        else:
            user = CustomUser.objects.create_user(
                username=username,
                email=customer.email or f"{username}@portal.local",
                first_name=customer.first_name,
                last_name=customer.last_name,
                phone=customer.phone,
                role=customer_role,
                branch=branch,
                organization=org,
                is_active=customer.portal_active,
            )
            user.set_password(temp_password)
            user.save()
            
        customer.user = user

    customer.temp_password_plain = temp_password
    customer.last_credential_reset_at = timezone.now()
    if reset_by:
        customer.last_credential_reset_by = reset_by
    customer.save(update_fields=['user', 'temp_password_plain', 'last_credential_reset_at', 'last_credential_reset_by', 'portal_active'])
    
    logger.info(f"Portal credentials provisioned for Customer #{customer.id} ({customer.full_name}) -> User: {user.username}")
    return user, temp_password


def build_customer_portal_whatsapp_message(customer, temp_password: str = None, request=None) -> str:
    """
    Constructs a bilingual English & Tamil WhatsApp message template with
    customer login credentials and direct portal deep links.
    """
    branch_name = customer.branch.name if customer.branch else "First Money Gold"
    branch_phone = getattr(customer.branch, 'phone', '') or getattr(customer.branch, 'contact_phone', '') or ''
    
    username = customer.user.username if customer.user else derive_customer_username(customer)
    password_to_show = temp_password or customer.temp_password_plain or "******"
    
    # Resolve portal URL
    if request:
        base_url = request.build_absolute_uri('/')[:-1]
    else:
        base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    portal_login_url = f"{base_url}/portal/login/"
    
    msg_lines = [
        f"🌟 *{branch_name} - Customer Portal Access*",
        f"வணக்கம் / Dear *{customer.full_name}*,",
        "",
        "Welcome to our Self-Service Customer Portal. You can now view your active loans, track payment histories, and pay your interest securely online via UPI QR code.",
        "",
        "🔐 *Your Login Credentials:*",
        f"👤 *Username:* `{username}`",
        f"🔑 *Password / PIN:* `{password_to_show}`",
        f"🌐 *Portal URL:* {portal_login_url}",
        "",
        "📌 *உங்கள் சுய சேவை போர்ட்டல் விபரங்கள்:*",
        f"உங்களது அடகு கடன் விபரங்கள், வட்டி நிலுவை மற்றும் UPI QR மூலம் எளிதாக வட்டி செலுத்த மேற்கண்ட லிங்கை கிளிக் செய்து லாகின் செய்யவும்.",
        "",
        "⚠️ *Security Note:* Please keep your PIN confidential and change your password upon your first login.",
    ]
    
    if branch_phone:
        msg_lines.extend(["", f"📞 *Branch Helpdesk:* {branch_phone}"])
        
    msg_lines.extend(["", f"Thank you for choosing *{branch_name}*! 🙏"])
    
    return "\n".join(msg_lines)


def get_customer_portal_whatsapp_url(customer, temp_password: str = None, request=None) -> str:
    """
    Returns the ready-to-click https://wa.me/ deep link containing the prefilled message.
    """
    phone_clean = re.sub(r"\D", "", str(customer.phone or ""))
    if len(phone_clean) == 10:
        phone_clean = f"91{phone_clean}"
    elif len(phone_clean) > 10 and not phone_clean.startswith("91") and len(phone_clean) == 12 and phone_clean.startswith("0"):
        phone_clean = f"91{phone_clean[-10:]}"
        
    message_body = build_customer_portal_whatsapp_message(customer, temp_password=temp_password, request=request)
    encoded_message = urllib.parse.quote(message_body)
    return f"https://wa.me/{phone_clean}?text={encoded_message}"
