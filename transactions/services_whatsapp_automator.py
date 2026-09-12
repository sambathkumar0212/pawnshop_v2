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


def get_session_dir():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return str(SESSION_DIR)


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
    """Checks if a saved WhatsApp Web session exists."""
    session_path = Path(settings.BASE_DIR) / ".whatsapp_user_data"
    if not session_path.exists():
        return False
    # Check if storage state / local storage directory is non-empty
    subdirs = list(session_path.glob("*"))
    return len(subdirs) > 3


def pair_whatsapp_interactive(timeout_seconds: int = 120) -> dict:
    """
    Launches a visible Chromium window for the user to scan the WhatsApp Web QR code once.
    Saves the user data directory persistently for all future background runs.
    """
    from playwright.sync_api import sync_playwright

    user_data_dir = get_session_dir()
    logger.info("Opening WhatsApp Web for one-time pairing in %s", user_data_dir)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
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
                if (
                    page.locator('div[contenteditable="true"][data-tab="3"]').is_visible()
                    or page.locator('div[aria-label="Chat list"]').is_visible()
                    or page.locator('span[data-icon="chat"]').is_visible()
                    or page.locator('header').is_visible()
                ):
                    logged_in = True
                    time.sleep(4)  # Allow storage to settle
                    break
            except Exception:
                pass
            time.sleep(1)

        context.close()

        if logged_in:
            return {"success": True, "message": "WhatsApp session paired successfully!"}
        return {
            "success": False,
            "message": f"Pairing timed out after {timeout_seconds} seconds. Please scan the QR code before timeout.",
        }


def get_whatsapp_qr_image_base64() -> dict:
    """
    Launches browser in headless mode, opens WhatsApp Web, captures the QR code canvas as base64 image,
    and checks if already logged in.
    """
    import base64
    from playwright.sync_api import sync_playwright

    user_data_dir = get_session_dir()

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://web.whatsapp.com/", timeout=45000)

            # Wait up to 15s for either login or QR canvas
            for _ in range(15):
                # 1. Check if already logged in
                if (
                    page.locator('div[contenteditable="true"][data-tab="3"]').is_visible()
                    or page.locator('div[aria-label="Chat list"]').is_visible()
                    or page.locator('span[data-icon="chat"]').is_visible()
                    or page.locator('header').is_visible()
                ):
                    context.close()
                    return {"status": "authenticated", "message": "WhatsApp is already linked!"}

                # 2. Check for QR code canvas
                canvas = page.locator('canvas').first
                if canvas.is_visible():
                    screenshot_bytes = canvas.screenshot()
                    b64_str = base64.b64encode(screenshot_bytes).decode("utf-8")
                    context.close()
                    return {
                        "status": "qr_ready",
                        "qr_image": f"data:image/png;base64,{b64_str}",
                        "message": "Scan this QR code from WhatsApp > Linked Devices."
                    }

                time.sleep(1)

            # If canvas not found directly, take screenshot of center area
            screenshot_bytes = page.screenshot()
            b64_str = base64.b64encode(screenshot_bytes).decode("utf-8")
            context.close()
            return {
                "status": "qr_ready",
                "qr_image": f"data:image/png;base64,{b64_str}",
                "message": "Scan the QR code displayed on screen."
            }
        except Exception as e:
            logger.exception("Error capturing WhatsApp QR code: %s", e)
            return {"status": "error", "message": str(e)}



def send_whatsapp_message_headless(phone: str, message: str, headless: bool = True) -> dict:
    """
    Dispatches a single message headlessly using the persistent session.
    """
    from playwright.sync_api import sync_playwright

    phone_clean = clean_phone_number(phone)
    if not phone_clean or len(phone_clean) < 10:
        return {"success": False, "error": f"Invalid phone number: {phone}"}

    user_data_dir = get_session_dir()

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            page = context.pages[0] if context.pages else context.new_page()

            # Encode message into WhatsApp Web send URL
            import urllib.parse
            encoded_msg = urllib.parse.quote(message)
            send_url = f"https://web.whatsapp.com/send?phone={phone_clean}&text={encoded_msg}"

            page.goto(send_url, timeout=45000)

            # Wait for either the chat composer or invalid number dialog
            time.sleep(4)  # Initial wait for chat to load

            # Look for the Send button or composer
            send_btn = page.locator('button[aria-label="Send"], span[data-icon="send"], button span[data-icon="send"]').first

            # Wait up to 15 seconds for composer or send button
            try:
                send_btn.wait_for(state="visible", timeout=15000)
                send_btn.click()
                time.sleep(2)  # Wait for message dispatch animation
                context.close()
                return {"success": True, "phone": phone_clean}
            except Exception:
                # If send button not found, try pressing Enter in the composer
                composer = page.locator('div[contenteditable="true"][data-tab="10"]').first
                if composer.is_visible():
                    composer.focus()
                    composer.press("Enter")
                    time.sleep(2)
                    context.close()
                    return {"success": True, "phone": phone_clean}

                # Check if invalid number dialog popped up
                if page.locator("text=Phone number shared via url is invalid").is_visible():
                    context.close()
                    return {"success": False, "error": f"Phone number {phone_clean} is not registered on WhatsApp"}

                context.close()
                return {"success": False, "error": "Timed out waiting for WhatsApp composer/send button"}

        except Exception as e:
            logger.exception("Error in headless WhatsApp dispatch: %s", e)
            return {"success": False, "error": str(e)}


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

    user_data_dir = get_session_dir()
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
                user_data_dir=user_data_dir,
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
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

                if not phone_clean:
                    results["failed"] += 1
                    results["details"].append({
                        "loan_no": loan.loan_number,
                        "customer": cust_name,
                        "status": "FAILED",
                        "error": "No valid phone number in profile",
                    })
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

                        results["sent"] += 1
                        results["details"].append({
                            "loan_no": loan.loan_number,
                            "customer": cust_name,
                            "status": "SENT",
                            "phone": phone_clean,
                        })
                    else:
                        results["failed"] += 1
                        results["details"].append({
                            "loan_no": loan.loan_number,
                            "customer": cust_name,
                            "status": "FAILED",
                            "error": "Could not locate send button / invalid contact",
                        })

                except Exception as ex:
                    results["failed"] += 1
                    results["details"].append({
                        "loan_no": loan.loan_number,
                        "customer": cust_name,
                        "status": "FAILED",
                        "error": str(ex),
                    })

            context.close()
        except Exception as e:
            logger.exception("Batch headless dispatch encountered an exception: %s", e)
            results["error"] = str(e)

    return results
