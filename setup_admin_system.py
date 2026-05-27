#!/usr/bin/env python
"""
Quick Setup Script for Admin-Only System
This script helps set up the initial admin account with all permissions
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from accounts.models import CustomUser, Role
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


def create_admin_account(username, email, first_name, last_name, password):
    """
    Create admin account with is_pawnshop_admin flag set
    
    Args:
        username: Admin username
        email: Admin email
        first_name: Admin first name
        last_name: Admin last name
        password: Admin password
    """
    try:
        # Check if admin already exists
        if CustomUser.objects.filter(username=username).exists():
            print(f"✗ Admin '{username}' already exists!")
            return False
        
        # Create admin user
        admin_user = CustomUser.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            is_pawnshop_admin=True,  # Set admin flag
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        
        print(f"✓ Admin account created successfully!")
        print(f"  Username: {username}")
        print(f"  Email: {email}")
        print(f"  Name: {first_name} {last_name}")
        print(f"  Admin Flag: {admin_user.is_pawnshop_admin}")
        
        return True
    
    except Exception as e:
        print(f"✗ Error creating admin account: {str(e)}")
        return False


def verify_admin_access(username):
    """Verify admin has proper access and can manage staff"""
    try:
        admin = CustomUser.objects.get(username=username, is_pawnshop_admin=True)
        print(f"✓ Admin '{username}' verification:")
        print(f"  - is_pawnshop_admin: {admin.is_pawnshop_admin}")
        print(f"  - is_superuser: {admin.is_superuser}")
        print(f"  - is_active: {admin.is_active}")
        print(f"  - is_staff: {admin.is_staff}")
        return True
    except CustomUser.DoesNotExist:
        print(f"✗ Admin '{username}' not found!")
        return False


def create_sample_staff(admin_username, staff_username, staff_email, role_name='Cashier'):
    """Create a sample staff account for testing"""
    try:
        admin = CustomUser.objects.get(username=admin_username, is_pawnshop_admin=True)
        
        # Check if staff already exists
        if CustomUser.objects.filter(username=staff_username).exists():
            print(f"✗ Staff '{staff_username}' already exists!")
            return False
        
        # Get role
        try:
            role = Role.objects.get(name__icontains=role_name)
        except Role.DoesNotExist:
            print(f"⚠ Role '{role_name}' not found. Creating with default role...")
            role = Role.objects.first()  # Get any role
        
        # Create staff user
        staff_user = CustomUser.objects.create_user(
            username=staff_username,
            email=staff_email,
            first_name='Sample',
            last_name='Staff',
            password='TempPassword123!',
            role=role,
            is_pawnshop_admin=False,
            is_active=True
        )
        
        print(f"✓ Sample staff account created!")
        print(f"  Username: {staff_username}")
        print(f"  Email: {staff_email}")
        print(f"  Temporary Password: TempPassword123!")
        print(f"  Role: {role.name}")
        print(f"  Admin Flag: {staff_user.is_pawnshop_admin}")
        print(f"\n  Note: Admin should change this password via admin panel")
        
        return True
    
    except CustomUser.DoesNotExist:
        print(f"✗ Admin '{admin_username}' not found!")
        return False
    except Exception as e:
        print(f"✗ Error creating sample staff: {str(e)}")
        return False


def setup_initial_permissions():
    """Ensure all necessary permissions are available"""
    try:
        # This is handled automatically by Django, but we can verify here
        print("✓ Permissions setup is handled automatically by Django")
        return True
    except Exception as e:
        print(f"⚠ Error setting up permissions: {str(e)}")
        return False


def print_admin_urls():
    """Print important admin URLs"""
    print("\n" + "="*60)
    print("IMPORTANT ADMIN URLS")
    print("="*60)
    print(f"Admin Login:              /accounts/login/")
    print(f"Admin Dashboard:          /accounts/admin/dashboard/")
    print(f"Staff List:               /accounts/admin/staff/")
    print(f"Create New Staff:         /accounts/admin/staff/add/")
    print(f"Audit Trail:              /accounts/admin/audit-trail/")
    print(f"Password History:         /accounts/admin/password-history/")
    print(f"Deletion History:         /accounts/admin/deletion-history/")
    print("="*60 + "\n")


def main():
    """Main setup function"""
    print("\n" + "="*60)
    print("PAWNSHOP ADMIN-ONLY SYSTEM SETUP")
    print("="*60 + "\n")
    
    print("Step 1: Creating Admin Account...")
    create_admin_account(
        username='admin',
        email='admin@pawnshop.local',
        first_name='System',
        last_name='Administrator',
        password='AdminPassword123!'
    )
    
    print("\nStep 2: Verifying Admin Access...")
    verify_admin_access('admin')
    
    print("\nStep 3: Setting Up Permissions...")
    setup_initial_permissions()
    
    print("\nStep 4: Creating Sample Staff Account (optional)...")
    create_sample_staff(
        admin_username='admin',
        staff_username='cashier1',
        staff_email='cashier1@pawnshop.local',
        role_name='Cashier'
    )
    
    print_admin_urls()
    
    print("✓ Setup Complete!")
    print("\nNext Steps:")
    print("1. Access the login page: /accounts/login/")
    print("2. Login with username: admin")
    print("3. Password: AdminPassword123!")
    print("4. Go to Admin Dashboard: /accounts/admin/dashboard/")
    print("5. Create more staff accounts from the dashboard")
    print("\nFor more information, see: ADMIN_SYSTEM_DOCUMENTATION.md\n")


if __name__ == '__main__':
    main()
