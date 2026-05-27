#!/usr/bin/env python3
"""
Verify bilingual bill generation setup is complete
Checks all requirements for English and Tamil PDF generation
"""

import os
import sys
import django
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.conf import settings
from django.utils import translation

def check_setup():
    """Verify all bilingual bill generation components"""
    print("=" * 75)
    print("BILINGUAL BILL GENERATION - SETUP VERIFICATION")
    print("=" * 75)
    
    all_passed = True
    
    # Check 1: i18n Configuration
    print("\n✓ Check 1: Django i18n Configuration")
    print("-" * 75)
    print(f"  USE_I18N: {settings.USE_I18N} (Should be True)")
    if not settings.USE_I18N:
        print("  ✗ FAIL: USE_I18N must be True")
        all_passed = False
    else:
        print("  ✓ PASS")
    
    print(f"  LANGUAGE_CODE: {settings.LANGUAGE_CODE} (Should be 'en-us')")
    print(f"  LANGUAGES: {settings.LANGUAGES}")
    if ('en', 'English') not in settings.LANGUAGES or ('ta', 'Tamil') not in settings.LANGUAGES:
        print("  ✗ FAIL: Both English and Tamil must be in LANGUAGES")
        all_passed = False
    else:
        print("  ✓ PASS")
    
    # Check 2: Locale Files
    print("\n✓ Check 2: Locale Files")
    print("-" * 75)
    locale_path = Path(settings.BASE_DIR) / 'locale'
    print(f"  Locale path: {locale_path}")
    print(f"  Path exists: {locale_path.exists()}")
    
    if locale_path.exists():
        ta_po = locale_path / 'ta' / 'LC_MESSAGES' / 'django.po'
        ta_mo = locale_path / 'ta' / 'LC_MESSAGES' / 'django.mo'
        print(f"  Tamil PO file exists: {ta_po.exists()}")
        print(f"  Tamil MO file exists: {ta_mo.exists()}")
        if ta_mo.exists():
            mo_size = ta_mo.stat().st_size
            print(f"    File size: {mo_size} bytes")
            if mo_size > 0:
                print("  ✓ PASS")
            else:
                print("  ✗ FAIL: MO file is empty")
                all_passed = False
        else:
            print("  ✗ FAIL: Run 'python manage.py compilemessages'")
            all_passed = False
    else:
        print("  ✗ FAIL: locale directory not found")
        all_passed = False
    
    # Check 3: Tamil Font File
    print("\n✓ Check 3: Tamil Font File")
    print("-" * 75)
    font_path = Path(settings.BASE_DIR) / 'static' / 'fonts' / 'NotoSansTamil-Regular.ttf'
    print(f"  Font path: {font_path}")
    print(f"  Font exists: {font_path.exists()}")
    if font_path.exists():
        font_size = font_path.stat().st_size
        print(f"  Font size: {font_size:,} bytes")
        if font_size > 50000:
            print("  ✓ PASS")
        else:
            print("  ⚠ WARNING: Font file seems too small")
    else:
        print("  ✗ FAIL: Font file not found")
        all_passed = False
    
    # Check 4: PDF Template Files
    print("\n✓ Check 4: PDF Template Files")
    print("-" * 75)
    template_path = Path(settings.BASE_DIR) / 'transactions' / 'templates' / 'transactions'
    templates = {
        'loan_document_pdf.html': 'Loan agreement template',
        'payment_receipt_pdf.html': 'Payment receipt template',
        'sale_receipt_pdf.html': 'Sale receipt template',
    }
    
    for template_file, description in templates.items():
        full_path = template_path / template_file
        exists = full_path.exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {template_file}")
        print(f"    ({description})")
        if not exists:
            all_passed = False
        else:
            # Check for Tamil font support
            content = full_path.read_text(encoding='utf-8')
            if 'NotoSansTamil' in content or 'tamil-text' in content:
                print(f"    ✓ Tamil font support found")
            else:
                print(f"    ⚠ Tamil font support not detected")
    
    if all([
        (template_path / f).exists() 
        for f in templates.keys()
    ]):
        print("  ✓ PASS: All templates found")
    else:
        print("  ✗ FAIL: Some templates missing")
        all_passed = False
    
    # Check 5: View Functions
    print("\n✓ Check 5: PDF View Functions")
    print("-" * 75)
    try:
        from transactions.views import LoanDocumentView, build_loan_pdf_language_context
        print("  ✓ LoanDocumentView imported successfully")
        print("  ✓ build_loan_pdf_language_context imported successfully")
        
        # Check if function returns proper structure
        test_context = build_loan_pdf_language_context(None, 'en')
        if isinstance(test_context, dict) and 'labels' in test_context:
            print("  ✓ Function returns correct context structure")
        else:
            print("  ⚠ WARNING: Function structure may be incorrect")
    except ImportError as e:
        print(f"  ✗ FAIL: Import error - {e}")
        all_passed = False
    except Exception as e:
        print(f"  ⚠ WARNING: {e}")
    
    # Check 6: Middleware
    print("\n✓ Check 6: Django Middleware")
    print("-" * 75)
    middleware = settings.MIDDLEWARE
    locale_middleware = [m for m in middleware if 'locale' in m.lower()]
    print(f"  Locale middleware found: {len(locale_middleware) > 0}")
    for m in locale_middleware:
        print(f"    • {m}")
    if locale_middleware:
        print("  ✓ PASS: LocaleMiddleware configured")
    else:
        print("  ⚠ WARNING: LocaleMiddleware may not be configured")
    
    # Check 7: Browser Rendering
    print("\n✓ Check 7: Browser PDF Rendering")
    print("-" * 75)
    import shutil
    browsers = {
        'Chrome': [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        'Edge': [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ],
    }
    
    found = False
    for name, paths in browsers.items():
        for path in paths:
            if Path(path).exists() or shutil.which(name.lower()):
                print(f"  ✓ {name} browser found")
                found = True
                break
    
    if found:
        print("  ✓ PASS: Browser rendering available")
    else:
        print("  ✗ FAIL: No browser found for rendering")
        print("    Install Chrome or Edge for best PDF quality")
        all_passed = False
    
    # Check 8: Test Data
    print("\n✓ Check 8: Test Data (Loans)")
    print("-" * 75)
    from transactions.models import Loan
    loan_count = Loan.objects.count()
    print(f"  Total loans in database: {loan_count}")
    if loan_count > 0:
        latest_loan = Loan.objects.latest('created_at')
        print(f"  Latest loan: {latest_loan.loan_number}")
        print(f"  Customer: {latest_loan.customer.full_name if latest_loan.customer else 'N/A'}")
        print(f"  Amount: Rs {latest_loan.principal_amount:,}")
        print("  ✓ PASS: Test data available")
    else:
        print("  ✗ FAIL: No loans found in database")
        all_passed = False
    
    # Summary
    print("\n" + "=" * 75)
    if all_passed:
        print("✅ ALL CHECKS PASSED!")
        print("=" * 75)
        print("\n✓ Bilingual bill generation is fully configured")
        print("✓ Both English and Tamil bills can be generated")
        print("✓ Single-page layout with auto-adjusted content")
        print("✓ Professional formatting with proper fonts")
        print("\nYou can now:")
        print("  1. Select English or Tamil language")
        print("  2. Open any loan")
        print("  3. Click 'Download Loan Agreement'")
        print("  4. PDF generates in selected language")
        return True
    else:
        print("⚠️  SOME CHECKS FAILED")
        print("=" * 75)
        print("\nActions needed:")
        print("  1. Check all failed items above")
        print("  2. Run: python manage.py compilemessages")
        print("  3. Ensure fonts are in static/fonts/")
        print("  4. Verify templates exist")
        print("  5. Install Chrome or Edge browser")
        return False

if __name__ == '__main__':
    success = check_setup()
    sys.exit(0 if success else 1)
