"""
Services for Headless / Automated WhatsApp Message Dispatch using Playwright.
Persists browser profile in `.whatsapp_user_data/` so QR code is scanned once.
"""

import os
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import re
import time
import logging
import threading
import json
import base64
from pathlib import Path
from django.conf import settings
from django.utils import timezone
import datetime
from transactions.models import Loan, IRACAlertLog
from transactions.services_irac import render_irac_alert_message

logger = logging.getLogger(__name__)

SESSION_DIR = Path(settings.BASE_DIR) / ".whatsapp_user_data"

MODERN_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


def get_session_dir():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return str(SESSION_DIR)


def clean_stale_locks():
    """Removes stale Chromium Singleton lock files if a previous process terminated abruptly."""
    session_dir = Path(get_session_dir())
    for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"]:
        lock_file = session_dir / lock_name
        if lock_file.exists():
            try:
                lock_file.unlink(missing_ok=True)
            except Exception:
                pass


def get_launch_context_options(headless: bool = True) -> dict:
    """Standardizes launch parameters for persistent Chromium context to bypass WhatsApp browser version checks."""
    clean_stale_locks()
    return {
        "user_data_dir": get_session_dir(),
        "headless": headless,
        "user_agent": MODERN_CHROME_USER_AGENT,
        "viewport": {"width": 1280, "height": 800},
        "ignore_default_args": ["--enable-automation"],
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-zygote",
        ],
    }


def clean_phone_number(raw_phone: str) -> str:
    """Format phone number for Indian WhatsApp standard (91 + 10 digits)."""
    digits = re.sub(r"[^\d]", "", str(raw_phone or ""))
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10:
        return f"91{digits}"
    elif len(digits) == 12 and digits.startswith("91"):
        return digits
    return digits


def format_display_phone(raw_phone: str) -> str:
    """Format a 10 or 12 digit phone number nicely for human presentation (+91 XXXXX XXXXX)."""
    if not raw_phone:
        return ""
    digits = re.sub(r"[^\d]", "", str(raw_phone))
    if len(digits) == 12 and digits.startswith("91"):
        return f"+91 {digits[2:7]} {digits[7:]}"
    elif len(digits) == 10:
        return f"+91 {digits[:5]} {digits[5:]}"
    elif len(digits) > 10:
        return f"+{digits}"
    return raw_phone


def extract_connected_whatsapp_phone() -> str | None:
    """
    Inspects the local persistent Chromium LevelDB / storage to extract
    the active WhatsApp account's JID/Phone number without opening a browser.
    """
    import os
    session_dir = Path(get_session_dir())
    if not session_dir.exists():
        return None
    for root, dirs, files in os.walk(session_dir):
        for f in sorted(files, reverse=True):
            if f.endswith(('.ldb', '.log')):
                try:
                    filepath = os.path.join(root, f)
                    with open(filepath, 'rb') as fp:
                        content = fp.read().decode('latin1', errors='ignore')
                    m = re.search(r'last-wid(?:-md)?[^"]*"(\d{10,15})[:@]', content)
                    if m:
                        return m.group(1)
                except Exception:
                    pass
    return None


def is_whatsapp_paired() -> bool:
    """Checks if a verified paired session marker exists."""
    session_path = Path(settings.BASE_DIR) / ".whatsapp_user_data"
    marker = session_path / ".session_paired"
    return marker.exists()


def get_whatsapp_session_info() -> dict:
    """
    Returns detailed pairing status, formatted connected phone number, and metadata.
    """
    import json
    session_path = Path(settings.BASE_DIR) / ".whatsapp_user_data"
    marker = session_path / ".session_paired"
    
    if not marker.exists():
        return {
            "is_paired": False,
            "status": "unpaired",
            "phone": None,
            "raw_phone": None,
            "display_name": None,
            "paired_at": None,
            "message": "No WhatsApp account connected. Please scan QR code to pair."
        }
    
    phone = None
    raw_phone = None
    display_name = None
    paired_at = None

    try:
        content = marker.read_text(encoding="utf-8").strip()
        if content.startswith("{") and content.endswith("}"):
            data = json.loads(content)
            phone = data.get("phone")
            raw_phone = data.get("raw_phone")
            display_name = data.get("display_name")
            paired_at = data.get("paired_at")
    except Exception:
        pass

    # If phone was not yet recorded in marker, try auto-extracting from session storage
    if not phone or not raw_phone:
        extracted = extract_connected_whatsapp_phone()
        if extracted:
            raw_phone = extracted
            phone = format_display_phone(extracted)
            # Update marker with structured JSON
            try:
                marker_data = {
                    "paired": True,
                    "phone": phone,
                    "raw_phone": raw_phone,
                    "display_name": display_name or "",
                    "paired_at": paired_at or time.strftime('%Y-%m-%d %H:%M:%S'),
                }
                marker.write_text(json.dumps(marker_data, indent=2), encoding="utf-8")
            except Exception:
                pass

    display_phone = phone or "Connected WhatsApp Account"

    return {
        "is_paired": True,
        "status": "authenticated",
        "phone": display_phone,
        "raw_phone": raw_phone,
        "display_name": display_name,
        "paired_at": paired_at,
        "message": f"Connected to WhatsApp ({display_phone})"
    }


def reset_whatsapp_session() -> bool:
    """Wipes the .whatsapp_user_data directory and pairing flags so the user can re-link from scratch."""
    import shutil
    clean_stale_locks()
    session_dir = Path(get_session_dir())
    marker = session_dir / ".session_paired"
    if marker.exists():
        try:
            marker.unlink(missing_ok=True)
        except Exception:
            pass
    if session_dir.exists():
        try:
            shutil.rmtree(session_dir, ignore_errors=True)
            return True
        except Exception as e:
            logger.warning("Could not delete session dir: %s", e)
def get_pairing_state_file() -> Path:
    return Path(get_session_dir()) / "live_pairing_state.json"


def _load_pairing_state() -> dict:
    """Reads pairing state from shared JSON file so all Gunicorn workers stay synchronized."""
    state_file = get_pairing_state_file()
    if state_file.exists():
        try:
            content = state_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {
        'is_active': False,
        'status': 'idle',
        'qr_image_base64': None,
        'phone': None,
        'raw_phone': None,
        'message': 'No pairing in progress',
        'cancel_requested': False,
        'started_at': 0,
    }


def _save_pairing_state(state: dict):
    """Persists pairing state to shared JSON file."""
    state_file = get_pairing_state_file()
    try:
        state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Could not persist pairing state: %s", e)


# Global thread-safe Live QR Pairing State
LIVE_PAIRING_LOCK = threading.Lock()
LIVE_PAIRING_STATE = {
    'is_active': False,
    'status': 'idle',  # 'idle', 'starting', 'qr_ready', 'authenticated', 'timeout', 'error'
    'qr_image_base64': None,
    'phone': None,
    'raw_phone': None,
    'message': 'No pairing in progress',
    'cancel_requested': False,
    'started_at': 0,
}


def get_live_qr_pairing_status() -> dict:
    """Returns the current state of headless live QR code streaming & pairing across all worker processes."""
    session_info = get_whatsapp_session_info()
    if session_info.get('is_paired'):
        state = {
            'is_active': False,
            'is_paired': True,
            'status': 'authenticated',
            'phone': session_info['phone'],
            'raw_phone': session_info.get('raw_phone'),
            'display_name': session_info.get('display_name'),
            'message': session_info['message'],
            'qr_image_base64': None,
        }
        _save_pairing_state(state)
        return state

    with LIVE_PAIRING_LOCK:
        file_state = _load_pairing_state()
        state = dict(file_state)
        state['is_paired'] = False

        # If it's been in 'starting' state for more than 40s without QR or error, auto-mark timeout
        started_at = state.get('started_at') or 0
        if state.get('status') == 'starting' and started_at > 0 and (time.time() - started_at > 40):
            state['status'] = 'error'
            state['is_active'] = False
            state['message'] = 'Browser engine startup timed out. On cloud hosting, please use 1-Click WhatsApp Direct Broadcast.'
            _save_pairing_state(state)

        return state


