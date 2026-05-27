#!/usr/bin/env python
"""
Script to update existing loans that reference content_manager.Scheme to use schemes.Scheme instead.
Run this after migrate_content_manager_to_schemes.py to ensure all loans are properly mapped.
"""

import os
import sys
import django
from django.db import connection

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

def update_loan_schemes():
    """
    Update loans that reference content_manager.Scheme to use schemes.Scheme instead.
    """
    print("\nStarting loan scheme update process...")
    
    try:
        from transactions.models import Loan
        from schemes.models import Scheme
        
        # Check if the loans table has a scheme_id column that points to content_manager_scheme
        # We need to use a raw query to inspect the database structure
        with connection.cursor() as cursor:
            # Get the database type
            db_engine = connection.vendor
            
            if db_engine == 'sqlite':
                # SQLite query to check foreign key constraint
                cursor.execute("""
                    SELECT sql FROM sqlite_master 
                    WHERE type='table' AND name='transactions_loan';
                """)
                table_def = cursor.fetchone()[0]
                print("Table definition:", table_def)
                
                # Check if both content_manager_scheme and schemes_scheme tables exist
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND (name='content_manager_scheme' OR name='schemes_scheme');
                """)
                schema_tables = cursor.fetchall()
                schema_table_names = [table[0] for table in schema_tables]
                
                print(f"Found schema tables: {', '.join(schema_table_names)}")
                
                if 'content_manager_scheme' not in schema_table_names:
                    print("content_manager_scheme table not found. No need to update loans.")
                    return
                    
                # Get the name of the foreign key column referencing scheme
                cursor.execute("""
                    PRAGMA foreign_key_list(transactions_loan);
                """)
                fk_info = cursor.fetchall()
                scheme_column = None
                
                for fk in fk_info:
                    if 'content_manager_scheme' in fk or 'scheme' in fk:
                        scheme_column = fk[3]  # Column name is usually at index 3
                        print(f"Found scheme foreign key column: {scheme_column}")
                        break
                
                if not scheme_column:
                    print("No scheme foreign key found in transactions_loan. No update needed.")
                    return
            else:
                # For PostgreSQL, MySQL, etc.
                print(f"Database engine: {db_engine}")
                print("Using model-based approach for non-SQLite databases")
                scheme_column = "scheme_id"  # Default column name
            
            # Get all loans with a scheme
            loans_with_scheme = Loan.objects.filter(scheme__isnull=False)
            print(f"Found {loans_with_scheme.count()} loans with schemes.")
            
            updated_count = 0
            skipped_count = 0
            
            # Update each loan
            for loan in loans_with_scheme:
                try:
                    # Get the scheme name from the current scheme
                    scheme_name = loan.scheme.name
                    branch = loan.branch
                    
                    # Find the corresponding scheme in the schemes app
                    new_scheme = Scheme.objects.filter(name=scheme_name)
                    
                    # If branch-specific scheme exists, use it; otherwise use global scheme
                    if branch:
                        branch_scheme = new_scheme.filter(branch=branch).first()
                        if branch_scheme:
                            new_scheme = branch_scheme
                        else:
                            new_scheme = new_scheme.filter(branch__isnull=True).first() or new_scheme.first()
                    else:
                        new_scheme = new_scheme.first()
                    
                    if new_scheme:
                        # Store old scheme info for logging
                        old_scheme_id = loan.scheme.id
                        old_scheme_name = loan.scheme.name
                        
                        # Update loan to use new scheme
                        loan.scheme = new_scheme
                        loan.save(update_fields=['scheme'])
                        
                        print(f"  Updated loan #{loan.id}: Scheme changed from {old_scheme_name} (id:{old_scheme_id}) to {new_scheme.name} (id:{new_scheme.id})")
                        updated_count += 1
                    else:
                        print(f"  WARNING: Could not find matching scheme '{scheme_name}' for loan #{loan.id}. Skipping.")
                        skipped_count += 1
                        
                except Exception as e:
                    print(f"  ERROR: Failed to update loan #{loan.id}: {str(e)}")
                    skipped_count += 1
            
            print("\nLoan scheme update complete!")
            print(f"Updated: {updated_count}, Skipped: {skipped_count}")
            
    except ImportError as e:
        print(f"Import error: {str(e)}")
        print("Make sure both transactions and schemes apps are properly installed.")
    except Exception as e:
        print(f"Error updating loan schemes: {str(e)}")

if __name__ == "__main__":
    update_loan_schemes()