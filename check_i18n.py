#!/usr/bin/env python
"""Check i18n configuration"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.conf import settings

print("=" * 60)
print("DJANGO i18N CONFIGURATION CHECK")
print("=" * 60)

print("\n✓ LANGUAGES settings:")
for code, name in settings.LANGUAGES:
    print(f"    {code}: {name}")

print(f"\n✓ LANGUAGE_CODE: {settings.LANGUAGE_CODE}")
print(f"✓ USE_I18N: {settings.USE_I18N}")
print(f"✓ USE_L10N: {settings.USE_L10N}")

print(f"\n✓ LOCALE_PATHS:")
for path in settings.LOCALE_PATHS:
    exists = os.path.exists(path)
    print(f"    {path}")
    print(f"      Exists: {exists}")
    if exists:
        for root, dirs, files in os.walk(path):
            level = root.replace(str(path), '').count(os.sep)
            indent = ' ' * 4 * (level + 2)
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 3)
            for file in files:
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                print(f"{subindent}{file} ({size} bytes)")

print("\n✓ MIDDLEWARE (relevant to i18n):")
for mw in settings.MIDDLEWARE:
    if 'locale' in mw.lower() or 'session' in mw.lower():
        print(f"    {mw} ✓")
    elif 'i18n' in mw.lower():
        print(f"    {mw} ✓")

print("\n" + "=" * 60)
