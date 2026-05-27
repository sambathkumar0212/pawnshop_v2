#!/usr/bin/env python
"""Test language switching functionality"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from django.contrib.sessions.models import Session
from django.utils import translation

# Create a test client
client = Client()

print("=" * 60)
print("TESTING TAMIL LANGUAGE SWITCHING")
print("=" * 60)

# Test 1: Check if the set_language view exists
print("\n[Test 1] Checking set_language URL...")
try:
    url = reverse('set_language')
    print(f"  ✓ URL found: {url}")
except Exception as e:
    print(f"  ✗ Error: {e}")
    sys.exit(1)

# Test 2: Try to get the homepage in English
print("\n[Test 2] Getting homepage in English...")
try:
    response = client.get('/')
    print(f"  ✓ Status code: {response.status_code}")
    if 'Dashboard' in response.content.decode('utf-8'):
        print(f"  ✓ English content found")
    else:
        print(f"  ✗ English content not found")
    print(f"  ✓ Session language (initially): {translation.get_language_from_request(response.wsgi_request)}")
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 3: Switch to Tamil
print("\n[Test 3] Switching language to Tamil...")
try:
    response = client.post(
        reverse('set_language'),
        {'language': 'ta', 'next': '/'},
        follow=True
    )
    print(f"  ✓ POST Status code: {response.status_code}")
    print(f"  ✓ Redirect location: {response.redirect_chain}")
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 4: Check if the session has the language set
print("\n[Test 4] Checking session language...")
try:
    from django.conf import settings
    session = client.session
    lang_key = settings.LANGUAGE_COOKIE_NAME if hasattr(settings, 'LANGUAGE_COOKIE_NAME') else 'django_language'
    print(f"  ℹ Language cookie name: {lang_key}")
    if lang_key in session:
        print(f"  ✓ Session language: {session[lang_key]}")
    else:
        print(f"  ✗ Language not found in session")
        print(f"  ℹ Session keys: {list(session.keys())}")
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 5: Check Tamil translations
print("\n[Test 5] Testing Tamil translations...")
try:
    from django.utils.translation import gettext
    from django.utils import translation
    
    # Activate Tamil
    translation.activate('ta')
    
    translations = {
        'Dashboard': 'பணிமுகப்பு',
        'Customers': 'வாடிக்கையாளர்கள்',
        'Profile': 'சுயவிவரம்',
    }
    
    for en, ta in translations.items():
        result = gettext(en)
        if result == ta:
            print(f"  ✓ '{en}' → '{result}'")
        else:
            print(f"  ✗ '{en}' → '{result}' (expected: '{ta}')")
    
    # Reset to English
    translation.activate('en-us')
    
except Exception as e:
    print(f"  ✗ Error: {e}")

print("\n" + "=" * 60)
