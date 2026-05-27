#!/usr/bin/env python
"""
Script to create sample schemes in the content_manager app
"""

import os
import sys
import django
from decimal import Decimal

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from content_manager.models import Scheme
from branches.models import Branch
from django.db import IntegrityError

def create_sample_schemes():
    """Create sample schemes in the content_manager app"""
    print("Creating sample schemes in content_manager app...")
    
    # Get default branch if available
    default_branch = None
    try:
        default_branch = Branch.objects.first()
    except:
        print("No branches found. Creating global schemes only.")
    
    # Define schemes to create
    schemes_to_create = [
        {
            'name': 'Standard Loan',
            'code': 'standard',
            'scheme_type': 'GOLD',
            'description': 'Standard gold loan scheme with 12% annual interest rate',
            'interest_rate': Decimal('12.00'),
            'duration_days': 364,
            'processing_fee_percentage': Decimal('1.00'),
            'is_active': True,
            'additional_conditions': {'no_interest_period_days': 0}
        },
        {
            'name': 'Flexible Loan',
            'code': 'flexible',
            'scheme_type': 'GOLD',
            'description': 'Flexible gold loan scheme with 24% annual interest rate',
            'interest_rate': Decimal('24.00'),
            'duration_days': 364,
            'processing_fee_percentage': Decimal('1.00'),
            'is_active': True,
            'additional_conditions': {'no_interest_period_days': 0}
        },
        {
            'name': 'Special Promotion',
            'code': 'promo',
            'scheme_type': 'GOLD',
            'description': 'Special promotional scheme with no interest for the first 30 days',
            'interest_rate': Decimal('15.00'),
            'duration_days': 364,
            'processing_fee_percentage': Decimal('0.50'),
            'is_active': True,
            'additional_conditions': {'no_interest_period_days': 30}
        }
    ]
    
    # Create each scheme
    for scheme_data in schemes_to_create:
        try:
            # Check if scheme already exists
            try:
                scheme = Scheme.objects.get(name=scheme_data['name'])
                print(f"Scheme '{scheme_data['name']}' already exists, updating it...")
                
                # Update existing scheme
                for key, value in scheme_data.items():
                    setattr(scheme, key, value)
                scheme.save()
                print(f"Updated '{scheme_data['name']}' scheme")
            except Scheme.DoesNotExist:
                # Create new scheme
                scheme = Scheme(**scheme_data)
                scheme.save()
                print(f"Created '{scheme_data['name']}' scheme")
        except Exception as e:
            print(f"Error creating/updating scheme '{scheme_data['name']}': {str(e)}")
    
    # Create branch-specific scheme if we have a branch
    if default_branch:
        branch_scheme_data = {
            'name': f'{default_branch.name} Gold Special',
            'code': f'{default_branch.name.lower().replace(" ", "_")}_special',
            'scheme_type': 'GOLD',
            'description': f'Special scheme available only at {default_branch.name}',
            'interest_rate': Decimal('10.00'),
            'duration_days': 364,
            'processing_fee_percentage': Decimal('1.00'),
            'branch': default_branch,
            'is_active': True,
            'additional_conditions': {'no_interest_period_days': 0}
        }
        
        try:
            try:
                branch_scheme = Scheme.objects.get(name=branch_scheme_data['name'])
                print(f"Branch scheme '{branch_scheme_data['name']}' already exists, updating it...")
                
                # Update existing branch scheme
                for key, value in branch_scheme_data.items():
                    setattr(branch_scheme, key, value)
                branch_scheme.save()
                print(f"Updated branch scheme '{branch_scheme_data['name']}'")
            except Scheme.DoesNotExist:
                # Create new branch scheme
                branch_scheme = Scheme(**branch_scheme_data)
                branch_scheme.save()
                print(f"Created branch scheme '{branch_scheme_data['name']}'")
        except Exception as e:
            print(f"Error creating/updating branch scheme '{branch_scheme_data['name']}': {str(e)}")
    
    print("Done creating sample schemes!")
    print(f"Total schemes in content_manager app: {Scheme.objects.count()}")

if __name__ == "__main__":
    create_sample_schemes()