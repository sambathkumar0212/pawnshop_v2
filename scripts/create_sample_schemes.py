#!/usr/bin/env python
"""
Script to create sample loan schemes in the schemes app.
This will help ensure the scheme dropdown in the loan form has content.
"""
import os
import sys
import django

# Add the project directory to the path so Django can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from schemes.models import Scheme
from decimal import Decimal
from django.db import connection

def check_column_exists(table, column):
    """Check if a column exists in a table"""
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [info[1] for info in cursor.fetchall()]
        return column in columns

def create_sample_schemes():
    """Create sample loan schemes if none exist"""
    # Check if any schemes already exist
    if Scheme.objects.exists():
        print("✓ Loan schemes already exist in the database.")
        print(f"  Found {Scheme.objects.count()} schemes.")
        return
    
    # Check if no_interest_period_days is a direct column in the table
    has_no_interest_column = check_column_exists('schemes_scheme', 'no_interest_period_days')
    
    # Create sample schemes
    schemes = [
        {
            'name': 'Standard Gold Loan',
            'description': 'Standard gold loan scheme with 12% annual interest',
            'interest_rate': Decimal('12.00'),
            'loan_duration': 365,
            'minimum_amount': Decimal('5000.00'),
            'maximum_amount': Decimal('1000000.00'),
            'start_date': '2025-01-01',
            'end_date': '2025-12-31',
            'status': 'active',
            'additional_conditions': {
                'no_interest_period_days': 30,
                'late_fee_percentage': 2.00,
                'processing_fee_percentage': 1.00
            }
        },
        {
            'name': 'Premium Gold Loan',
            'description': 'Premium gold loan scheme with 10% annual interest',
            'interest_rate': Decimal('10.00'),
            'loan_duration': 365, 
            'minimum_amount': Decimal('10000.00'),
            'maximum_amount': Decimal('2000000.00'),
            'start_date': '2025-01-01',
            'end_date': '2025-12-31',
            'status': 'active',
            'additional_conditions': {
                'no_interest_period_days': 45,
                'late_fee_percentage': 1.50,
                'processing_fee_percentage': 1.50
            }
        },
        {
            'name': 'Quick Gold Loan',
            'description': 'Short-term gold loan with 15% annual interest',
            'interest_rate': Decimal('15.00'),
            'loan_duration': 180,
            'minimum_amount': Decimal('3000.00'),
            'maximum_amount': Decimal('500000.00'),
            'start_date': '2025-01-01',
            'end_date': '2025-12-31',
            'status': 'active',
            'additional_conditions': {
                'no_interest_period_days': 15,
                'late_fee_percentage': 2.50,
                'processing_fee_percentage': 0.75
            }
        }
    ]
    
    # Create schemes one by one
    for scheme_data in schemes:
        try:
            # Create the scheme
            scheme = Scheme.objects.create(**scheme_data)
            print(f"✓ Created scheme: {scheme_data['name']}")
        except Exception as e:
            print(f"✗ Error creating scheme {scheme_data['name']}: {str(e)}")
            
            # Try an alternative approach if the first one fails
            try:
                # Create the scheme without additional_conditions first
                additional_conditions = scheme_data.pop('additional_conditions')
                scheme = Scheme.objects.create(**scheme_data)
                
                # Then update additional_conditions separately
                scheme.additional_conditions = additional_conditions
                scheme.save()
                print(f"✓ Created scheme: {scheme_data['name']} (alternative method)")
            except Exception as e2:
                print(f"✗ Alternative method also failed: {str(e2)}")
    
    print(f"✓ Scheme creation process completed.")

if __name__ == "__main__":
    print("Creating sample loan schemes...")
    create_sample_schemes()
    print("Done!")