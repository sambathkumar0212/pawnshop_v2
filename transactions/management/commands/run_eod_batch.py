from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from transactions.services_eod import run_daily_eod_batch
from branches.models import Branch


class Command(BaseCommand):
    help = "Run Automated End-of-Day (EOD) Daily Interest Accrual & RBI IRAC NPA Tagging Batch"

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Execution date in YYYY-MM-DD format (default: today)'
        )
        parser.add_argument(
            '--branch',
            type=int,
            help='Specific Branch ID to process (default: all branches)'
        )
        parser.add_argument(
            '--no-gl',
            action='store_true',
            help='Skip automated General Ledger journal voucher posting'
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        if date_str:
            try:
                exec_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date format: {date_str}. Use YYYY-MM-DD."))
                return
        else:
            exec_date = timezone.now().date()

        branch_id = options.get('branch')
        branch = None
        if branch_id:
            try:
                branch = Branch.objects.get(pk=branch_id)
            except Branch.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Branch with ID {branch_id} not found."))
                return

        post_gl = not options.get('no_gl')

        self.stdout.write(self.style.NOTICE(
            f"=== Starting EOD Batch for Date: {exec_date.strftime('%d-%b-%Y')} "
            f"[{branch.name if branch else 'ALL BRANCHES'}] ==="
        ))

        try:
            exec_log = run_daily_eod_batch(date=exec_date, branch=branch, user=None, post_gl=post_gl)
            
            self.stdout.write(self.style.SUCCESS(
                f"\n[SUCCESS] EOD Batch Run Completed Successfully!\n"
                f"  - Total Loans Processed:       {exec_log.total_loans_processed}\n"
                f"  - Total Daily Interest Accrued: Rs. {exec_log.total_daily_interest_accrued:,.2f}\n"
                f"  - Standard Assets:             {exec_log.standard_count}\n"
                f"  - SMA-0 (1-30 Days Overdue):   {exec_log.sma0_count}\n"
                f"  - SMA-1 (31-60 Days Overdue):  {exec_log.sma1_count}\n"
                f"  - SMA-2 (61-90 Days Overdue):  {exec_log.sma2_count}\n"
                f"  - NPA Substandard (>90 Days):  {exec_log.npa_count}\n"
            ))
            if exec_log.gl_journal_entry:
                self.stdout.write(self.style.SUCCESS(
                    f"  - GL Journal Voucher Created:  #{exec_log.gl_journal_entry.entry_number}\n"
                ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"\n[FAILED] EOD Batch execution encountered error: {e}"))
            raise e
