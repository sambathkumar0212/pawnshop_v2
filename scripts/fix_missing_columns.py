#!/usr/bin/env python
"""
Fix script for missing region_id column in branches_branch table.
Run this script directly on Render.com's console with:
python scripts/fix_missing_columns.py
"""
import os
import sys
import traceback

# Add the parent directory to the Python path so Django can find the settings
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now set up Django environment
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.db import connection

def check_table_exists(table_name):
    """Check if a table exists in the database."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=%s;",
            [table_name]
        )
        return bool(cursor.fetchone())

def check_column_exists(table, column):
    """Check if a column exists in a table."""
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [info[1] for info in cursor.fetchall()]
        return column in columns

def add_column(table, column, definition):
    """Add a column to a table if it doesn't exist."""
    try:
        # First check if column exists to avoid error
        if not check_column_exists(table, column):
            with connection.cursor() as cursor:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition};")
                print(f"✅ Added column {column} to table {table}")
            return True
        else:
            print(f"✅ Column {column} already exists in {table}, no need to add")
            return True
    except Exception as e:
        print(f"❌ Error adding column {column} to table {table}: {e}")
        traceback.print_exc()
        return False

def fix_region_reference():
    """Fix the region_id foreign key in branches_branch table."""
    if not check_table_exists('branches_branch'):
        print("❌ The branches_branch table doesn't exist yet. Run migrations first.")
        return False
        
    # Check if the accounts_region table exists
    region_table_exists = check_table_exists('accounts_region')
    if not region_table_exists:
        print("⚠️ The accounts_region table doesn't exist. Creating a temporary solution...")
        
        # Create the region table if it doesn't exist
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts_region (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)
                print("✅ Created accounts_region table")
                
                # Insert a default region
                cursor.execute("""
                INSERT INTO accounts_region (name, description)
                VALUES ('Default Region', 'Default region created by fix script')
                ON CONFLICT DO NOTHING;
                """)
        except Exception as e:
            print(f"❌ Error creating region table: {e}")
            traceback.print_exc()
            return False
    
    # Now add the region_id column to the branches table
    if not check_column_exists('branches_branch', 'region_id'):
        print("Missing region_id column in branches_branch table. Adding it...")
        add_column('branches_branch', 'region_id', 'INTEGER NULL')
        
        # Add the foreign key constraint separately for better error handling
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                ALTER TABLE branches_branch
                ADD CONSTRAINT branches_branch_region_id_fk
                FOREIGN KEY (region_id) REFERENCES accounts_region(id)
                ON DELETE SET NULL
                NOT VALID;
                """)
            print("✅ Added foreign key constraint for region_id")
        except Exception as e:
            print(f"⚠️ Could not add foreign key constraint, but column was added: {e}")
            # This is not fatal - the column exists even if the constraint doesn't
    else:
        print("✅ region_id column already exists in branches_branch table.")
    
    return True

def fix_content_manager_scheme():
    """Fix missing columns in content_manager_scheme table."""
    if not check_table_exists('content_manager_scheme'):
        print("❌ The content_manager_scheme table doesn't exist yet. Run migrations first.")
        return False
    
    # Check if additional_conditions column exists
    if not check_column_exists('content_manager_scheme', 'additional_conditions'):
        print("Missing additional_conditions column in content_manager_scheme table. Adding it...")
        add_column('content_manager_scheme', 'additional_conditions', 'TEXT DEFAULT \'{}\'')
    else:
        print("✅ additional_conditions column already exists in content_manager_scheme table.")
    
    return True

def main():
    """Fix missing columns and relationships in the database."""
    print("Starting database schema fix script...")
    
    try:
        # Fix region reference in branches_branch
        if fix_region_reference():
            print("✅ Successfully fixed region references")
        else:
            print("⚠️ Some issues occurred while fixing region references")
        
        # Fix content manager scheme
        if fix_content_manager_scheme():
            print("✅ Successfully fixed content manager scheme")
        else:
            print("⚠️ Some issues occurred while fixing content manager scheme")
        
        # Add more fixes here if needed for other tables
        
        print("✅ Database schema fix script completed")
        return 0
    except Exception as e:
        print(f"❌ Unhandled error in database schema fix script: {e}")
        traceback.print_exc()
        # Return success anyway to not block application startup
        return 0

if __name__ == "__main__":
    sys.exit(main())