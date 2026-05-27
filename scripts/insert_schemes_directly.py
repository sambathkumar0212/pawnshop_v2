#!/usr/bin/env python
"""
Script to insert sample schemes directly using SQL to bypass model validation issues
"""
import os
import sys
import json
import django
from decimal import Decimal

# Add the project directory to the path so Django can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.db import connection
from django.utils import timezone

def insert_sample_schemes():
    """Insert sample schemes using direct SQL to bypass model validation"""
    # First check if any schemes exist
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM content_manager_scheme")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"✓ {count} schemes already exist in the database")
            return
        
        now = timezone.now().isoformat()
        
        # Create schemes with SQL INSERT statements
        schemes = [
            (
                'Standard Gold Loan',  # name
                'STD-GOLD',  # code
                'GOLD',  # scheme_type
                'Standard gold loan scheme with 12% annual interest',  # description
                12.00,  # interest_rate
                365,  # duration_days
                1.00,  # processing_fee_percentage
                None,  # branch_id (null for global schemes)
                1,  # is_active
                now,  # created_at
                now,  # updated_at
                json.dumps({  # additional_conditions as JSON string
                    'no_interest_period_days': 30,
                    'late_fee_percentage': 2.00
                }),
            ),
            (
                'Premium Gold Loan',
                'PREM-GOLD',
                'GOLD',
                'Premium gold loan scheme with 10% annual interest',
                10.00,
                365,
                1.50,
                None,
                1,
                now,
                now,
                json.dumps({
                    'no_interest_period_days': 45,
                    'late_fee_percentage': 1.50
                }),
            ),
            (
                'Quick Gold Loan',
                'QUICK-GOLD',
                'GOLD',
                'Short-term gold loan with 15% annual interest',
                15.00,
                180,
                0.75,
                None,
                1,
                now,
                now,
                json.dumps({
                    'no_interest_period_days': 15,
                    'late_fee_percentage': 2.50
                }),
            ),
        ]
        
        # Insert schemes one by one to handle potential errors better
        for i, scheme in enumerate(schemes, 1):
            try:
                cursor.execute("""
                    INSERT INTO content_manager_scheme 
                    (name, code, scheme_type, description, interest_rate, duration_days,
                    processing_fee_percentage, branch_id, is_active, created_at, updated_at, additional_conditions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, scheme)
                print(f"✓ Created scheme {i}: {scheme[0]}")
            except Exception as e:
                print(f"✗ Error creating scheme {i} ({scheme[0]}): {str(e)}")
        
        print("✓ Sample schemes creation completed")

if __name__ == "__main__":
    print("Creating sample schemes with direct SQL...")
    insert_sample_schemes()
    print("Done!")