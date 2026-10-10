from django.core.management.base import BaseCommand
from schemes.models import DailyGoldRate

class Command(BaseCommand):
    help = "Sync today's gold rate with live market API feeds (GoodReturns Chennai / Bullion Spot)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help="Force sync even if today's rate is already recorded"
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        self.stdout.write(self.style.NOTICE("Fetching live market gold rates..."))
        rate = DailyGoldRate.sync_today_rate(force=force)
        if rate:
            self.stdout.write(self.style.SUCCESS(
                f"[SUCCESS] Gold rates updated for {rate.date}: "
                f"22K: Rs {rate.rate_22k_per_gram:,.2f}/g | "
                f"24K: Rs {rate.rate_24k_per_gram:,.2f}/g | "
                f"RBI LTV Cap: {rate.maximum_ltv_percentage}% "
                f"[{rate.notes}]"
            ))
        else:
            self.stdout.write(self.style.ERROR("[ERROR] Failed to fetch live gold rate from all providers."))
