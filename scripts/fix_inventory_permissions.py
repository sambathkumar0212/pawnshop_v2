import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.db import transaction
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from accounts.models import CustomUser, Role
from inventory.models import Item

def fix_inventory_permissions():
    """
    Grant inventory view permissions to all active users.
    This ensures that all users can access the inventory page.
    """
    print("\nFixing inventory permissions for all users...")
    
    # Get the 'view_item' permission
    content_type = ContentType.objects.get_for_model(Item)
    view_item_permission = Permission.objects.get(
        content_type=content_type,
        codename='view_item'
    )
    
    # Count of users updated
    users_updated = 0
    
    # Update all active users
    with transaction.atomic():
        for user in CustomUser.objects.filter(is_active=True):
            # Skip if user already has the permission
            if user.has_perm('inventory.view_item'):
                continue
                
            # Add permission to user
            user.user_permissions.add(view_item_permission)
            users_updated += 1
    
    print(f"Added inventory view permissions to {users_updated} users")
    
    # Now ensure all roles have this permission
    roles_updated = 0
    with transaction.atomic():
        for role in Role.objects.all():
            if not role.has_permission('view_item'):
                role.add_permissions('view_item')
                roles_updated += 1
    
    print(f"Added inventory view permissions to {roles_updated} roles")
    print("Inventory permissions fixed successfully!")

if __name__ == "__main__":
    fix_inventory_permissions()