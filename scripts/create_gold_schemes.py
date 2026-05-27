#!/usr/bin/env python
"""
Script to create gold loan schemes in the schemes app.
This will add the six gold schemes as specified:
1. Standard
2. Long Term Saver
3. Premium
4. Standard Premium
5. 916 QuickPay
6. QuickPay
"""
import os
import sys
import django
from datetime import date, timedelta

# Add the project directory to the path so Django can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from schemes.models import Scheme
from decimal import Decimal
from django.utils import timezone

def create_gold_schemes():
    """Create the six gold loan schemes"""
    # Check if any gold schemes already exist
    if Scheme.objects.filter(is_gold_scheme=True).exists():
        print("✓ Gold loan schemes already exist in the database.")
        print(f"  Found {Scheme.objects.filter(is_gold_scheme=True).count()} gold schemes.")
        return
    
    # Define the start date (today) and end date (1 year from now)
    start_date = timezone.now().date()
    end_date = start_date + timedelta(days=365)
    
    # Create the six gold schemes
    gold_schemes = [
        {
            'name': 'Standard Gold Loan',
            'description': 'Standard gold loan with 1 Rupee per 100 Rupees per month interest rate.',
            'is_gold_scheme': True,
            'gold_interest_rate': Decimal('1.00'),
            'expiry_period': 6,
            'minimum_duration': 0,
            'late_payment_interest': Decimal('0.30'),
            'payment_due_day': 5,
            'special_conditions': 'If the interest is not paid by the 5th of the month, an additional 30 paisa interest per month will be added.',
            'is_fixed_interest': False,
            'auction_on_expiry': False,
            'interest_rate': Decimal('12.00'),  # Annual equivalent rate
            'loan_duration': 180,  # 6 months in days
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('1000000.00'),
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
        },
        {
            'name': 'Long Term Saver Gold Loan',
            'description': 'Long term gold loan with 1 Rupee per 100 Rupees per month interest rate and minimum 3 months duration.',
            'is_gold_scheme': True,
            'gold_interest_rate': Decimal('1.00'),
            'expiry_period': 12,
            'minimum_duration': 3,
            'late_payment_interest': Decimal('0.40'),
            'payment_due_day': 5,
            'special_conditions': 'If the interest is not paid by the 5th of the month, an additional 40 paisa interest per month will be added.',
            'is_fixed_interest': False,
            'auction_on_expiry': False,
            'interest_rate': Decimal('12.00'),  # Annual equivalent rate
            'loan_duration': 365,  # 12 months in days
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('1000000.00'),
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
        },
        {
            'name': 'Premium Gold Loan',
            'description': 'Premium gold loan with 2 Rupees per 100 Rupees per month fixed interest rate.',
            'is_gold_scheme': True,
            'gold_interest_rate': Decimal('2.00'),
            'expiry_period': 6,
            'minimum_duration': 0,
            'late_payment_interest': Decimal('0.00'),
            'payment_due_day': 5,
            'special_conditions': 'Fixed interest rate.',
            'is_fixed_interest': True,
            'auction_on_expiry': False,
            'interest_rate': Decimal('24.00'),  # Annual equivalent rate
            'loan_duration': 180,  # 6 months in days
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('1000000.00'),
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
        },
        {
            'name': 'Standard Premium Gold Loan',
            'description': 'Standard premium gold loan with 3 Rupees per 100 Rupees per month fixed interest rate and minimum 3 months duration.',
            'is_gold_scheme': True,
            'gold_interest_rate': Decimal('3.00'),
            'expiry_period': 12,
            'minimum_duration': 3,
            'late_payment_interest': Decimal('0.00'),
            'payment_due_day': 5,
            'special_conditions': 'Fixed interest rate.',
            'is_fixed_interest': True,
            'auction_on_expiry': False,
            'interest_rate': Decimal('36.00'),  # Annual equivalent rate
            'loan_duration': 365,  # 12 months in days
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('1000000.00'),
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
        },
        {
            'name': '916 QuickPay Gold Loan',
            'description': '916 QuickPay gold loan with 0 Rupees per 100 Rupees for the first month, then 4 Rupees after.',
            'is_gold_scheme': True,
            'gold_interest_rate': Decimal('0.00'),
            'expiry_period': 3,
            'minimum_duration': 0,
            'late_payment_interest': Decimal('0.00'),
            'payment_due_day': 5,
            'special_conditions': 'After 1 month, the interest will be 4 Rupees. If the loan is not repaid in 3 months, the gold will be auctioned.',
            'is_fixed_interest': False,
            'auction_on_expiry': True,
            'interest_rate': Decimal('48.00'),  # Equivalent to 4 Rupees per month after first month
            'loan_duration': 90,  # 3 months in days
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('1000000.00'),
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
        },
        {
            'name': 'QuickPay Gold Loan',
            'description': 'QuickPay gold loan with 50 paisa per 100 Rupees for the first month, then 4 Rupees after.',
            'is_gold_scheme': True,
            'gold_interest_rate': Decimal('0.50'),
            'expiry_period': 3,
            'minimum_duration': 0,
            'late_payment_interest': Decimal('0.00'),
            'payment_due_day': 5,
            'special_conditions': 'After 1 month, the interest will be 4 Rupees. If the loan is not repaid in 3 months, the gold will be auctioned.',
            'is_fixed_interest': False,
            'auction_on_expiry': True,
            'interest_rate': Decimal('48.00'),  # Equivalent to 4 Rupees per month after first month
            'loan_duration': 90,  # 3 months in days
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('1000000.00'),
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
        },
    ]
    
    # Create schemes one by one
    for scheme_data in gold_schemes:
        try:
            # Create the scheme
            scheme = Scheme.objects.create(**scheme_data)
            print(f"✓ Created gold scheme: {scheme_data['name']}")
        except Exception as e:
            print(f"✗ Error creating gold scheme {scheme_data['name']}: {str(e)}")
    
    print(f"✓ Gold scheme creation process completed.")

if __name__ == "__main__":
    print("Creating gold loan schemes...")
    create_gold_schemes()
    print("Done!")