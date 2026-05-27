#!/usr/bin/env python
"""
Simple script to add a basic scheme without complex conditions
"""
import os
import sys
import django
from decimal import Decimal

# Add the project directory to the path so Django can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.db import connection

def add_basic_scheme():
    """Add a single basic scheme to the database using raw SQL"""
    try:
        # Check if any schemes exist
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM content_manager_scheme")
            count = cursor.fetchone()[0]
            
            if count > 0:
                print(f"✓ {count} schemes already exist in the database")
                return
            
            # First get table schema to understand what fields we need to include
            cursor.execute("PRAGMA table_info(content_manager_scheme)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            print(f"Table columns: {column_names}")
            
            # Use raw SQL with values directly - include all required fields
            cursor.execute("""
                INSERT INTO content_manager_scheme 
                (name, code, scheme_type, description, interest_rate, duration_days,
                processing_fee_percentage, is_active, created_at, updated_at, 
                additional_conditions, no_interest_period_days, minimum_period_days)
                VALUES 
                ('Standard Gold Loan', 'STD-GOLD', 'GOLD', 'Standard gold loan scheme', 
                12.0, 365, 1.0, 1, datetime('now'), datetime('now'), 
                '{"no_interest_period_days": 30, "late_fee_percentage": 2.0}', 30, 30)
            """)
            print("✓ Created basic scheme: Standard Gold Loan")
            
            # Add a second scheme for variety
            cursor.execute("""
                INSERT INTO content_manager_scheme 
                (name, code, scheme_type, description, interest_rate, duration_days,
                processing_fee_percentage, is_active, created_at, updated_at, 
                additional_conditions, no_interest_period_days, minimum_period_days)
                VALUES 
                ('Premium Gold Loan', 'PREM-GOLD', 'GOLD', 'Premium gold loan with lower rate', 
                10.0, 365, 1.5, 1, datetime('now'), datetime('now'), 
                '{"no_interest_period_days": 45, "late_fee_percentage": 1.5}', 45, 45)
            """)
            print("✓ Created basic scheme: Premium Gold Loan")
            
            # Verify the schemes were created
            cursor.execute("SELECT COUNT(*) FROM content_manager_scheme")
            count = cursor.fetchone()[0]
            print(f"✓ Now have {count} schemes in the database")
            
    except Exception as e:
        print(f"✗ Error adding basic scheme: {str(e)}")

if __name__ == "__main__":
    print("Adding basic schemes to the database...")
    add_basic_scheme()
    print("Done!")