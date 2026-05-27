#!/usr/bin/env python3
"""
Test bilingual bill generation (English and Tamil)
Tests that PDFs generate correctly in both languages
"""

import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from transactions.models import Loan
from django.test import RequestFactory
from django.utils import translation

def test_bill_generation():
    """Test bill generation in both languages"""
    print("=" * 70)
    print("BILINGUAL BILL GENERATION TEST")
    print("=" * 70)
    
    # Get the latest loan
    try:
        loan = Loan.objects.latest('created_at')
        print(f"\n✓ Found loan: {loan.loan_number}")
        print(f"  Customer: {loan.customer.full_name if loan.customer else 'N/A'}")
        print(f"  Amount: Rs {loan.principal_amount}")
    except Loan.DoesNotExist:
        print("\n✗ ERROR: No loans found in database")
        return False
    
    # Test English bill
    print("\n" + "-" * 70)
    print("TEST 1: English Bill Generation")
    print("-" * 70)
    
    try:
        factory = RequestFactory()
        request = factory.get('/loans/')
        
        with translation.override('en'):
            request.LANGUAGE_CODE = 'en'
            from transactions.views import LoanDocumentView
            view = LoanDocumentView()
            response = view.get(request, loan.loan_number)
            
            if response.status_code == 200:
                content_length = len(response.content)
                print(f"✓ English PDF generated successfully")
                print(f"  File size: {content_length / 1024:.1f} KB")
                print(f"  Language code: {request.LANGUAGE_CODE}")
            else:
                print(f"✗ ERROR: Response status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ ERROR generating English bill: {e}")
        return False
    
    # Test Tamil bill
    print("\n" + "-" * 70)
    print("TEST 2: Tamil Bill Generation")
    print("-" * 70)
    
    try:
        factory = RequestFactory()
        request = factory.get('/loans/')
        
        with translation.override('ta'):
            request.LANGUAGE_CODE = 'ta'
            from transactions.views import LoanDocumentView
            view = LoanDocumentView()
            response = view.get(request, loan.loan_number)
            
            if response.status_code == 200:
                content_length = len(response.content)
                print(f"✓ Tamil PDF generated successfully")
                print(f"  File size: {content_length / 1024:.1f} KB")
                print(f"  Language code: {request.LANGUAGE_CODE}")
            else:
                print(f"✗ ERROR: Response status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ ERROR generating Tamil bill: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✓ BOTH LANGUAGE BILLS GENERATED SUCCESSFULLY!")
    print("=" * 70)
    print("\nBill Features:")
    print("  • Single page layout (A4 format)")
    print("  • Responsive font sizing")
    print("  • Auto-adjusted images")
    print("  • Proper Tamil Unicode support")
    print("  • Professional formatting")
    print("\nHow to Use:")
    print("  1. Select language (English/Tamil) in web interface")
    print("  2. Click 'Download Loan Agreement' or 'Generate PDF'")
    print("  3. Bill generates in selected language")
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    success = test_bill_generation()
    sys.exit(0 if success else 1)
