from django.core.management.base import BaseCommand
from pathlib import Path
import polib
import sys


class Command(BaseCommand):
    help = 'Compile .po files to .mo using polib (works without GNU gettext)'

    def handle(self, *args, **options):
        project_root = Path(__file__).resolve().parents[3]
        locale_dir = project_root / 'locale'
        if not locale_dir.exists():
            self.stdout.write(self.style.WARNING(f'No locale directory found at {locale_dir}'))
            return

        found = False
        for po_path in locale_dir.rglob('*.po'):
            found = True
            try:
                mo_path = po_path.with_suffix('.mo')
                self.stdout.write(f'Compiling {po_path} -> {mo_path}')
                po = polib.pofile(str(po_path))
                po.save_as_mofile(str(mo_path))
            except Exception as e:
                self.stderr.write(f'Failed to compile {po_path}: {e}')
        if not found:
            self.stdout.write(self.style.WARNING('No .po files found to compile.'))
        else:
            self.stdout.write(self.style.SUCCESS('Compiled .po files to .mo successfully.'))
