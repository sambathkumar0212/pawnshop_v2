#!/usr/bin/env python
"""
Script to check schemes in both content_manager and schemes apps
"""

import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

def check_content_manager_schemes():
    """Check schemes in content_manager app"""
    from content_manager.models import Scheme
    
    print("\n===== Schemes in content_manager app: =====")
    schemes = Scheme.objects.all()
    if schemes:
        for scheme in schemes:
            branch_name = scheme.branch.name if scheme.branch else "Global"
            print(f"- {scheme.name} (Branch: {branch_name}, Active: {scheme.is_active})")
    else:
        print("No schemes found in content_manager app.")
    print(f"Total: {schemes.count()} schemes\n")

def check_schemes_app_schemes():
    """Check schemes in schemes app"""
    try:
        from schemes.models import Scheme
        
        print("===== Schemes in schemes app: =====")
        schemes = Scheme.objects.all()
        if schemes:
            for scheme in schemes:
                branch_name = scheme.branch.name if scheme.branch else "Global"
                status = scheme.status
                print(f"- {scheme.name} (Branch: {branch_name}, Status: {status})")
        else:
            print("No schemes found in schemes app.")
        print(f"Total: {schemes.count()} schemes\n")
    except ImportError:
        print("Could not import Scheme from schemes app. The app might not be installed.")

if __name__ == "__main__":
    check_content_manager_schemes()
    check_schemes_app_schemes()