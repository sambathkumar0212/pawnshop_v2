from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Send due-date reminder emails to borrowers whose loan is due in N days. '
        'Default is 3 days. Run daily via cron or the EOD batch.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='Number of days before the due date to trigger the reminder (default: 3).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='List matching loans without sending emails.',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        today = timezone.now().date()
        target_date = today + timedelta(days=days)

        from transactions.models import Loan

        loans = Loan.objects.filter(
            status='active',
            due_date=target_date,
        ).select_related('customer', 'branch')

        count = loans.count()
        self.stdout.write(
            f"Found {count} active loan(s) due on {target_date} ({days} days from today)."
        )

        if dry_run:
            for loan in loans:
                email = getattr(loan.customer, 'email', None)
                self.stdout.write(
                    f"  [DRY RUN] Loan {loan.loan_number} | Customer: {loan.customer} | Email: {email or 'N/A'}"
                )
            return

        from transactions.services_email import send_due_date_reminder_email

        sent = 0
        skipped = 0
        for loan in loans:
            email = getattr(loan.customer, 'email', None)
            if not email:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(f"  Skipped {loan.loan_number}: no customer email.")
                )
                continue
            try:
                send_due_date_reminder_email(loan, days_left=days)
                sent += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  Sent reminder for {loan.loan_number} to {email}")
                )
            except Exception as exc:
                skipped += 1
                logger.warning("Reminder email failed for %s: %s", loan.loan_number, exc)
                self.stdout.write(
                    self.style.ERROR(f"  FAILED {loan.loan_number}: {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Sent: {sent}, Skipped (no email / error): {skipped}."
            )
        )
