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


def fix_organization_branch_permissions():
    """
    Fix permissions for organization users to be able to create branches.
    """
    print("\nFixing branch permissions for organization users...")
    
    # Get the content type for Branch model
    branch_content_type = ContentType.objects.get_for_model(Branch)
    
    # Get branch permissions
    view_branch = Permission.objects.get(content_type=branch_content_type, codename='view_branch')
    add_branch = Permission.objects.get(content_type=branch_content_type, codename='add_branch')
    change_branch = Permission.objects.get(content_type=branch_content_type, codename='change_branch')
    
    # Create or get the Organization Admin group
    org_admin_group, created = Group.objects.get_or_create(name='Organization Admin')
    
    # Add branch permissions to Organization Admin group
    org_admin_group.permissions.add(view_branch, add_branch, change_branch)
    print("Added branch permissions to Organization Admin group")
    
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
            
            # Also directly grant the branch permissions
            user.user_permissions.add(view_branch, add_branch, change_branch)
    
    print(f"Added {users_updated} organization administrators to Organization Admin group")
    
    # Update organization owners directly
    owners_updated = 0
    for org in Organization.objects.all():
        if org.owner:
            org.owner.user_permissions.add(view_branch, add_branch, change_branch)
            owners_updated += 1
    
    print(f"Granted branch permissions to {owners_updated} organization owners")
    
    print("Branch permissions fixed successfully!")


if __name__ == "__main__":
    fix_organization_branch_permissions()