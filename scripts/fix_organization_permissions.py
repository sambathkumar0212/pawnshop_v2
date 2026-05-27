import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.db import transaction
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from accounts.models import Organization, CustomUser, Role, Customer
from branches.models import Branch

def create_organization_permissions():
    """
    Creates default permissions and groups for organizations.
    Ensures all organization users have the minimum required permissions.
    This fixes the 403 Forbidden error for new organization users.
    """
    
    print("\nCreating default permissions for organizations...")
    
    # Create basic permissions groups if they don't exist
    org_admin_group, created = Group.objects.get_or_create(name='Organization Admin')
    branch_manager_group, created = Group.objects.get_or_create(name='Branch Manager')
    staff_group, created = Group.objects.get_or_create(name='Staff')
    
    # Get content types for all relevant models
    customer_ct = ContentType.objects.get_for_model(Customer)
    
    # Basic customer permissions that all staff need
    view_customer = Permission.objects.get(content_type=customer_ct, codename='view_customer')
    add_customer = Permission.objects.get(content_type=customer_ct, codename='add_customer')
    change_customer = Permission.objects.get(content_type=customer_ct, codename='change_customer')
    
    # Add permissions to groups
    staff_group.permissions.add(view_customer, add_customer, change_customer)
    print("Added basic customer permissions to Staff group")
    
    # Make sure all organization users have staff group
    users_updated = 0
    
    for user in CustomUser.objects.filter(organization__isnull=False):
        if not user.groups.filter(name='Staff').exists():
            user.groups.add(staff_group)
            users_updated += 1
    
    print(f"Added {users_updated} organization users to Staff group")
    
    # Create or update roles with correct permissions
    roles_updated = 0
    
    # Basic roles with view permissions
    basic_roles = ['Cashier', 'Appraiser', 'Security', 'Loan Officer', 'Inventory Manager']
    for role_name in basic_roles:
        role, created = Role.objects.get_or_create(name=role_name)
        role.permissions.add(view_customer)
        roles_updated += 1
    
    # Roles that can add/change customers
    customer_roles = ['Sales Associate', 'Customer Service']
    for role_name in customer_roles:
        role, created = Role.objects.get_or_create(name=role_name)
        role.permissions.add(view_customer, add_customer, change_customer)
        roles_updated += 1
    
    print(f"Updated {roles_updated} roles with correct permissions")
    
    # Directly assign permissions to users without roles
    users_fixed = 0
    
    for user in CustomUser.objects.filter(organization__isnull=False):
        if not user.has_perm('accounts.view_customer'):
            user.user_permissions.add(view_customer)
            users_fixed += 1
    
    print(f"Added view_customer permission to {users_fixed} users without it\n")
    
    print("All permissions successfully created and assigned!")
    print("Users should now be able to access customer pages without 403 errors.")

if __name__ == "__main__":
    create_organization_permissions()