from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import Permission
from accounts.models import Role
from accounts.permissions import get_role_permissions
from django.db import transaction

class Command(BaseCommand):
    help = 'Sets up default roles with appropriate permissions'

    def handle(self, *args, **options):
        self.stdout.write('Setting up default roles...')
        role_permissions = get_role_permissions()
        
        # Define default roles with their attributes
        default_roles = [
            {
                'name': 'Branch Manager',
                'role_type': 'branch_manager',
                'category': 'management',
                'description': 'Manages branch operations, staff, and has full control over branch-level activities'
            },
            {
                'name': 'Regional Manager',
                'role_type': 'regional_manager',
                'category': 'management',
                'description': 'Oversees multiple branches in a region, manages branch managers, and regional policies'
            },
            {
                'name': 'Loan Officer',
                'role_type': 'loan_officer',
                'category': 'frontline',
                'description': 'Handles loan applications, appraisals, and customer interactions for pawning'
            },
            {
                'name': 'Senior Appraiser',
                'role_type': 'appraiser',
                'category': 'frontline',
                'description': 'Expert in valuation of items, particularly jewelry and precious metals'
            },
            {
                'name': 'Cashier',
                'role_type': 'cashier',
                'category': 'frontline',
                'description': 'Handles cash transactions, payments, and basic customer service'
            },
            {
                'name': 'Inventory Manager',
                'role_type': 'inventory_manager',
                'category': 'support',
                'description': 'Manages and tracks pawned items, maintains inventory records'
            },
            {
                'name': 'Customer Service Representative',
                'role_type': 'customer_service',
                'category': 'frontline',
                'description': 'Handles customer inquiries, complaints, and general assistance'
            },
            {
                'name': 'Security Officer',
                'role_type': 'security',
                'category': 'support',
                'description': 'Maintains security of premises, staff, customers, and valuable items'
            },
            {
                'name': 'Finance Manager',
                'role_type': 'finance_manager',
                'category': 'headoffice',
                'description': 'Manages financial operations, reporting, and compliance'
            },
            {
                'name': 'IT Administrator',
                'role_type': 'it_admin',
                'category': 'headoffice',
                'description': 'Manages system access, technical infrastructure, and software maintenance'
            },
            {
                'name': 'Compliance Officer',
                'role_type': 'compliance_officer',
                'category': 'headoffice',
                'description': 'Ensures regulatory compliance, audits operations, and maintains policies'
            }
        ]
        
        # Create or update roles
        with transaction.atomic():
            for role_data in default_roles:
                role, created = Role.objects.update_or_create(
                    name=role_data['name'],
                    defaults={
                        'role_type': role_data['role_type'],
                        'category': role_data['category'],
                        'description': role_data['description']
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created new role: {role.name}'))
                else:
                    self.stdout.write(f'Updated existing role: {role.name}')
                
                # Apply permissions based on role type
                if role.role_type in role_permissions:
                    permission_codenames = role_permissions[role.role_type]
                    permissions = Permission.objects.filter(codename__in=permission_codenames)
                    
                    # Clear existing permissions and set new ones
                    role.permissions.clear()
                    role.permissions.add(*permissions)
                    
                    self.stdout.write(
                        f'Applied {permissions.count()} permissions to {role.name}'
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'No default permissions found for role type: {role.role_type}'
                        )
                    )
        
        self.stdout.write(self.style.SUCCESS('Successfully set up all default roles!'))