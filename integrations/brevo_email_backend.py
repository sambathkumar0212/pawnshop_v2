"""
integrations/brevo_email_backend.py
Custom Django Email Backend for sending emails via Brevo (Sendinblue) HTTP API v3.

Bypasses cloud provider SMTP egress port blocks (such as Render Free Tier blocking
outbound ports 25, 465, and 587) by sending transactional emails via HTTPS (port 443).
"""

import base64
import json
import logging
from email.utils import parseaddr
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class BrevoApiEmailBackend(BaseEmailBackend):
    """
    Django Email Backend that sends transactional emails via the Brevo v3 HTTP REST API.
    Endpoint: POST https://api.brevo.com/v3/smtp/email
    """

    def __init__(self, api_key=None, api_url=None, timeout=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = (api_key or getattr(settings, 'BREVO_API_KEY', '') or '').strip()
        self.api_url = api_url or getattr(settings, 'BREVO_API_URL', 'https://api.brevo.com/v3/smtp/email')
        self.timeout = timeout or getattr(settings, 'EMAIL_TIMEOUT', 15)
        self.default_from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@myapp.com')

    def send_messages(self, email_messages):
        """
        Send one or more EmailMessage / EmailMultiAlternatives instances via Brevo HTTP API.
        Returns the number of messages successfully delivered to the API.
        """
        if not email_messages:
            return 0

        if not self.api_key:
            err_msg = (
                "[BrevoAPI] BREVO_API_KEY is not configured in settings/environment. "
                "Please set BREVO_API_KEY in your environment to send emails via Brevo HTTP API."
            )
            logger.error(err_msg)
            if not self.fail_silently:
                raise ValueError(err_msg)
            return 0

        num_sent = 0
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

        for message in email_messages:
            try:
                payload = self._build_payload(message)
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=self.timeout
                )

                if 200 <= response.status_code < 300:
                    resp_data = {}
                    try:
                        resp_data = response.json()
                    except Exception:
                        pass
                    msg_id = resp_data.get('messageId', 'ok')
                    logger.info(
                        "[BrevoAPI] Email dispatched successfully. MessageId: %s | Subject: '%s' | To: %s",
                        msg_id, message.subject, [r['email'] for r in payload.get('to', [])]
                    )
                    num_sent += 1
                else:
                    err_msg = (
                        f"[BrevoAPI] API error (HTTP {response.status_code}): {response.text} | "
                        f"Subject: '{message.subject}' | To: {[r['email'] for r in payload.get('to', [])]}"
                    )
                    logger.error(err_msg)
                    if not self.fail_silently:
                        raise RuntimeError(err_msg)

            except Exception as exc:
                logger.error("[BrevoAPI] Exception dispatching email '%s': %s", getattr(message, 'subject', 'N/A'), exc, exc_info=True)
                if not self.fail_silently:
                    raise

        return num_sent

    def _parse_recipient(self, addr_str):
        name, email = parseaddr(str(addr_str or '').strip())
        res = {"email": email}
        if name:
            res["name"] = name
        return res

    def _build_payload(self, message):
        # 1. Sender
        from_header = message.from_email or self.default_from_email
        from_name, from_email = parseaddr(from_header)
        sender = {"email": from_email or self.default_from_email}
        if from_name:
            sender["name"] = from_name

        # 2. Recipients
        to_list = [self._parse_recipient(a) for a in message.to if a]
        if not to_list:
            raise ValueError(f"EmailMessage '{message.subject}' has no recipients in 'to'.")

        payload = {
            "sender": sender,
            "to": to_list,
            "subject": message.subject or "(No Subject)",
        }

        if getattr(message, 'cc', None):
            cc_list = [self._parse_recipient(a) for a in message.cc if a]
            if cc_list:
                payload["cc"] = cc_list

        if getattr(message, 'bcc', None):
            bcc_list = [self._parse_recipient(a) for a in message.bcc if a]
            if bcc_list:
                payload["bcc"] = bcc_list

        if getattr(message, 'reply_to', None):
            _, reply_email = parseaddr(message.reply_to[0])
            if reply_email:
                payload["replyTo"] = {"email": reply_email}

        # 3. Content (HTML vs Plain text)
        html_content = None
        text_content = message.body or ""

        if getattr(message, 'content_subtype', '') == 'html':
            html_content = message.body
        else:
            for content, mimetype in getattr(message, 'alternatives', []):
                if mimetype == 'text/html':
                    html_content = content
                    break

        if html_content:
            payload["htmlContent"] = html_content
        if text_content:
            payload["textContent"] = text_content
        if not html_content and not text_content:
            payload["textContent"] = " "

        # 4. Attachments
        if getattr(message, 'attachments', None):
            formatted_attachments = self._format_attachments(message.attachments)
            if formatted_attachments:
                payload["attachment"] = formatted_attachments

        return payload

    def _format_attachments(self, attachments):
        formatted = []
        for attachment in attachments:
            try:
                if isinstance(attachment, tuple):
                    name = str(attachment[0])
                    raw_content = attachment[1]
                    if isinstance(raw_content, str):
                        content_bytes = raw_content.encode('utf-8')
                    elif hasattr(raw_content, 'read'):
                        content_bytes = raw_content.read()
                    else:
                        content_bytes = bytes(raw_content)
                    b64_content = base64.b64encode(content_bytes).decode('ascii')
                    formatted.append({"name": name, "content": b64_content})
                elif hasattr(attachment, 'get_payload'):
                    name = attachment.get_filename() or 'attachment'
                    payload = attachment.get_payload(decode=True)
                    if payload:
                        b64_content = base64.b64encode(payload).decode('ascii')
                        formatted.append({"name": name, "content": b64_content})
            except Exception as e:
                logger.warning("[BrevoAPI] Could not format attachment: %s", e)
        return formatted
