"""
Services for Headless / Automated WhatsApp Message Dispatch using Playwright.
Persists browser profile in `.whatsapp_user_data/` so QR code is scanned once.
"""

import os
import re
import time
import logging
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


def is_whatsapp_paired() -> bool:
    """Checks if a verified paired session marker exists."""
    session_path = Path(settings.BASE_DIR) / ".whatsapp_user_data"
    marker = session_path / ".session_paired"
    return marker.exists()


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
            return False
    return True


def pair_whatsapp_interactive(timeout_seconds: int = 120) -> dict:
    """
    Launches a visible Chromium window for the user to scan the WhatsApp Web QR code once.
    Saves the user data directory persistently for all future background runs.
    """
    from playwright.sync_api import sync_playwright

    logger.info("Opening WhatsApp Web for one-time pairing in %s", get_session_dir())
    clean_stale_locks()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            **get_launch_context_options(headless=False)
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://web.whatsapp.com/", timeout=60000)

        # Bring window to front
        try:
            page.bring_to_front()
        except Exception:
            pass

        logged_in = False
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                # Check multiple indicators of a successful WhatsApp Web login
                if (
                    page.locator('div[contenteditable="true"][data-tab="3"]').is_visible()
                    or page.locator('div[aria-label="Chat list"]').is_visible()
                    or page.locator('span[data-icon="chat"]').is_visible()
                    or page.locator('header').is_visible()
                    or page.locator('#pane-side').is_visible()
                    or page.locator('div[role="textbox"]').is_visible()
                ):
                    logged_in = True
                    time.sleep(6)  # Allow storage and IndexedDB keys to settle completely
                    break
            except Exception:
                pass
            time.sleep(1)

        context.close()

        if logged_in:
            marker = Path(get_session_dir()) / ".session_paired"
            try:
                marker.write_text("PAIRED", encoding="utf-8")
            except Exception:
                pass
            return {"success": True, "message": "WhatsApp session paired successfully!"}
        return {
            "success": False,
            "message": f"Pairing timed out after {timeout_seconds} seconds. Please scan the QR code before timeout.",
        }


def get_whatsapp_qr_image_base64() -> dict:
    """
    Checks session authentication status and returns pairing status.
    """
    if is_whatsapp_paired():
        return {"status": "authenticated", "message": "WhatsApp is already linked!"}
    return {
        "status": "unpaired",
        "message": "Click 'Open Live QR Pairing Window' to scan the live QR code on screen."
    }



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
                    time.sleep(3)

                    # Click send button
                    send_btn = page.locator('button[aria-label="Send"], span[data-icon="send"], button span[data-icon="send"]').first
                    sent_success = False

                    try:
                        send_btn.wait_for(state="visible", timeout=12000)
                        send_btn.click()
                        sent_success = True
                    except Exception:
                        composer = page.locator('div[contenteditable="true"][data-tab="10"]').first
                        if composer.is_visible():
                            composer.focus()
                            composer.press("Enter")
                            sent_success = True

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

