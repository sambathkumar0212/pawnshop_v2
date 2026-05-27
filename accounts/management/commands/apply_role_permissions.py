from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Role


class Command(BaseCommand):
    help = 'Apply default permissions to all roles based on their role_type'

    def add_arguments(self, parser):
        parser.add_argument(
            '--role-type',
            help='Apply permissions to roles of a specific type only'
        )
        parser.add_argument(
            '--role-id',
            type=int,
            help='Apply permissions to a specific role by ID'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually making changes'
        )

    def handle(self, *args, **options):
        role_type = options.get('role_type')
        role_id = options.get('role_id')
        dry_run = options.get('dry_run')

        # Filter roles if needed
        roles = Role.objects.all()
        if role_type:
            roles = roles.filter(role_type=role_type)
            self.stdout.write(f"Filtering to roles of type: {role_type}")
            
        if role_id:
            roles = roles.filter(id=role_id)
            self.stdout.write(f"Filtering to role with ID: {role_id}")
            
        # Count roles before processing
        total_roles = roles.count()
        self.stdout.write(f"Found {total_roles} roles to process")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: No changes will be made"))
            
        # Process each role
        with transaction.atomic():
            for role in roles:
                old_perms_count = role.permissions.count()
                if not dry_run:
                    role.apply_default_permissions()
                    role.save()
                new_perms_count = role.permissions.count()
                
                self.stdout.write(
                    f"Role: {role.name} ({role.role_type}) - " +
                    f"Permissions: {old_perms_count} → {'would be ' if dry_run else ''}{new_perms_count}"
                )
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Successfully applied default permissions to {total_roles} roles"))
        else:
            self.stdout.write(self.style.WARNING("DRY RUN completed - no changes were made"))