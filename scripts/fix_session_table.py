#!/usr/bin/env python
"""
Script to specifically check for and create the django_session table if missing.
Run this script after deployment if the django_session table is missing.
"""

import os
import sys
import django
from django.db import connection
from django.db.utils import OperationalError

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

def check_session_table():
    """Check if django_session table exists and create it if missing."""
    print("Checking for django_session table...")
    
    # Check if django_session table exists
    with connection.cursor() as cursor:
        try:
            cursor.execute("SELECT 1 FROM django_session LIMIT 1;")
            print("✅ django_session table exists.")
            return True
        except OperationalError:
            print("❌ django_session table does not exist.")
            return False

def create_session_table():
    """Create django_session table by running the sessions migration."""
    print("Creating django_session table...")
    
    try:
        # Run just the sessions migration
        from django.core.management import call_command
        call_command('migrate', 'sessions', verbosity=3)
        print("✅ django_session table created successfully.")
        return True
    except Exception as e:
        print(f"❌ Failed to create django_session table: {e}")
        return False

def main():
    """Main function to check and fix the django_session table."""
    if not check_session_table():
        success = create_session_table()
        if success:
            print("Session table fix completed successfully.")
            return 0
        else:
            print("Failed to fix session table.")
            return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())