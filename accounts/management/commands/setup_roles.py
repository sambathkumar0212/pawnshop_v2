from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from accounts.models import Role
from accounts.permissions import get_role_permissions


class Command(BaseCommand):
    help = _('Creates default roles and permissions for the pawnshop system')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up default roles and permissions'))
        
        # Get all default permissions for roles
        role_permissions = get_role_permissions()
        
        with transaction.atomic():
            # Create each role type
            for role_type, permissions_list in role_permissions.items():
                # Determine role category based on role type
                if role_type in [Role.BRANCH_MANAGER, Role.REGIONAL_MANAGER]:
                    category = Role.MANAGEMENT
                elif role_type in [Role.LOAN_OFFICER, Role.APPRAISER, Role.CASHIER]:
                    category = Role.FRONTLINE
                elif role_type in [Role.SECURITY, Role.INVENTORY_MANAGER, Role.CUSTOMER_SERVICE]:
                    category = Role.SUPPORT
                else:
                    category = Role.HEADOFFICE
                
                # Get or create role
                role, created = Role.objects.get_or_create(
                    role_type=role_type,
                    defaults={
                        'name': dict(Role.ROLE_TYPE_CHOICES)[role_type],
                        'category': category
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created new role: {role.name}'))
                else:
                    self.stdout.write(f'Role already exists: {role.name}')
                
                # Get permissions for this role
                if permissions_list:
                    # Find permissions by codename
                    db_permissions = Permission.objects.filter(codename__in=permissions_list)
                    
                    # Count permissions found vs expected
                    found_count = db_permissions.count()
                    expected_count = len(permissions_list)
                    
                    if found_count < expected_count:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Found only {found_count}/{expected_count} '
                                f'permissions for {role.name}'
                            )
                        )
                        
                        # Show missing permissions
                        found_codenames = set(db_permissions.values_list('codename', flat=True))
                        missing = set(permissions_list) - found_codenames
                        if missing:
                            self.stdout.write(
                                self.style.WARNING(f'Missing permissions: {", ".join(missing)}')
                            )
                    
                    # Assign permissions to the role
                    role.permissions.set(db_permissions)
                    self.stdout.write(
                        self.style.SUCCESS(f'Assigned {db_permissions.count()} permissions to {role.name}')
                    )
            
            self.stdout.write(self.style.SUCCESS('Successfully set up all roles and permissions'))