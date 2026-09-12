"""
Management command to pair WhatsApp Web session once.
Opens a browser window and waits for QR scan from your phone's WhatsApp -> Linked Devices.
"""

from django.core.management.base import BaseCommand
from transactions.services_whatsapp_automator import pair_whatsapp_interactive, is_whatsapp_paired


class Command(BaseCommand):
    help = "Pair WhatsApp Web session once by scanning QR code from phone (Linked Devices)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=120,
            help="Timeout in seconds to wait for QR code scan (default: 120)",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        self.stdout.write(self.style.NOTICE("=================================================="))
        self.stdout.write(self.style.NOTICE("      WHATSAPP WEB ONE-TIME SESSION PAIRING       "))
        self.stdout.write(self.style.NOTICE("=================================================="))
        self.stdout.write("1. A Chromium browser window will open.")
        self.stdout.write("2. Open WhatsApp on your phone -> Settings/Menu -> Linked Devices.")
        self.stdout.write("3. Scan the QR code displayed on the screen.")
        self.stdout.write("4. Once scanned, this session is saved permanently for automated dispatch.\n")

        self.stdout.write(self.style.WARNING(f"[*] Opening browser... (Timeout: {timeout}s)"))
        res = pair_whatsapp_interactive(timeout_seconds=timeout)

        if res.get("success"):
            self.stdout.write(self.style.SUCCESS("[+] " + res["message"]))
            self.stdout.write(self.style.SUCCESS("[+] You can now use automated 100% hands-free WhatsApp alert dispatch!"))
        else:
            self.stdout.write(self.style.ERROR("[-] " + res["message"]))
