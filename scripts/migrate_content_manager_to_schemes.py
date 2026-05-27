#!/usr/bin/env python
"""
Script to migrate schemes from the content_manager app to the schemes app
before removing the content_manager app from the project.
"""

import os
import sys
import django
from decimal import Decimal
from django.utils import timezone

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

def migrate_schemes():
    """Migrate schemes from content_manager app to schemes app"""
    from content_manager.models import Scheme as ContentManagerScheme
    from schemes.models import Scheme as SchemesAppScheme
    
    print("\nStarting migration of schemes from content_manager to schemes app...")
    
    # Get all schemes from the content_manager app
    cm_schemes = ContentManagerScheme.objects.all()
    
    if not cm_schemes:
        print("No schemes found in content_manager app to migrate.")
        return
    
    print(f"Found {cm_schemes.count()} schemes to migrate.")
    
    # Track statistics
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    # Process each scheme
    for cm_scheme in cm_schemes:
        print(f"\nProcessing scheme: {cm_scheme.name}")
        
        # Get created_by user if it exists
        created_by = None
        if hasattr(cm_scheme, 'created_by') and cm_scheme.created_by:
            created_by = cm_scheme.created_by
        
        # Set up reasonable defaults for minimum and maximum amounts
        min_amount = Decimal('1000.00')  # Default 1,000 Rs
        max_amount = Decimal('1000000.00')  # Default 10,00,000 Rs
        
        # Extract min/max amounts from additional conditions if available
        if hasattr(cm_scheme, 'additional_conditions') and cm_scheme.additional_conditions:
            if 'minimum_amount' in cm_scheme.additional_conditions:
                try:
                    min_amount = Decimal(str(cm_scheme.additional_conditions['minimum_amount']))
                except (ValueError, TypeError, KeyError):
                    pass
                
            if 'maximum_amount' in cm_scheme.additional_conditions:
                try:
                    max_amount = Decimal(str(cm_scheme.additional_conditions['maximum_amount']))
                except (ValueError, TypeError, KeyError):
                    pass
        
        # Ensure duration_days is properly mapped
        duration_days = 364  # Default loan duration (1 year)
        if hasattr(cm_scheme, 'duration_days') and cm_scheme.duration_days:
            duration_days = cm_scheme.duration_days
        
        # Map fields from content_manager scheme to schemes app format
        scheme_data = {
            'name': cm_scheme.name,
            'description': cm_scheme.description or f"Loan scheme: {cm_scheme.name}",
            'interest_rate': cm_scheme.interest_rate,
            'loan_duration': duration_days,
            'minimum_amount': min_amount,
            'maximum_amount': max_amount,
            'branch': cm_scheme.branch,
            'status': 'active' if cm_scheme.is_active else 'inactive',
            'start_date': timezone.now().date(),  # Current date as start date
            'created_by': created_by,
            'additional_conditions': {},
        }
        
        # Copy and enhance additional conditions
        if hasattr(cm_scheme, 'additional_conditions') and cm_scheme.additional_conditions:
            scheme_data['additional_conditions'] = cm_scheme.additional_conditions.copy()
        
        # Make sure the additional_conditions field has essential values
        if 'no_interest_period_days' not in scheme_data['additional_conditions']:
            scheme_data['additional_conditions']['no_interest_period_days'] = 0
            
        if 'processing_fee_percentage' not in scheme_data['additional_conditions']:
            scheme_data['additional_conditions']['processing_fee_percentage'] = 1.0  # Default 1%
            
        # Add custom scheme metadata
        scheme_data['additional_conditions']['migrated_from_content_manager'] = True
        scheme_data['additional_conditions']['migration_date'] = timezone.now().isoformat()
        
        # Check if a scheme with the same name already exists in schemes app
        try:
            existing_scheme = SchemesAppScheme.objects.get(name=cm_scheme.name, branch=cm_scheme.branch)
            print(f"  Scheme '{cm_scheme.name}' already exists in schemes app.")
            
            # Update the existing scheme
            for key, value in scheme_data.items():
                setattr(existing_scheme, key, value)
            
            existing_scheme.save()
            print(f"  Updated existing scheme in schemes app.")
            updated_count += 1
            
        except SchemesAppScheme.DoesNotExist:
            # Create a new scheme in schemes app
            new_scheme = SchemesAppScheme(**scheme_data)
            new_scheme.save()
            print(f"  Created new scheme '{new_scheme.name}' in schemes app.")
            created_count += 1
        
        except Exception as e:
            print(f"  Error processing scheme '{cm_scheme.name}': {str(e)}")
            skipped_count += 1
    
    print("\nMigration complete!")
    print(f"Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}")
    
    # Check if any loans are using content_manager schemes and update them
    try:
        from transactions.models import Loan
        
        # Check if the Loan model has a scheme field that's a ForeignKey to content_manager.Scheme
        loans_using_cm_schemes = Loan.objects.filter(scheme__isnull=False).count()
        if loans_using_cm_schemes > 0:
            print(f"\nFound {loans_using_cm_schemes} loans using content_manager schemes.")
            print("Please run the update_loan_schemes.py script to update these loans to use schemes from the schemes app.")
    except Exception as e:
        print(f"\nError checking loans using content_manager schemes: {str(e)}")

if __name__ == "__main__":
    migrate_schemes()