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
from accounts.models import Organization, CustomUser, Role
from branches.models import Branch
from schemes.models import Scheme


def fix_organization_admin_permissions():
    """
    Fix all permissions for organization owners/admins to properly access and manage:
    - Roles
    - Users
    - Branches
    - Schemes
    This ensures that newly signed-up organization admins can properly manage their organization.
    """
    print("\nFixing permissions for organization owners and administrators...")
    
    # Get content types for all relevant models
    branch_content_type = ContentType.objects.get_for_model(Branch)
    role_content_type = ContentType.objects.get_for_model(Role)
    user_content_type = ContentType.objects.get_for_model(CustomUser)
    scheme_content_type = ContentType.objects.get_for_model(Scheme)
    
    # Get branch permissions
    branch_permissions = Permission.objects.filter(content_type=branch_content_type)
    
    # Get role permissions
    role_permissions = Permission.objects.filter(content_type=role_content_type)
    
    # Get user permissions (limited set appropriate for org admins)
    user_permissions = Permission.objects.filter(
        content_type=user_content_type,
        codename__in=['view_customuser', 'add_customuser', 'change_customuser']
    )
    
    # Get scheme permissions
    scheme_permissions = Permission.objects.filter(content_type=scheme_content_type)
    
    # Collect all permissions
    all_permissions = list(branch_permissions) + list(role_permissions) + list(user_permissions) + list(scheme_permissions)
    
    # Create or get the Organization Admin group
    org_admin_group, created = Group.objects.get_or_create(name='Organization Admin')
    
    # Add all permissions to Organization Admin group
    for permission in all_permissions:
        org_admin_group.permissions.add(permission)
    
    print(f"Added {len(all_permissions)} permissions to Organization Admin group")
    
    # Find organization owners and administrators and add them to the Organization Admin group
    users_updated = 0
    
    for user in CustomUser.objects.filter(organization__isnull=False):
        # Check if user is an organization owner or has an admin role
        is_owner = hasattr(user, 'organization') and user.organization and user.organization.owner == user
        is_admin = hasattr(user, 'role') and user.role and user.role.name.lower() in ['admin', 'administrator', 'owner']
        
        if is_owner or is_admin:
            # Add user to Organization Admin group
            if not user.groups.filter(name='Organization Admin').exists():
                user.groups.add(org_admin_group)
                users_updated += 1
            
            # Also directly grant the permissions
            for permission in all_permissions:
                user.user_permissions.add(permission)
    
    print(f"Added {users_updated} organization administrators to Organization Admin group")
    
    # Update organization owners directly
    owners_updated = 0
    for org in Organization.objects.all():
        if org.owner:
            for permission in all_permissions:
                org.owner.user_permissions.add(permission)
            owners_updated += 1
    
    print(f"Granted permissions to {owners_updated} organization owners")
    
    print("Organization admin permissions fixed successfully!")


if __name__ == "__main__":
    fix_organization_admin_permissions()