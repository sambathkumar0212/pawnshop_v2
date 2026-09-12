"""
transactions/management/commands/send_irac_alerts.py
Management command to scan all active loans for RBI IRAC asset classification delinquency,
generate tiered risk alert notices (SMA-0, SMA-1, SMA-2 Pre-NPA, NPA Recovery, Auction Warning),
and record/dispatch automated alerts.
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from branches.models import Branch
from transactions.models import Loan
from transactions.services_irac import (
    get_delinquency_watchlist,
    log_irac_alert,
    render_irac_alert_message,
)


class Command(BaseCommand):
    help = "Scans active loans, classifies RBI IRAC status, and dispatches/logs risk alerts."

    def add_arguments(self, parser):
        parser.add_argument(
            '--branch',
            type=int,
            help='Branch ID to filter loans (optional, defaults to enterprise-wide)'
        )
        parser.add_argument(
            '--bucket',
            type=str,
            default='ALL_OVERDUE',
            help='Filter specific risk bucket (SMA_0, SMA_1, SMA_2, NPA, ALL_OVERDUE)'
        )
        parser.add_argument(
            '--channel',
            type=str,
            default='whatsapp_web',
            help='Notification channel (whatsapp_web, pywhatkit, sms)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview risk alerts without creating log records'
        )
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Dispatch messages 100% automatically via background headless Playwright automation'
        )
        parser.add_argument(
            '--lang',
            type=str,
            default='ta',
            help='Alert language (ta for Tamil, en for English, both for bilingual)'
        )

    def handle(self, *args, **options):
        branch_id = options.get('branch')
        bucket_filter = options.get('bucket', 'ALL_OVERDUE')
        channel = options.get('channel', 'whatsapp_web')
        dry_run = options.get('dry_run', False)
        lang = options.get('lang', 'ta')
        use_tamil = (lang == 'ta')

        today = timezone.now().date()
        self.stdout.write(self.style.NOTICE(
            f"[*] Scanning loan portfolio for IRAC Delinquency as of {today.strftime('%d-%b-%Y')}..."
        ))

        watchlist, stats = get_delinquency_watchlist(
            branch_id=branch_id,
            bucket_filter=bucket_filter,
            use_tamil=use_tamil
        )

        self.stdout.write(self.style.SUCCESS(
            f"[+] Portfolio Summary: {stats['total_overdue_loans']} Overdue Loans | "
            f"Principal at Risk: Rs. {stats['total_overdue_principal']:,.2f} | "
            f"Provisioning Required: Rs. {stats['total_provisioning_required']:,.2f}"
        ))
        self.stdout.write(
            f"   - SMA-0 (1-30d): {stats['sma0_count']} | "
            f"- SMA-1 (31-60d): {stats['sma1_count']} | "
            f"- SMA-2 (61-90d): {stats['sma2_count']} | "
            f"- NPA (>90d): {stats['npa_count']}"
        )

        if not watchlist:
            self.stdout.write(self.style.SUCCESS("[+] No delinquent accounts found for the specified filter."))
            return

        auto_send = options.get('auto', False)

        if auto_send and not dry_run:
            from transactions.services_whatsapp_automator import send_batch_irac_alerts_automated, is_whatsapp_paired
            if not is_whatsapp_paired():
                self.stdout.write(self.style.ERROR(
                    "[-] WhatsApp session is not paired yet! Please run 'python manage.py setup_whatsapp_session' first."
                ))
                return

            self.stdout.write(self.style.NOTICE(f"[*] Starting 100% Automated Headless WhatsApp Dispatch for {len(watchlist)} accounts..."))
            loans = [item['loan'] for item in watchlist]
            res = send_batch_irac_alerts_automated(loans=loans, user=None, lang=lang, delay_between_seconds=3, headless=True)
            self.stdout.write(self.style.SUCCESS(
                f"\n[+] Automated Dispatch Finished: {res['sent']} Sent Successfully | {res['failed']} Failed."
            ))
            return

        logged_count = 0
        for item in watchlist:
            loan = item['loan']
            bucket = item['alert_bucket']
            overdue_days = item['overdue_days']
            msg = item['alert_message']
            cust_name = item['customer_name']
            cust_phone = item['customer_phone']

            if dry_run:
                self.stdout.write(
                    f"   [DRY-RUN] Loan #{loan.loan_number} | {cust_name} ({cust_phone}) | "
                    f"Bucket: {bucket} ({overdue_days}d overdue) | Due: Rs. {item['total_due']:,.2f}"
                )
            else:
                log_irac_alert(
                    loan=loan,
                    bucket=bucket,
                    channel=channel,
                    status='sent',
                    message_text=msg,
                    overdue_days=overdue_days,
                    overdue_amount=item['total_due'],
                    user=None
                )
                logged_count += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\n[DRY RUN COMPLETE] {len(watchlist)} alerts simulated."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n[+] Successfully processed & logged {logged_count} IRAC risk alerts."))
