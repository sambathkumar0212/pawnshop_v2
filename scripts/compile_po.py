import polib
from pathlib import Path

locale_dir = Path(r"D:\pawn\pawnshop\locale")
if not locale_dir.exists():
    print(f"Locale dir not found: {locale_dir}")
    raise SystemExit(1)

count = 0
for po_path in locale_dir.rglob('*.po'):
    mo_path = po_path.with_suffix('.mo')
    print(f"Compiling {po_path} -> {mo_path}")
    po = polib.pofile(str(po_path))
    po.save_as_mofile(str(mo_path))
    count += 1

print(f"Compiled {count} .po files")
