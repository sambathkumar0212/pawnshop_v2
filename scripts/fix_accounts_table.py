#!/usr/bin/env python
"""
Simplified emergency fix script for the accounts_customuser table.
"""
import os
import sys
import django
import traceback

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

def check_table_exists(table_name):
    """Check if a table exists in the database using a simpler query."""
    from django.db import connection
    with connection.cursor() as cursor:
        try:
            # Simple query that works in PostgreSQL and SQLite
            cursor.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
            return True
        except Exception:
            return False

def main():
    """Simplified fix for the accounts_customuser table."""
    print("Performing minimal database check...")
    
    try:
        # Check if user model exists and can be accessed
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Try to access the user table
        User.objects.first()
        print("✅ User model is accessible. Database appears OK.")
        return 0
        
    except Exception as e:
        print(f"⚠️ User model access failed: {e}")
        
        # Apply only essential migrations
        print("Applying core auth migrations...")
        os.system('python manage.py migrate auth --noinput')
        os.system('python manage.py migrate accounts --noinput')
        
        print("Database fix attempted, continuing with startup...")
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Error in fix script: {e}")
        # Always exit with success to not block startup
        sys.exit(0)