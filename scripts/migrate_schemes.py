#!/usr/bin/env python
"""
Script to migrate schemes from the schemes app to the content_manager app.
This addresses the issue of having two different Scheme models in the project.

Usage:
    python manage.py shell < scripts/migrate_schemes.py
"""

import sys
import os
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pawnshop_management.settings")
django.setup()

# Import both Scheme models
from schemes.models import Scheme as SchemeOld
from content_manager.models import Scheme as SchemeNew
from django.utils.text import slugify
from django.utils import timezone
from decimal import Decimal

def migrate_schemes():
    """Migrate schemes from schemes app to content_manager app"""
    
    print("Starting scheme migration...")
    
    # Get all schemes from the schemes app
    old_schemes = SchemeOld.objects.all()
    
    if not old_schemes.exists():
        print("No schemes found in the schemes app to migrate.")
        return
    
    print(f"Found {old_schemes.count()} schemes to migrate.")
    
    # Track statistics
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    # Process each scheme
    for old_scheme in old_schemes:
        print(f"\nProcessing scheme: {old_scheme.name}")
        
        # Map fields from old scheme to new scheme format
        scheme_data = {
            'name': old_scheme.name,
            'description': old_scheme.description,
            'interest_rate': old_scheme.interest_rate,
            'duration_days': old_scheme.loan_duration,
            'processing_fee_percentage': Decimal('1.00'),  # Default value
            'branch': old_scheme.branch,
            'is_active': old_scheme.is_active,
            'scheme_type': 'GOLD',  # Default to gold loan
        }
        
        # Generate code from name
        scheme_data['code'] = slugify(old_scheme.name)[:20]
        
        # Copy additional conditions
        additional_conditions = {}
        if old_scheme.additional_conditions:
            additional_conditions = old_scheme.additional_conditions
            
            # Specifically handle no_interest_period_days if present
            if old_scheme.no_interest_period_days:
                additional_conditions['no_interest_period_days'] = old_scheme.no_interest_period_days
                
        scheme_data['additional_conditions'] = additional_conditions
        
        # Check if a scheme with the same name already exists in content_manager
        try:
            existing_scheme = SchemeNew.objects.get(name=old_scheme.name, branch=old_scheme.branch)
            print(f"  Scheme '{old_scheme.name}' already exists in content_manager app.")
            
            # Update the existing scheme
            for key, value in scheme_data.items():
                setattr(existing_scheme, key, value)
            
            existing_scheme.save()
            print(f"  Updated existing scheme in content_manager app.")
            updated_count += 1
            
        except SchemeNew.DoesNotExist:
            # Create a new scheme in content_manager
            new_scheme = SchemeNew(**scheme_data)
            new_scheme.save()
            print(f"  Created new scheme '{new_scheme.name}' in content_manager app.")
            created_count += 1
        
        except Exception as e:
            print(f"  Error processing scheme '{old_scheme.name}': {str(e)}")
            skipped_count += 1
    
    print("\nMigration complete!")
    print(f"Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}")
    print("\nIMPORTANT: Make sure to update your views to use the Scheme model from content_manager app.")

if __name__ == "__main__":
    migrate_schemes()