def cancel_headless_qr_pairing():
    """Requests cancellation of active background QR pairing worker."""
    with LIVE_PAIRING_LOCK:
        LIVE_PAIRING_STATE.update({
            'cancel_requested': True,
            'is_active': False,
            'status': 'idle',
            'qr_image_base64': None,
            'message': 'Pairing cancelled.'
        })
        _save_pairing_state(LIVE_PAIRING_STATE)


def _run_headless_qr_pairing_worker(force_relink: bool = False, timeout_seconds: int = 120):
    """
    Background worker thread that runs Playwright headlessly, captures the live QR code screenshot,
    and streams it via base64 directly to the web modal.
    """
    from django.db import close_old_connections
    close_old_connections()

    start_init_state = {
        'is_active': True,
        'status': 'starting',
        'qr_image_base64': None,
        'message': 'Initializing WhatsApp Web engine...',
        'cancel_requested': False,
        'started_at': time.time(),
    }
    with LIVE_PAIRING_LOCK:
        LIVE_PAIRING_STATE.update(start_init_state)
        _save_pairing_state(LIVE_PAIRING_STATE)

    clean_stale_locks()
    context = None

    try:
        # 1. Safely attempt Playwright import
        try:
            from playwright.sync_api import sync_playwright
        except (ImportError, ModuleNotFoundError) as imp_err:
            raise RuntimeError(
                "Playwright library is not installed on this server. "
                "You can send broadcasts directly via 1-Click WhatsApp Direct sending!"
            )

        with sync_playwright() as p:
            try:
                context = p.chromium.launch_persistent_context(
                    **get_launch_context_options(headless=True)
                )
            except Exception as launch_err:
                raise RuntimeError(
                    f"Chromium browser engine could not be launched on this cloud server: {launch_err}. "
                    "Please use 1-Click WhatsApp Direct broadcast."
                )

            page = context.pages[0] if context.pages else context.new_page()
            
            with LIVE_PAIRING_LOCK:
                LIVE_PAIRING_STATE['message'] = 'Connecting to WhatsApp Web...'
                _save_pairing_state(LIVE_PAIRING_STATE)

            try:
                page.goto("https://web.whatsapp.com/", timeout=50000)
            except Exception as nav_err:
                logger.warning("WhatsApp Web navigation notice: %s", nav_err)

            start_time = time.time()
            qr_captured = False

            while time.time() - start_time < timeout_seconds:
                with LIVE_PAIRING_LOCK:
                    current_file_state = _load_pairing_state()
                    if current_file_state.get('cancel_requested') or LIVE_PAIRING_STATE.get('cancel_requested'):
                        logger.info("QR pairing worker cancelled by user.")
                        break

                # 1. Check if user is already logged in or completed scan
                try:
                    is_logged_in = (
                        page.locator('div[contenteditable="true"][data-tab="3"]').is_visible()
                        or page.locator('div[aria-label="Chat list"]').is_visible()
                        or page.locator('span[data-icon="chat"]').is_visible()
                        or page.locator('header').is_visible()
                        or page.locator('#pane-side').is_visible()
                        or page.locator('div[role="textbox"]').is_visible()
                    )
                except Exception:
                    is_logged_in = False

                if is_logged_in:
                    time.sleep(4)  # Let local storage keys settle
                    raw_phone_extracted = ""
                    display_name = ""
                    try:
                        eval_data = page.evaluate("""() => {
                            let res = { phone: '', name: '' };
                            try {
                                for (let i = 0; i < localStorage.length; i++) {
                                    let k = localStorage.key(i) || '';
                                    let v = localStorage.getItem(k) || '';
                                    if (k.includes('last-wid') || k.includes('user-id') || k.includes('me-jid')) {
                                        let m = v.match(/(\\d{10,15})/);
                                        if (m && !res.phone) {
                                            res.phone = m[1];
                                        }
                                    }
                                    if (k.includes('pushname') && !res.name) {
                                        res.name = v.replace(/["']/g, '').trim();
                                    }
                                }
                            } catch(e) {}
                            return res;
                        }""")
                        if isinstance(eval_data, dict):
                            raw_phone_extracted = eval_data.get('phone', '')
                            display_name = eval_data.get('name', '')
                    except Exception:
                        pass

                    if not raw_phone_extracted:
                        raw_phone_extracted = extract_connected_whatsapp_phone() or ""

                    formatted_phone = format_display_phone(raw_phone_extracted) if raw_phone_extracted else ""
                    marker = Path(get_session_dir()) / ".session_paired"
                    try:
                        marker_data = {
                            "paired": True,
                            "phone": formatted_phone or "Connected WhatsApp Device",
                            "raw_phone": raw_phone_extracted,
                            "display_name": display_name,
                            "paired_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                        }
                        marker.write_text(json.dumps(marker_data, indent=2), encoding="utf-8")
                    except Exception:
                        try:
                            marker.write_text("PAIRED", encoding="utf-8")
                        except Exception:
                            pass

                    with LIVE_PAIRING_LOCK:
                        LIVE_PAIRING_STATE.update({
                            'is_active': False,
                            'status': 'authenticated',
                            'qr_image_base64': None,
                            'phone': formatted_phone or "Connected WhatsApp Device",
                            'raw_phone': raw_phone_extracted,
                            'display_name': display_name,
                            'message': f"WhatsApp paired successfully! Connected: {formatted_phone or 'Active Device'}"
                        })
                        _save_pairing_state(LIVE_PAIRING_STATE)
                    
                    logger.info("✅ Headless WhatsApp QR pairing completed! Connected: %s", formatted_phone)
                    return

                # 2. Check for QR code canvas/element
                try:
                    qr_loc = page.locator('canvas, div[data-testid="qrcode"], div[data-ref]').first
                    if qr_loc.is_visible():
                        time.sleep(0.5)
                        qr_bytes = qr_loc.screenshot()
                        qr_b64 = "data:image/png;base64," + base64.b64encode(qr_bytes).decode('utf-8')
                        with LIVE_PAIRING_LOCK:
                            LIVE_PAIRING_STATE['status'] = 'qr_ready'
                            LIVE_PAIRING_STATE['qr_image_base64'] = qr_b64
                            LIVE_PAIRING_STATE['message'] = 'Scan this QR code with WhatsApp on your phone'
                            _save_pairing_state(LIVE_PAIRING_STATE)
                        qr_captured = True
                except Exception:
                    pass

                # 3. Check if QR code expired and needs reload click
                try:
                    reload_btn = page.locator('button:has-text("Click to reload QR code"), div[data-testid="qrcode"] button, span[role="button"]:has(span[data-icon="refresh"])').first
                    if reload_btn.is_visible():
                        reload_btn.click()
                        time.sleep(1.5)
                except Exception:
                    pass

                time.sleep(1.5)

            # If loop finished without login
            with LIVE_PAIRING_LOCK:
                if LIVE_PAIRING_STATE.get('status') != 'authenticated':
                    LIVE_PAIRING_STATE.update({
                        'is_active': False,
                        'status': 'timeout',
                        'qr_image_base64': None,
                        'message': 'QR code pairing timed out. Please click Retry to generate a new QR code.'
                    })
                    _save_pairing_state(LIVE_PAIRING_STATE)

    except Exception as fatal_err:
        logger.error("Error in headless QR pairing worker: %s", fatal_err)
        with LIVE_PAIRING_LOCK:
            LIVE_PAIRING_STATE.update({
                'is_active': False,
                'status': 'error',
                'qr_image_base64': None,
                'message': str(fatal_err)
            })
            _save_pairing_state(LIVE_PAIRING_STATE)
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        clean_stale_locks()


def start_headless_qr_pairing_thread(force_relink: bool = False) -> dict:
    """
    Spawns or resumes the background headless QR code streaming and pairing worker.
    """
    with LIVE_PAIRING_LOCK:
        file_state = _load_pairing_state()
        started_at = file_state.get('started_at') or 0
        if file_state.get('is_active') and (time.time() - started_at < 120):
            return get_live_qr_pairing_status()

        fresh_state = {
            'is_active': True,
            'status': 'starting',
            'qr_image_base64': None,
            'message': 'Starting WhatsApp Web engine...',
            'cancel_requested': False,
            'started_at': time.time(),
        }
        LIVE_PAIRING_STATE.update(fresh_state)
        _save_pairing_state(LIVE_PAIRING_STATE)

    t = threading.Thread(
        target=_run_headless_qr_pairing_worker,
        args=(force_relink,),
        daemon=True,
        name="whatsapp-headless-qr-pairing-worker"
    )
    t.start()
    return get_live_qr_pairing_status()


def pair_whatsapp_interactive(timeout_seconds: int = 120) -> dict:
    """
    Starts headless live QR pairing.
    (Backwards compatible with pair_whatsapp_interactive endpoint).
    """
    start_headless_qr_pairing_thread(force_relink=True)
    return {
        "success": True,
        "message": "Headless QR code generator started. Live QR is streaming directly to your screen modal.",
        "status": "starting",
    }


def get_whatsapp_qr_image_base64() -> dict:
    """
    Returns live QR code image stream or connected session details.
    """
    return get_live_qr_pairing_status()





def send_whatsapp_message_headless(phone: str, message: str, headless: bool = True) -> dict:
    """
    Dispatches a single message headlessly using the persistent session.
    """
    from playwright.sync_api import sync_playwright
    import urllib.parse

    phone_clean = clean_phone_number(phone)
    if not phone_clean or len(phone_clean) < 10:
        return {"success": False, "error": f"Invalid phone number: {phone}"}

    clean_stale_locks()
    with sync_playwright() as p:
        context = None
        try:
            context = p.chromium.launch_persistent_context(
                **get_launch_context_options(headless=headless)
            )
            page = context.pages[0] if context.pages else context.new_page()

            # Encode message into WhatsApp Web send URL
            encoded_msg = urllib.parse.quote(message)
            send_url = f"https://web.whatsapp.com/send?phone={phone_clean}&text={encoded_msg}"

            page.goto(send_url, timeout=45000)
            time.sleep(4)  # Initial wait for chat to initialize

            # Check if invalid number dialog popped up
            if page.locator("text=Phone number shared via url is invalid").is_visible() or page.locator("text=URL is invalid").is_visible():
                return {"success": False, "error": f"Phone number +{phone_clean} is not registered on WhatsApp"}

            # Look for the Send button or composer
            send_btn = page.locator('button[aria-label="Send"], button[aria-label="Send message"], span[data-icon="send"], span[data-icon="send-light"], button span[data-icon="send"], button[data-tab="11"]').first

            # Wait up to 15 seconds for composer or send button
            try:
                send_btn.wait_for(state="visible", timeout=15000)
                send_btn.click()
                time.sleep(2)  # Wait for message dispatch animation
                return {"success": True, "phone": phone_clean}
            except Exception:
                # If send button not found, try pressing Enter in the composer
                composer = page.locator('footer div[contenteditable="true"], div[role="textbox"][contenteditable="true"], div[contenteditable="true"][data-tab="10"], div[contenteditable="true"][data-tab="6"]').first
                if composer.is_visible():
                    composer.focus()
                    composer.press("Enter")
                    time.sleep(2)
                    return {"success": True, "phone": phone_clean}

                # Secondary check if invalid number dialog appeared late
                if page.locator("text=Phone number shared via url is invalid").is_visible():
                    return {"success": False, "error": f"Phone number +{phone_clean} is not registered on WhatsApp"}

                return {"success": False, "error": "Timed out waiting for WhatsApp composer/send button"}

        except Exception as e:
            logger.exception("Error in headless WhatsApp dispatch: %s", e)
            return {"success": False, "error": str(e)}
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            clean_stale_locks()


# ---------------------------------------------------------------------------
# Automated New Customer Welcome Wish Dispatches
# ---------------------------------------------------------------------------

def build_customer_welcome_whatsapp_message(customer, lang: str = 'ta') -> str:
    """
    Constructs a warm, highly professional bilingual welcome message for a newly onboarded customer.
    """
    branch = getattr(customer, 'branch', None)
    org_name = 'First Money Gold'
    if branch and getattr(branch, 'organization', None):
        org_name = branch.organization.name or 'First Money Gold'
    elif hasattr(settings, 'ORGANIZATION_NAME'):
        org_name = getattr(settings, 'ORGANIZATION_NAME', 'First Money Gold')

    branch_name = getattr(branch, 'name', '') or org_name
    branch_phone = getattr(branch, 'phone', '') or getattr(settings, 'COMPANY_PHONE', '9876543210')
    customer_name = getattr(customer, 'full_name', '') or f"{getattr(customer, 'first_name', '')} {getattr(customer, 'last_name', '')}".strip() or 'Valued Customer'

    if lang == 'en':
        return (
            f"🌟 *WELCOME TO {org_name}!* 🌟\n\n"
            f"Dear *{customer_name}*,\n"
            f"Welcome to the {org_name} family! We are delighted to have you as our valued customer. ✨\n\n"
            f"💎 *Our Core Services:*\n"
            f"• Instant Gold Loans at lowest interest rates (starting 0.99%)\n"
            f"• 100% Safe & Insured Bank-Grade Vault Storage\n"
            f"• Spot Cash for Old / Used Gold Ornaments\n"
            f"• Quick 5-Minute Direct Disbursal\n\n"
            f"📍 Your Branch: *{branch_name}*\n"
            f"📞 Helpline: *{branch_phone}*\n\n"
            f"Thank you for choosing us as your trusted financial partner! 🙏"
        )

    # Tamil default
    return (
        f"🌟 *{org_name}-க்கு அன்புடன் வரவேற்கிறோம்!* 🌟\n\n"
        f"அன்புள்ள *{customer_name}* அவர்களுக்கு,\n"
        f"எங்கள் {org_name} குடும்பத்தில் தங்களை இணைத்துக் கொண்டதில் பெருமகிழ்ச்சி அடைகிறோம்! ✨\n\n"
        f"💎 *எங்களின் சிறப்பு நிதிச் சேவைகள்:*\n"
        f"• மிகக் குறைந்த வட்டியில் உடனடி தங்கக் கடன் (0.99% முதல்)\n"
        f"• 100% பாதுகாப்பான வங்கி பெட்டக பாதுகாப்பு\n"
        f"• பழைய & பயன்படுத்திய தங்க நகைகளுக்கு உடனடி ரொக்கம்\n"
        f"• 5 நிமிடங்களில் உடனடி கடன் பட்டுவாடா\n\n"
        f"📍 உங்கள் கிளை: *{branch_name}*\n"
        f"📞 தொடர்பு எண்: *{branch_phone}*\n\n"
        f"எங்களை நம்பியதற்கு மனமார்ந்த நன்றிகள்! 🙏"
    )


def send_single_customer_welcome_automated(customer, user=None, headless: bool = True) -> dict:
    """
    Dispatches a single welcome WhatsApp message for a newly created customer
    and records the transaction in MarketingCampaignLog.
    """
    from transactions.models import MarketingCampaignLog
    from transactions.services_whatsapp import normalize_phone_number

    raw_phone = getattr(customer, 'phone', '') or ''
    norm_phone = normalize_phone_number(raw_phone)
    cust_name = getattr(customer, 'full_name', '') or str(customer)
    branch = getattr(customer, 'branch', None)

    if not norm_phone:
        err_msg = f"Skipped: Customer '{cust_name}' does not have a valid WhatsApp mobile number ({raw_phone})"
        logger.warning(err_msg)
        try:
            MarketingCampaignLog.objects.create(
                template_key='welcome_new_customer',
                campaign_name='New Customer Welcome Wish',
                recipient_name=cust_name,
                recipient_phone=raw_phone or 'N/A',
                recipient_type='customer',
                branch=branch,
                channel='whatsapp_web',
                status='failed',
                message_snippet=err_msg,
                sent_by=user
            )
        except Exception as e:
            logger.warning("Could not create MarketingCampaignLog for skipped welcome: %s", e)
        return {"success": False, "status": "skipped", "error": err_msg}

    welcome_msg = build_customer_welcome_whatsapp_message(customer, lang='ta')

    if not is_whatsapp_paired():
        err_msg = "Skipped: WhatsApp Web session is not paired / connected on server"
        logger.warning(err_msg)
        try:
            MarketingCampaignLog.objects.create(
                template_key='welcome_new_customer',
                campaign_name='New Customer Welcome Wish',
                recipient_name=cust_name,
                recipient_phone=norm_phone,
                recipient_type='customer',
                branch=branch,
                channel='whatsapp_web',
                status='failed',
                message_snippet=f"{err_msg}. Message queued: {welcome_msg[:100]}...",
                sent_by=user
            )
        except Exception as e:
            logger.warning("Could not create MarketingCampaignLog for offline welcome: %s", e)
        return {"success": False, "status": "offline", "error": err_msg}

    # Dispatch via headless Playwright worker
    res = send_whatsapp_message_headless(phone=norm_phone, message=welcome_msg, headless=headless)
    
    if res.get('success'):
        status = 'sent'
        snippet = welcome_msg[:250]
    else:
        status = 'failed'
        snippet = f"Failed: {res.get('error', 'Unknown WhatsApp dispatch error')}"

    try:
        MarketingCampaignLog.objects.create(
            template_key='welcome_new_customer',
            campaign_name='New Customer Welcome Wish',
            recipient_name=cust_name,
            recipient_phone=norm_phone,
            recipient_type='customer',
            branch=branch,
            channel='whatsapp_web',
            status=status,
            message_snippet=snippet,
            sent_by=user
        )
    except Exception as e:
        logger.warning("Could not log welcome wish MarketingCampaignLog: %s", e)

    return {
        "success": res.get('success', False),
        "status": status,
        "phone": norm_phone,
        "customer_name": cust_name,
        "error": res.get('error')
    }


def _dispatch_customer_welcome_worker(customer_id: int, user_id: int = None):
    """Background worker entry point."""
    import os
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    from accounts.models import Customer
    from django.contrib.auth import get_user_model

    try:
        customer = Customer.objects.select_related('branch', 'branch__organization').get(id=customer_id)
    except Exception as e:
        logger.error(f"Customer #{customer_id} not found for background welcome dispatch: {e}")
        return

    user = None
    if user_id:
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except Exception:
            pass

    try:
        result = send_single_customer_welcome_automated(customer=customer, user=user, headless=True)
        logger.info(f"Background Welcome Wish result for customer #{customer_id} ({customer.full_name}): {result}")
    except Exception as e:
        logger.exception(f"Exception during background welcome wish dispatch for customer #{customer_id}: {e}")


def send_customer_welcome_whatsapp_async(customer_id: int, user_id: int = None):
    """Spawns an asynchronous background worker thread to dispatch welcome message."""
    t = threading.Thread(
        target=_dispatch_customer_welcome_worker,
        args=(customer_id, user_id),
        daemon=True,
        name=f"welcome-wish-{customer_id}"
    )
    t.start()
    return t


# ---------------------------------------------------------------------------
# Automated Gold Loan Customer Identity OTP Dispatches
# ---------------------------------------------------------------------------

def send_single_loan_otp_automated(loan, user=None, headless: bool = True) -> dict:
    """
    Dispatches a 6-digit customer verification OTP WhatsApp message for a newly initiated loan application
    and logs the transaction in MarketingCampaignLog.
    """
    from transactions.models import MarketingCampaignLog
    from transactions.services_whatsapp import normalize_phone_number

    customer = getattr(loan, 'customer', None)
    raw_phone = getattr(customer, 'phone', '') or ''
    norm_phone = normalize_phone_number(raw_phone)
    cust_name = getattr(customer, 'full_name', '') or (str(customer) if customer else 'Customer')
    branch = getattr(loan, 'branch', None) or (getattr(customer, 'branch', None) if customer else None)
    loan_num = getattr(loan, 'loan_number', 'N/A')

    if not norm_phone:
        err_msg = f"Skipped: Customer '{cust_name}' does not have a valid WhatsApp mobile number ({raw_phone})"
        logger.warning(err_msg)
        try:
            MarketingCampaignLog.objects.create(
                template_key='loan_creation_otp',
                campaign_name=f"Loan #{loan_num} Customer Verification OTP",
                recipient_name=cust_name,
                recipient_phone=raw_phone or 'N/A',
                recipient_type='customer',
                branch=branch,
                channel='whatsapp_web',
                status='failed',
                message_snippet=err_msg,
                sent_by=user
            )
        except Exception as e:
            logger.warning("Could not create MarketingCampaignLog for skipped OTP: %s", e)
        return {"success": False, "status": "skipped", "error": err_msg}

    otp_msg = loan.build_otp_whatsapp_message(lang='ta')

    if not is_whatsapp_paired():
        err_msg = "Skipped: WhatsApp Web session is not paired / connected on server"
        logger.warning(err_msg)
        try:
            MarketingCampaignLog.objects.create(
                template_key='loan_creation_otp',
                campaign_name=f"Loan #{loan_num} Customer Verification OTP",
                recipient_name=cust_name,
                recipient_phone=norm_phone,
                recipient_type='customer',
                branch=branch,
                channel='whatsapp_web',
                status='failed',
                message_snippet=f"{err_msg}. OTP Code: {loan.otp_code}",
                sent_by=user
            )
        except Exception as e:
            logger.warning("Could not create MarketingCampaignLog for offline OTP: %s", e)
        return {"success": False, "status": "offline", "error": err_msg, "otp_code": loan.otp_code}

    # Dispatch via headless Playwright worker
    res = send_whatsapp_message_headless(phone=norm_phone, message=otp_msg, headless=headless)
    
    if res.get('success'):
        status = 'sent'
        snippet = f"OTP {loan.otp_code} sent successfully for Loan #{loan_num}"
    else:
        status = 'failed'
        snippet = f"Failed: {res.get('error', 'Unknown WhatsApp dispatch error')}"

    try:
        MarketingCampaignLog.objects.create(
            template_key='loan_creation_otp',
            campaign_name=f"Loan #{loan_num} Customer Verification OTP",
            recipient_name=cust_name,
            recipient_phone=norm_phone,
            recipient_type='customer',
            branch=branch,
            channel='whatsapp_web',
            status=status,
            message_snippet=snippet,
            sent_by=user
        )
    except Exception as e:
        logger.warning("Could not log loan OTP MarketingCampaignLog: %s", e)

    return {
        "success": res.get('success', False),
        "status": status,
        "phone": norm_phone,
        "loan_number": loan_num,
        "otp_code": loan.otp_code,
        "customer_name": cust_name,
        "error": res.get('error')
    }


def _dispatch_loan_otp_worker(loan_id: int, user_id: int = None):
    """Background worker entry point for loan OTP dispatch."""
    import os
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    from transactions.models import Loan
    from django.contrib.auth import get_user_model

    try:
        loan = Loan.objects.select_related('customer', 'branch', 'branch__organization').get(id=loan_id)
    except Exception as e:
        logger.error(f"Loan #{loan_id} not found for background OTP dispatch: {e}")
        return

    user = None
    if user_id:
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except Exception:
            pass

    try:
        result = send_single_loan_otp_automated(loan=loan, user=user, headless=True)
        logger.info(f"Background OTP result for Loan #{loan.loan_number} ({loan.customer.full_name}): {result}")
    except Exception as e:
        logger.exception(f"Exception during background OTP dispatch for Loan #{loan_id}: {e}")


def send_loan_otp_whatsapp_async(loan_id: int, user_id: int = None):
    """Spawns an asynchronous background worker thread to dispatch customer OTP message."""
    t = threading.Thread(
        target=_dispatch_loan_otp_worker,
        args=(loan_id, user_id),
        daemon=True,
        name=f"loan-otp-{loan_id}"
    )
    t.start()
    return t


def send_batch_retention_promos_automated(
    promo_items: list,
    delay_between_seconds: int = 3,
    headless: bool = True,
    user = None
) -> dict:
    """
    Dispatches customer retention & re-pledge promo offers in a single persistent browser session.
    Reuses browser context across all messages for maximum performance and reliability.
    """
    from playwright.sync_api import sync_playwright
    import urllib.parse
    from transactions.models import LoanWhatsAppLog, MarketingCampaignLog

    results = {
        "total": len(promo_items),
        "sent": 0,
        "failed": 0,
        "details": [],
    }

    if not promo_items:
        return results

    if not is_whatsapp_paired():
        results["error"] = "WhatsApp Web session is not paired. Please pair WhatsApp Web from Digital Marketing/Loans page first."
        for item in promo_items:
            results["failed"] += 1
            results["details"].append({
                "customer": item.get('name', 'Customer'),
                "phone": item.get('phone', ''),
                "status": "FAILED",
                "error": "WhatsApp session not paired"
            })
        return results

    clean_stale_locks()
    with sync_playwright() as p:
        context = None
        try:
            context = p.chromium.launch_persistent_context(
                **get_launch_context_options(headless=headless)
            )
            page = context.pages[0] if context.pages else context.new_page()

            # Pre-warm WhatsApp Web
            page.goto("https://web.whatsapp.com/", timeout=45000)
            time.sleep(5)

            for item in promo_items:
                loan = item.get('loan')
                cust = item.get('customer')
                cust_name = item.get('name') or (getattr(cust, 'first_name', '') if cust else 'Valued Customer')
                raw_phone = item.get('phone') or ''
                phone_clean = clean_phone_number(raw_phone)
                promo_text = item.get('message', '')

                if not phone_clean or len(phone_clean) < 10:
                    results["failed"] += 1
                    err_msg = f"Invalid phone number: '{raw_phone}'"
                    results["details"].append({
                        "loan_no": getattr(loan, 'loan_number', ''),
                        "customer": cust_name,
                        "phone": raw_phone,
                        "status": "FAILED",
                        "error": err_msg,
                    })
                    try:
                        MarketingCampaignLog.objects.create(
                            template_key='repledge_retention',
                            campaign_name='Autopilot Re-Pledge Retention',
                            recipient_name=cust_name,
                            recipient_phone=raw_phone,
                            recipient_type='customer',
                            channel='whatsapp_blast',
                            status='failed',
                            message_snippet=promo_text[:300],
                            sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                        )
                    except Exception:
                        pass
                    continue

                encoded_msg = urllib.parse.quote(promo_text)
                send_url = f"https://web.whatsapp.com/send?phone={phone_clean}&text={encoded_msg}"

                try:
                    page.goto(send_url, timeout=35000)
                    time.sleep(3)

                    # Check for invalid number popup
                    if page.locator("text=Phone number shared via url is invalid").is_visible() or page.locator("text=URL is invalid").is_visible():
                        results["failed"] += 1
                        err_msg = f"Phone number +{phone_clean} is not registered on WhatsApp"
                        results["details"].append({
                            "loan_no": getattr(loan, 'loan_number', ''),
                            "customer": cust_name,
                            "phone": phone_clean,
                            "status": "FAILED",
                            "error": err_msg,
                        })
                        try:
                            MarketingCampaignLog.objects.create(
                                template_key='repledge_retention',
                                campaign_name='Autopilot Re-Pledge Retention',
                                recipient_name=cust_name,
                                recipient_phone=phone_clean,
                                recipient_type='customer',
                                channel='whatsapp_blast',
                                status='failed',
                                message_snippet=promo_text[:300],
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                            )
                        except Exception:
                            pass

                        try:
                            ok_btn = page.locator('button:has-text("OK"), div[role="button"]:has-text("OK")').first
                            if ok_btn.is_visible():
                                ok_btn.click()
                        except Exception:
                            pass
                        continue

                    # Look for Send button or composer
                    send_btn = page.locator('button[aria-label="Send"], button[aria-label="Send message"], span[data-icon="send"], span[data-icon="send-light"], button span[data-icon="send"], button[data-tab="11"]').first
                    sent_success = False

                    try:
                        send_btn.wait_for(state="visible", timeout=12000)
                        send_btn.click()
                        sent_success = True
                    except Exception:
                        composer = page.locator('footer div[contenteditable="true"], div[role="textbox"][contenteditable="true"], div[contenteditable="true"][data-tab="10"], div[contenteditable="true"][data-tab="6"]').first
                        if composer.is_visible():
                            composer.focus()
                            composer.press("Enter")
                            sent_success = True

                    if sent_success:
                        time.sleep(delay_between_seconds)

                        # Record in database logs
                        try:
                            MarketingCampaignLog.objects.create(
                                template_key='repledge_retention',
                                campaign_name='Autopilot Re-Pledge Retention',
                                recipient_name=cust_name,
                                recipient_phone=phone_clean,
                                recipient_type='customer',
                                channel='whatsapp_blast',
                                status='sent',
                                message_snippet=promo_text[:300],
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                            )
                        except Exception as log_err:
                            logger.warning("Could not create MarketingCampaignLog: %s", log_err)

                        try:
                            LoanWhatsAppLog.objects.create(
                                loan=loan,
                                customer=cust,
                                recipient_phone=phone_clean,
                                notification_type='marketing_broadcast',
                                status='sent',
                                message_content=promo_text,
                                channel='automated_browser',
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                            )
                        except Exception as log_err:
                            logger.warning("Could not create LoanWhatsAppLog: %s", log_err)

                        results["sent"] += 1
                        results["details"].append({
                            "loan_no": getattr(loan, 'loan_number', ''),
                            "customer": cust_name,
                            "phone": phone_clean,
                            "status": "SENT",
                        })
                    else:
                        results["failed"] += 1
                        err_msg = "Could not locate WhatsApp send button / timeout"
                        results["details"].append({
                            "loan_no": getattr(loan, 'loan_number', ''),
                            "customer": cust_name,
                            "phone": phone_clean,
                            "status": "FAILED",
                            "error": err_msg,
                        })
                        try:
                            MarketingCampaignLog.objects.create(
                                template_key='repledge_retention',
                                campaign_name='Autopilot Re-Pledge Retention',
                                recipient_name=cust_name,
                                recipient_phone=phone_clean,
                                recipient_type='customer',
                                channel='whatsapp_blast',
                                status='failed',
                                message_snippet=promo_text[:300],
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                            )
                        except Exception:
                            pass

                except Exception as ex:
                    results["failed"] += 1
                    err_msg = str(ex)
                    results["details"].append({
                        "loan_no": getattr(loan, 'loan_number', ''),
                        "customer": cust_name,
                        "phone": phone_clean,
                        "status": "FAILED",
                        "error": err_msg,
                    })
                    try:
                        MarketingCampaignLog.objects.create(
                            template_key='repledge_retention',
                            campaign_name='Autopilot Re-Pledge Retention',
                            recipient_name=cust_name,
                            recipient_phone=phone_clean,
                            recipient_type='customer',
                            channel='whatsapp_blast',
                            status='failed',
                            message_snippet=promo_text[:300],
                            sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.exception("Batch retention promo automated WhatsApp dispatch encountered an exception: %s", e)
            results["error"] = str(e)
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            clean_stale_locks()

    return results


def send_batch_special_wishes_automated(
    wish_items: list,
    delay_between_seconds: int = 3,
    headless: bool = True,
    user=None
) -> dict:
    """
    Dispatches automated WhatsApp Birthday & Wedding Anniversary greetings in a single persistent browser session.
    Logs successful dispatches to MarketingCampaignLog and prevents duplicate wishes.
    """
    from playwright.sync_api import sync_playwright
    import urllib.parse
    from transactions.models import MarketingCampaignLog

    results = {
        "total": len(wish_items),
        "sent": 0,
        "failed": 0,
        "details": [],
    }

    if not wish_items:
        return results

    if not is_whatsapp_paired():
        results["error"] = "WhatsApp Web session is not paired. Please pair WhatsApp Web from Digital Marketing/Autopilot page first."
        for item in wish_items:
            results["failed"] += 1
            results["details"].append({
                "customer": item.get('name', 'Customer'),
                "phone": item.get('phone', ''),
                "occasion": item.get('occasion_type', 'greeting'),
                "status": "FAILED",
                "error": "WhatsApp session not paired"
            })
        return results

    clean_stale_locks()
    with sync_playwright() as p:
        context = None
        try:
            context = p.chromium.launch_persistent_context(
                **get_launch_context_options(headless=headless)
            )
            page = context.pages[0] if context.pages else context.new_page()

            # Pre-warm WhatsApp Web
            page.goto("https://web.whatsapp.com/", timeout=45000)
            time.sleep(5)

            for item in wish_items:
                cust = item.get('customer')
                cust_name = item.get('name') or (getattr(cust, 'first_name', '') if cust else 'Valued Customer')
                raw_phone = item.get('phone') or ''
                phone_clean = clean_phone_number(raw_phone)
                wish_text = item.get('message', '')
                occasion_type = item.get('occasion_type', 'birthday')
                campaign_name = item.get('campaign_name') or ('Birthday Wishes (Autopilot)' if occasion_type == 'birthday' else 'Wedding Anniversary Wishes (Autopilot)')
                template_key = 'birthday_wishes' if occasion_type == 'birthday' else 'anniversary_wishes'

                if not phone_clean or len(phone_clean) < 10:
                    results["failed"] += 1
                    err_msg = f"Invalid phone number: '{raw_phone}'"
                    results["details"].append({
                        "customer": cust_name,
                        "phone": raw_phone,
                        "occasion": occasion_type,
                        "status": "FAILED",
                        "error": err_msg,
                    })
                    try:
                        MarketingCampaignLog.objects.create(
                            template_key=template_key,
                            campaign_name=campaign_name,
                            recipient_name=cust_name,
                            recipient_phone=raw_phone,
                            recipient_type='customer',
                            channel='whatsapp_blast',
                            status='failed',
                            message_snippet=wish_text[:300],
                            sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                        )
                    except Exception:
                        pass
                    continue

                encoded_msg = urllib.parse.quote(wish_text)
                send_url = f"https://web.whatsapp.com/send?phone={phone_clean}&text={encoded_msg}"

                try:
                    page.goto(send_url, timeout=35000)
                    time.sleep(3)

                    # Check for invalid number popup
                    if page.locator("text=Phone number shared via url is invalid").is_visible() or page.locator("text=URL is invalid").is_visible():
                        results["failed"] += 1
                        err_msg = f"Phone number +{phone_clean} is not registered on WhatsApp"
                        results["details"].append({
                            "customer": cust_name,
                            "phone": phone_clean,
                            "occasion": occasion_type,
                            "status": "FAILED",
                            "error": err_msg,
                        })
                        try:
                            MarketingCampaignLog.objects.create(
                                template_key=template_key,
                                campaign_name=campaign_name,
                                recipient_name=cust_name,
                                recipient_phone=phone_clean,
                                recipient_type='customer',
                                channel='whatsapp_blast',
                                status='failed',
                                message_snippet=wish_text[:300],
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                            )
                        except Exception:
                            pass

                        try:
                            ok_btn = page.locator('button:has-text("OK"), div[role="button"]:has-text("OK")').first
                            if ok_btn.is_visible():
                                ok_btn.click()
                        except Exception:
                            pass
                        continue

                    # Look for Send button or composer
                    send_btn = page.locator('button[aria-label="Send"], button[aria-label="Send message"], span[data-icon="send"], span[data-icon="send-light"], button span[data-icon="send"], button[data-tab="11"]').first
                    sent_success = False

                    try:
                        send_btn.wait_for(state="visible", timeout=12000)
                        send_btn.click()
                        sent_success = True
                    except Exception:
                        composer = page.locator('footer div[contenteditable="true"], div[role="textbox"][contenteditable="true"], div[contenteditable="true"][data-tab="10"], div[contenteditable="true"][data-tab="6"]').first
                        if composer.is_visible():
                            composer.focus()
                            composer.press("Enter")
                            sent_success = True

                    if sent_success:
                        time.sleep(delay_between_seconds)

                        try:
                            MarketingCampaignLog.objects.create(
                                template_key=template_key,
                                campaign_name=campaign_name,
                                recipient_name=cust_name,
                                recipient_phone=phone_clean,
                                recipient_type='customer',
                                channel='whatsapp_blast',
                                status='sent',
                                message_snippet=wish_text[:300],
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                            )
                        except Exception as log_err:
                            logger.warning("Could not create MarketingCampaignLog for wish: %s", log_err)

                        results["sent"] += 1
                        results["details"].append({
                            "customer": cust_name,
                            "phone": phone_clean,
                            "occasion": occasion_type,
                            "status": "SENT",
                        })
                    else:
                        results["failed"] += 1
                        err_msg = "Send button / chat composer not found or timed out"
                        results["details"].append({
                            "customer": cust_name,
                            "phone": phone_clean,
                            "occasion": occasion_type,
                            "status": "FAILED",
                            "error": err_msg,
                        })
                        try:
                            MarketingCampaignLog.objects.create(
                                template_key=template_key,
                                campaign_name=campaign_name,
                                recipient_name=cust_name,
                                recipient_phone=phone_clean,
                                recipient_type='customer',
                                channel='whatsapp_blast',
                                status='failed',
                                message_snippet=wish_text[:300],
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                            )
                        except Exception:
                            pass

                except Exception as ex:
                    results["failed"] += 1
                    err_msg = str(ex)
                    results["details"].append({
                        "customer": cust_name,
                        "phone": phone_clean,
                        "occasion": occasion_type,
                        "status": "FAILED",
                        "error": err_msg,
                    })
                    try:
                        MarketingCampaignLog.objects.create(
                            template_key=template_key,
                            campaign_name=campaign_name,
                            recipient_name=cust_name,
                            recipient_phone=phone_clean,
                            recipient_type='customer',
                            channel='whatsapp_blast',
                            status='failed',
                            message_snippet=wish_text[:300],
                            sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.exception("Batch special wishes automated WhatsApp dispatch encountered an exception: %s", e)
            results["error"] = str(e)
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            clean_stale_locks()

    return results


def send_batch_irac_alerts_automated(
    loans,
    user=None,
    lang="both",
    delay_between_seconds: int = 3,
    headless: bool = True,
) -> dict:
    """
    Sends IRAC warning notices to a list of loans in a single persistent browser session.
    Reuses browser context across all messages for high efficiency.
    """
    from playwright.sync_api import sync_playwright
    import urllib.parse

    results = {
        "total": len(loans),
        "sent": 0,
        "failed": 0,
        "details": [],
    }

    if not loans:
        return results

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                **get_launch_context_options(headless=headless)
            )
            page = context.pages[0] if context.pages else context.new_page()

            # Pre-warm WhatsApp Web
            page.goto("https://web.whatsapp.com/", timeout=45000)
            time.sleep(5)

            from transactions.services_eod import classify_loan_irac
            from decimal import Decimal

            today = timezone.now().date() if hasattr(timezone, 'now') else datetime.date.today()

            for loan in loans:
                customer = loan.customer
                raw_phone = getattr(customer, 'phone', None) or getattr(customer, 'phone_number', None) or ""
                phone_clean = clean_phone_number(raw_phone)
                cust_name = getattr(customer, 'get_full_name', None)() if hasattr(customer, 'get_full_name') else f"{customer.first_name} {customer.last_name}" if customer else "N/A"

                from transactions.models import LoanWhatsAppLog

                if not phone_clean:
                    results["failed"] += 1
                    results["details"].append({
                        "loan_no": loan.loan_number,
                        "customer": cust_name,
                        "status": "FAILED",
                        "error": "No valid phone number in profile",
                    })
                    try:
                        LoanWhatsAppLog.objects.create(
                            loan=loan,
                            customer=customer,
                            recipient_phone=raw_phone or '',
                            notification_type='irac_alert',
                            status='failed',
                            error_message='No valid phone number in profile',
                            channel='automated_browser',
                            sent_by=user if user and user.is_authenticated else None,
                        )
                    except Exception:
                        pass
                    continue

                # Classify status & due amount
                irac_status, overdue_days, prov_pct, _ = classify_loan_irac(loan, as_of_date=today)
                irac_bucket = irac_status if irac_status in ['SMA_0', 'SMA_1', 'SMA_2', 'NPA_SUBSTANDARD', 'NPA_DOUBTFUL', 'NPA_LOSS'] else ('NPA_LOSS' if irac_status.startswith('NPA') else 'SMA_0')
                
                principal = loan.principal_amount or Decimal('0.00')
                accrued = loan.accrued_interest or Decimal('0.00')
                due_amount = principal + accrued

                # Render notice
                message_text = render_irac_alert_message(loan, bucket=irac_bucket, lang=lang)
                encoded_msg = urllib.parse.quote(message_text)
                send_url = f"https://web.whatsapp.com/send?phone={phone_clean}&text={encoded_msg}"

                try:
                    page.goto(send_url, timeout=35000)
                    time.sleep(2)

                    # Check for invalid number popup
                    invalid_modal = page.locator('div[data-animate-modal-popup="true"], div[role="dialog"], div[data-testid="popup-contents"]').filter(
                        has_text=re.compile(r'invalid|phone number shared via url', re.I)
                    ).first
                    if not invalid_modal.count() or not invalid_modal.is_visible():
                        invalid_modal = page.locator('text="Phone number shared via url is invalid", text="The phone number shared via url is invalid", text="URL is invalid", text="Phone number is invalid"').first

                    if invalid_modal.is_visible():
                        ok_btn = page.locator('div[data-animate-modal-popup="true"] button, div[role="dialog"] button, div[data-testid="popup-contents"] button, div[role="button"]:has-text("OK"), button:has-text("OK")').first
                        if ok_btn.is_visible():
                            try:
                                ok_btn.click()
                                time.sleep(1)
                            except Exception:
                                pass
                        results["failed"] += 1
                        results["details"].append({
                            "loan_no": loan.loan_number,
                            "customer": cust_name,
                            "phone": phone_clean,
                            "status": "SKIPPED",
                            "error": f"Not on WhatsApp: Phone +{phone_clean} is not registered on WhatsApp",
                        })
                        continue

                    # Look for send button or composer
                    sent_success = False
                    send_btn = page.locator('button[aria-label="Send"], button[aria-label="Send message"], span[data-icon="send"], span[data-icon="send-light"], button:has(span[data-icon="send"]), button[data-tab="11"]').first
                    if send_btn.is_visible():
                        try:
                            send_btn.click()
                            sent_success = True
                        except Exception:
                            pass

                    if not sent_success:
                        composer = page.locator('footer div[contenteditable="true"], div[role="textbox"][contenteditable="true"], div[contenteditable="true"][data-tab="10"], div[contenteditable="true"][data-tab="6"]').first
                        if composer.is_visible():
                            try:
                                composer.focus()
                                composer.press("Enter")
                                sent_success = True
                            except Exception:
                                pass

                    if sent_success:
                        time.sleep(delay_between_seconds)

                        # Record in database audit log
                        IRACAlertLog.objects.create(
                            loan=loan,
                            customer=customer,
                            irac_bucket=irac_bucket,
                            overdue_days=overdue_days,
                            overdue_amount=due_amount,
                            channel="WHATSAPP_AUTOMATED",
                            status="SENT",
                            message_sent=message_text,
                            sent_by=user if user and user.is_authenticated else None,
                        )

                        try:
                            LoanWhatsAppLog.objects.create(
                                loan=loan,
                                customer=customer,
                                recipient_phone=phone_clean,
                                notification_type=f"irac_{irac_bucket.lower()}",
                                status='sent',
                                message_content=message_text,
                                channel='automated_browser',
                                sent_by=user if user and user.is_authenticated else None,
                            )
                        except Exception:
                            pass

                        results["sent"] += 1
                        results["details"].append({
                            "loan_no": loan.loan_number,
                            "customer": cust_name,
                            "status": "SENT",
                            "phone": phone_clean,
                        })
                    else:
                        results["failed"] += 1
                        err_msg = "Could not locate send button / invalid contact"
                        results["details"].append({
                            "loan_no": loan.loan_number,
                            "customer": cust_name,
                            "status": "FAILED",
                            "error": err_msg,
                        })
                        try:
                            LoanWhatsAppLog.objects.create(
                                loan=loan,
                                customer=customer,
                                recipient_phone=phone_clean,
                                notification_type=f"irac_{irac_bucket.lower()}",
                                status='failed',
                                message_content=message_text,
                                error_message=err_msg,
                                channel='automated_browser',
                                sent_by=user if user and user.is_authenticated else None,
                            )
                        except Exception:
                            pass

                except Exception as ex:
                    results["failed"] += 1
                    results["details"].append({
                        "loan_no": loan.loan_number,
                        "customer": cust_name,
                        "status": "FAILED",
                        "error": str(ex),
                    })
                    try:
                        LoanWhatsAppLog.objects.create(
                            loan=loan,
                            customer=customer,
                            recipient_phone=phone_clean,
                            notification_type=f"irac_{irac_bucket.lower()}",
                            status='failed',
                            message_content=message_text,
                            error_message=str(ex),
                            channel='automated_browser',
                            sent_by=user if user and user.is_authenticated else None,
                        )
                    except Exception:
                        pass

            context.close()
        except Exception as e:
            logger.exception("Batch headless dispatch encountered an exception: %s", e)
            results["error"] = str(e)

    return results


def send_batch_loans_whatsapp_automated(
    loans,
    notification_type: str = "auto",
    custom_template: str = None,
    user=None,
    lang: str = None,
    delay_between_seconds: int = 3,
    headless: bool = True,
) -> dict:
    """
    Sends automated WhatsApp notifications to a list of loans in a single persistent browser session.
    Supports smart auto classification (overdue / reminder / demand notice), standard templates, or custom user templates.
    """
    from playwright.sync_api import sync_playwright
    import urllib.parse
    from transactions.services_whatsapp import build_smart_loan_whatsapp_message, normalize_phone_number, get_whatsapp_link

    results = {
        "total": len(loans),
        "sent": 0,
        "failed": 0,
        "details": [],
    }

    if not loans:
        return results

    clean_stale_locks()

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                **get_launch_context_options(headless=headless)
            )
            page = context.pages[0] if context.pages else context.new_page()

            # Pre-warm WhatsApp Web
            page.goto("https://web.whatsapp.com/", timeout=45000)
            time.sleep(4)

            # Check if WhatsApp Web is presenting QR code (unpaired session)
            if page.locator('canvas').is_visible() or page.locator('div[data-ref]').is_visible():
                context.close()
                results["error"] = "WhatsApp session is not paired yet. Please open 'Link WhatsApp' and scan the QR code first."
                from transactions.models import LoanWhatsAppLog
                for loan in loans:
                    c = getattr(loan, 'customer', None)
                    c_name = getattr(c, 'get_full_name', None)() if (c and hasattr(c, 'get_full_name')) else f"{getattr(c, 'first_name', '')} {getattr(c, 'last_name', '')}".strip() or "Valued Customer"
                    results["details"].append({
                        "loan_no": getattr(loan, 'loan_number', ''),
                        "customer": c_name,
                        "phone": getattr(c, 'phone', '') or '',
                        "status": "FAILED",
                        "error": "WhatsApp session is not paired. Please link device first.",
                    })
                    results["failed"] += 1
                    try:
                        LoanWhatsAppLog.objects.create(
                            loan=loan,
                            customer=c,
                            recipient_phone=getattr(c, 'phone', '') or '',
                            notification_type=notification_type or 'automated_notice',
                            status='failed',
                            error_message="WhatsApp session is not paired. Please link device first.",
                            channel='automated_browser',
                            sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
                        )
                    except Exception as l_err:
                        logger.warning("Could not create LoanWhatsAppLog for unpaired session: %s", l_err)
                return results

            from transactions.models import LoanWhatsAppLog

            for loan in loans:
                customer = getattr(loan, 'customer', None)
                raw_phone = getattr(customer, 'phone', None) or getattr(customer, 'phone_number', None) or ""
                phone_clean = clean_phone_number(raw_phone)
                cust_name = getattr(customer, 'get_full_name', None)() if (customer and hasattr(customer, 'get_full_name')) else f"{getattr(customer, 'first_name', '')} {getattr(customer, 'last_name', '')}".strip() or "Valued Customer"

                # Build notification text
                message_text = build_smart_loan_whatsapp_message(
                    loan=loan,
                    notification_type=notification_type,
                    custom_template=custom_template,
                    lang=lang,
                    request_user=user,
                )

                if not phone_clean or len(phone_clean) < 10:
                    results["failed"] += 1
                    results["details"].append({
                        "loan_no": getattr(loan, 'loan_number', ''),
                        "customer": cust_name,
                        "phone": raw_phone or "-",
                        "status": "FAILED",
                        "error": f"Invalid or missing phone number: '{raw_phone}'",
                    })
                    try:
                        LoanWhatsAppLog.objects.create(
                            loan=loan,
                            customer=customer,
                            recipient_phone=raw_phone or '',
                            notification_type=notification_type or 'automated_notice',
                            status='failed',
                            message_content=message_text,
                            error_message=f"Invalid or missing phone number: '{raw_phone}'",
                            channel='automated_browser',
                            sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
                        )
                    except Exception as l_err:
                        logger.warning("Could not log failed LoanWhatsAppLog: %s", l_err)
                    continue

                encoded_msg = urllib.parse.quote(message_text)
                send_url = f"https://web.whatsapp.com/send?phone={phone_clean}&text={encoded_msg}"

                try:
                    page.goto(send_url, timeout=35000)
                    time.sleep(3)

                    # Check for invalid number popup
                    if page.locator("text=Phone number shared via url is invalid").is_visible() or page.locator("text=URL is invalid").is_visible():
                        results["failed"] += 1
                        err_msg = f"Phone number +{phone_clean} is not registered on WhatsApp"
                        results["details"].append({
                            "loan_no": getattr(loan, 'loan_number', ''),
                            "customer": cust_name,
                            "phone": phone_clean,
                            "status": "FAILED",
                            "error": err_msg,
                        })
                        try:
                            LoanWhatsAppLog.objects.create(
                                loan=loan,
                                customer=customer,
                                recipient_phone=phone_clean,
                                notification_type=notification_type or 'automated_notice',
                                status='failed',
                                message_content=message_text,
                                error_message=err_msg,
                                channel='automated_browser',
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
                            )
                        except Exception as l_err:
                            logger.warning("Could not log failed LoanWhatsAppLog: %s", l_err)

                        try:
                            ok_btn = page.locator('button:has-text("OK"), div[role="button"]:has-text("OK")').first
                            if ok_btn.is_visible():
                                ok_btn.click()
                        except Exception:
                            pass
                        continue

                    # Look for Send button or composer
                    send_btn = page.locator('button[aria-label="Send"], span[data-icon="send"], button span[data-icon="send"], button[data-tab="11"]').first
                    sent_success = False

                    try:
                        send_btn.wait_for(state="visible", timeout=12000)
                        send_btn.click()
                        sent_success = True
                    except Exception:
                        composer = page.locator('div[contenteditable="true"][data-tab="10"], div[contenteditable="true"][data-tab="6"], div[role="textbox"][contenteditable="true"]').first
                        if composer.is_visible():
                            composer.focus()
                            composer.press("Enter")
                            sent_success = True

                    if sent_success:
                        time.sleep(delay_between_seconds)

                        # Record in database audit logs
                        try:
                            LoanWhatsAppLog.objects.create(
                                loan=loan,
                                customer=customer,
                                recipient_phone=phone_clean,
                                notification_type=notification_type or 'automated_notice',
                                status='sent',
                                message_content=message_text,
                                channel='automated_browser',
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
                            )
                        except Exception as log_err:
                            logger.warning("Could not create LoanWhatsAppLog: %s", log_err)

                        try:
                            from transactions.services_whatsapp import _compute_days_left, _get_total_payable
                            days_left, is_overdue = _compute_days_left(loan)
                            overdue_days = abs(days_left) if (is_overdue and days_left is not None) else 0
                            tot_due, _ = _get_total_payable(loan)
                            irac_bucket = 'SMA_0'
                            if overdue_days > 90:
                                irac_bucket = 'NPA_LOSS'
                            elif overdue_days > 60:
                                irac_bucket = 'SMA_2'
                            elif overdue_days > 30:
                                irac_bucket = 'SMA_1'

                            IRACAlertLog.objects.create(
                                loan=loan,
                                customer=customer,
                                irac_bucket=irac_bucket,
                                overdue_days=overdue_days,
                                overdue_amount=tot_due,
                                channel="whatsapp_web",
                                status="sent",
                                message_sent=message_text,
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
                            )
                        except Exception as log_err:
                            logger.warning("Could not create IRACAlertLog: %s", log_err)

                        results["sent"] += 1
                        results["details"].append({
                            "loan_no": getattr(loan, 'loan_number', ''),
                            "customer": cust_name,
                            "phone": phone_clean,
                            "status": "SENT",
                        })
                    else:
                        results["failed"] += 1
                        err_msg = "Could not locate WhatsApp send button / number unverified"
                        results["details"].append({
                            "loan_no": getattr(loan, 'loan_number', ''),
                            "customer": cust_name,
                            "phone": phone_clean,
                            "status": "FAILED",
                            "error": err_msg,
                        })
                        try:
                            LoanWhatsAppLog.objects.create(
                                loan=loan,
                                customer=customer,
                                recipient_phone=phone_clean,
                                notification_type=notification_type or 'automated_notice',
                                status='failed',
                                message_content=message_text,
                                error_message=err_msg,
                                channel='automated_browser',
                                sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
                            )
                        except Exception as log_err:
                            logger.warning("Could not create LoanWhatsAppLog failed record: %s", log_err)

                except Exception as ex:
                    results["failed"] += 1
                    err_msg = str(ex)
                    results["details"].append({
                        "loan_no": getattr(loan, 'loan_number', ''),
                        "customer": cust_name,
                        "phone": phone_clean,
                        "status": "FAILED",
                        "error": err_msg,
                    })
                    try:
                        LoanWhatsAppLog.objects.create(
                            loan=loan,
                            customer=customer,
                            recipient_phone=phone_clean,
                            notification_type=notification_type or 'automated_notice',
                            status='failed',
                            message_content=message_text,
                            error_message=err_msg,
                            channel='automated_browser',
                            sent_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
                        )
                    except Exception as log_err:
                        logger.warning("Could not create LoanWhatsAppLog exception record: %s", log_err)

            context.close()
        except Exception as e:
            logger.exception("Batch loan automated WhatsApp dispatch encountered an exception: %s", e)
            results["error"] = str(e)

    return results

