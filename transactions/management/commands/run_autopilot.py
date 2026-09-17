from django.core.management.base import BaseCommand
from transactions.services_autopilot import (
    get_or_create_autopilot_config,
    run_autopilot_cycle,
    run_pillar_2_whatsapp_collections,
    run_pillar_3_ltv_surveillance,
    run_pillar_4_retention_marketing,
    run_pillar_5_owner_digest,
)


class Command(BaseCommand):
    help = "Run 24/7 Autopilot Automation Orchestrator (Pillars 2, 3, 4, 5)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--pillar',
            type=str,
            help='Specific pillar to execute: 2 (WhatsApp Collections), 3 (LTV Risk), 4 (Marketing), 5 (Owner Digest), or all (default)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate execution and print eligible targets without dispatching actual WhatsApp messages'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force execution even if Autopilot Master Switch is OFF or outside safe time window'
        )

    def handle(self, *args, **options):
        pillar = str(options.get('pillar') or 'all').strip().lower()
        dry_run = bool(options.get('dry_run'))
        force = bool(options.get('force'))

        config = get_or_create_autopilot_config()

        self.stdout.write(self.style.NOTICE(
            f"=== Starting Autopilot Execution Engine [Pillar: {pillar.upper()}, Dry-Run: {dry_run}, Force: {force}] ==="
        ))

        if not config.is_enabled and not force:
            self.stdout.write(self.style.WARNING("Autopilot Master Switch is OFF. Use --force to override."))
            return

        def _safe_str(val):
            return str(val).encode('ascii', errors='replace').decode('ascii')

        if pillar in ('2', 'pillar_2', 'collections'):
            res = run_pillar_2_whatsapp_collections(config=config, dry_run=dry_run, forced=force)
            self.stdout.write(self.style.SUCCESS(f"Pillar 2 Result: {_safe_str(res)}"))

        elif pillar in ('3', 'pillar_3', 'ltv'):
            res = run_pillar_3_ltv_surveillance(config=config, dry_run=dry_run, forced=force)
            self.stdout.write(self.style.SUCCESS(f"Pillar 3 Result: {_safe_str(res)}"))

        elif pillar in ('4', 'pillar_4', 'marketing', 'retention'):
            res = run_pillar_4_retention_marketing(config=config, dry_run=dry_run, forced=force)
            self.stdout.write(self.style.SUCCESS(f"Pillar 4 Result: {_safe_str(res)}"))

        elif pillar in ('5', 'pillar_5', 'digest', 'owner'):
            res = run_pillar_5_owner_digest(config=config, dry_run=dry_run, forced=force)
            self.stdout.write(self.style.SUCCESS(f"Pillar 5 Result: {_safe_str(res)}"))

        else:
            res = run_autopilot_cycle(forced=force, dry_run=dry_run)
            self.stdout.write(self.style.SUCCESS(f"Full Autopilot Cycle Result: {_safe_str(res)}"))
