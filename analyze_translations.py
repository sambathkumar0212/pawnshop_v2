#!/usr/bin/env python
"""Analyze translation coverage"""
import os
import re
from pathlib import Path
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

base_dir = Path(__file__).parent

print("=" * 60)
print("TRANSLATION COVERAGE ANALYSIS")
print("=" * 60)

# Find all template files
template_dirs = [
    base_dir / 'templates',
]

# Add app-specific template dirs
for app_dir in base_dir.glob('*/templates'):
    template_dirs.append(app_dir)

all_trans_strings = set()

# Find all {% trans %}, {% blocktrans %}, and translation strings
trans_patterns = [
    r'{%\s*trans\s+"([^"]+)"\s*%}',  # {% trans "text" %}
    r"{%\s*trans\s+'([^']+)'\s*%}",  # {% trans 'text' %}
    r'{%\s*blocktrans\s*%}(.+?){%\s*endblocktrans\s*%}',  # {% blocktrans %}...{% endblocktrans %}
    r'gettext\s*\(\s*["\']([^"\']+)["\']\s*\)',  # gettext("text")
]

print("\n[1] Scanning templates for translatable strings...")

for template_dir in template_dirs:
    if not template_dir.exists():
        continue
    
    for template_file in template_dir.rglob('*.html'):
        with open(template_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        for pattern in trans_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                # Clean up match
                text = match.strip() if isinstance(match, str) else ''.join(match).strip()
                if text and len(text) > 0:
                    all_trans_strings.add(text)

print(f"  Found {len(all_trans_strings)} unique translatable strings in templates")

# Read .po file to find translated strings
po_file = base_dir / 'locale' / 'ta' / 'LC_MESSAGES' / 'django.po'
translated_strings = set()

if po_file.exists():
    print(f"\n[2] Reading translations from {po_file.relative_to(base_dir)}...")
    
    with open(po_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all msgid entries
    msgid_pattern = r'msgid "([^"]*)"'
    for match in re.finditer(msgid_pattern, content):
        text = match.group(1)
        if text and len(text) > 0:
            translated_strings.add(text)
    
    print(f"  Found {len(translated_strings)} strings in translation file")
else:
    print(f"  ✗ Translation file not found: {po_file}")

# Compare
print(f"\n[3] Comparison:")
missing = all_trans_strings - translated_strings
if missing:
    print(f"  ✗ Missing translations ({len(missing)} strings):")
    for string in sorted(missing)[:20]:  # Show first 20
        print(f"    - {string}")
    if len(missing) > 20:
        print(f"    ... and {len(missing) - 20} more")
else:
    print(f"  ✓ All translatable strings are translated!")

covered = all_trans_strings & translated_strings
print(f"  ✓ Coverage: {len(covered)}/{len(all_trans_strings)} strings ({100*len(covered)//len(all_trans_strings)}%)" if all_trans_strings else "  ℹ No translatable strings found")

print("\n" + "=" * 60)
