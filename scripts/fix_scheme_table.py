#!/usr/bin/env python
"""
Fix script for missing additional_conditions column in content_manager_scheme table.
Run this script from the project root directory with:
python scripts/fix_scheme_table.py
"""
import os
import sys
import sqlite3
import traceback

# Add the project directory to the path so Django can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up Django environment
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.db import connection

def check_column_exists(table, column):
    """Check if a column exists in a table"""
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [info[1] for info in cursor.fetchall()]
        return column in columns

def fix_scheme_table():
    """Add missing additional_conditions column to content_manager_scheme table"""
    try:
        if not check_column_exists('content_manager_scheme', 'additional_conditions'):
            with connection.cursor() as cursor:
                # Add the column with default value as empty JSON object
                cursor.execute("ALTER TABLE content_manager_scheme ADD COLUMN additional_conditions TEXT DEFAULT '{}' NOT NULL;")
                print("✅ Successfully added additional_conditions column to content_manager_scheme table")
        else:
            print("✅ Column additional_conditions already exists in content_manager_scheme table")
        return True
    except Exception as e:
        print(f"❌ Error fixing content_manager_scheme table: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔍 Checking content_manager_scheme table...")
    if fix_scheme_table():
        print("✅ Script completed successfully")
    else:
        print("❌ Script completed with errors")
        sys.exit(1)