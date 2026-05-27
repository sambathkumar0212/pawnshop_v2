#!/usr/bin/env python
"""
Script to create default loan schemes that will be available to all organizations.
These default schemes serve as standard options that all organizations can use,
while still allowing organizations to create their own custom schemes.
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
from django.contrib.auth import get_user_model

User = get_user_model()

def create_default_schemes():
    """Create default loan schemes that will be available to all organizations"""
    # Try to find a superuser to set as the creator
    try:
        admin_user = User.objects.filter(is_superuser=True).first()
    except:
        admin_user = None
        
    # Calculate dates based on current date
    today = date.today()
    start_date = today
    end_date = today + timedelta(days=365*2)  # Valid for 2 years
    
    # Define default schemes
    default_schemes = [
        {
            'name': 'Standard Gold Loan (Default)',
            'description': 'Default standard gold loan scheme with 12% annual interest',
            'interest_rate': Decimal('12.00'),
            'loan_duration': 365,
            'minimum_amount': Decimal('5000.00'),
            'maximum_amount': Decimal('1000000.00'),
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
            'is_default': True,  # Mark as default scheme
            'organization': None,  # No specific organization
            'branch': None,  # No specific branch
            'additional_conditions': {
                'no_interest_period_days': 30,
                'late_fee_percentage': 2.00,
                'processing_fee_percentage': 1.00
            }
        },
        {
            'name': 'Premium Gold Loan (Default)',
            'description': 'Default premium gold loan scheme with 10% annual interest',
            'interest_rate': Decimal('10.00'),
            'interest_rate_structure': {
                '0-6': 10.00,
                '6-12': 11.00,
                '12+': 12.00
            },
            'loan_duration': 365, 
            'minimum_amount': Decimal('10000.00'),
            'maximum_amount': Decimal('2000000.00'),
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
            'is_default': True,  # Mark as default scheme
            'organization': None,  # No specific organization
            'branch': None,  # No specific branch
            'additional_conditions': {
                'no_interest_period_days': 45,
                'late_fee_percentage': 1.50,
                'processing_fee_percentage': 1.50
            }
        },
        {
            'name': 'Quick Gold Loan (Default)',
            'description': 'Default short-term gold loan with 15% annual interest',
            'interest_rate': Decimal('15.00'),
            'loan_duration': 180,
            'minimum_amount': Decimal('3000.00'),
            'maximum_amount': Decimal('500000.00'),
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
            'is_default': True,  # Mark as default scheme
            'organization': None,  # No specific organization
            'branch': None,  # No specific branch
            'additional_conditions': {
                'no_interest_period_days': 15,
                'late_fee_percentage': 2.50,
                'processing_fee_percentage': 0.75
            }
        },
        {
            'name': 'Silver Loan (Default)',
            'description': 'Default silver loan scheme with 14% annual interest',
            'interest_rate': Decimal('14.00'),
            'loan_duration': 365,
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('300000.00'),
            'start_date': start_date,
            'end_date': end_date,
            'status': 'active',
            'is_default': True,  # Mark as default scheme
            'organization': None,  # No specific organization
            'branch': None,  # No specific branch
            'additional_conditions': {
                'no_interest_period_days': 15,
                'late_fee_percentage': 2.00,
                'processing_fee_percentage': 1.00
            }
        }
    ]
    
    # Check if default schemes already exist
    existing_default_count = Scheme.objects.filter(is_default=True).count()
    if existing_default_count > 0:
        print(f"✓ {existing_default_count} default schemes already exist.")
        return
    
    # Create schemes one by one
    for scheme_data in default_schemes:
        try:
            # Add creator and updater if admin user exists
            if admin_user:
                scheme_data['created_by'] = admin_user
                scheme_data['updated_by'] = admin_user
                
            # Create the scheme
            scheme = Scheme.objects.create(**scheme_data)
            print(f"✓ Created default scheme: {scheme_data['name']}")
        except Exception as e:
            print(f"✗ Error creating default scheme {scheme_data['name']}: {str(e)}")
            
            # Try an alternative approach if the first one fails
            try:
                # Create the scheme without additional_conditions first
                additional_conditions = scheme_data.pop('additional_conditions', None)
                interest_rate_structure = scheme_data.pop('interest_rate_structure', None)
                
                scheme = Scheme.objects.create(**scheme_data)
                
                # Then update additional fields separately
                if additional_conditions:
                    scheme.additional_conditions = additional_conditions
                if interest_rate_structure:
                    scheme.interest_rate_structure = interest_rate_structure
                scheme.save()
                print(f"✓ Created default scheme: {scheme_data['name']} (alternative method)")
            except Exception as e2:
                print(f"✗ Alternative method also failed: {str(e2)}")
    
    print(f"✓ Default scheme creation process completed.")

if __name__ == "__main__":
    print("Creating default loan schemes that will be available to all organizations...")
    create_default_schemes()
    print("Done!")