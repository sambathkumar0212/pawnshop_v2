from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps

class Command(BaseCommand):
    help = 'Creates default roles (groups) for the pawnshop management system'

    def handle(self, *args, **options):
        # Define roles with descriptions and permissions
        roles = [
            {
                'name': 'Administrator',
                'description': 'Full system access with all permissions',
                'permissions': 'all'  # Special case: all permissions
            },
            {
                'name': 'Branch Manager',
                'description': 'Manages branch operations, staff, and reporting',
                'permissions': [
                    # Auth permissions
                    {'app': 'auth', 'model': 'user', 'codenames': ['view', 'add', 'change']},
                    {'app': 'auth', 'model': 'group', 'codenames': ['view']},
                    # Core business permissions
                    {'app': 'loans', 'model': '*', 'codenames': ['view', 'add', 'change', 'delete']},
                    {'app': 'inventory', 'model': '*', 'codenames': ['view', 'add', 'change', 'delete']},
                    {'app': 'customers', 'model': '*', 'codenames': ['view', 'add', 'change', 'delete']},
                    {'app': 'transactions', 'model': '*', 'codenames': ['view', 'add', 'change']},
                    {'app': 'reports', 'model': '*', 'codenames': ['view']},
                    {'app': 'settings', 'model': '*', 'codenames': ['view', 'change']},
                ]
            },
            {
                'name': 'Loan Officer',
                'description': 'Handles pawn loans, valuations, and customer interactions',
                'permissions': [
                    {'app': 'loans', 'model': '*', 'codenames': ['view', 'add', 'change']},
                    {'app': 'inventory', 'model': 'item', 'codenames': ['view', 'add', 'change']},
                    {'app': 'customers', 'model': '*', 'codenames': ['view', 'add', 'change']},
                    {'app': 'transactions', 'model': 'payment', 'codenames': ['view', 'add']},
                ]
            },
            {
                'name': 'Cashier',
                'description': 'Processes payments, buyouts, and basic customer transactions',
                'permissions': [
                    {'app': 'loans', 'model': '*', 'codenames': ['view']},
                    {'app': 'inventory', 'model': 'item', 'codenames': ['view']},
                    {'app': 'customers', 'model': '*', 'codenames': ['view']},
                    {'app': 'transactions', 'model': '*', 'codenames': ['view', 'add']},
                ]
            },
            {
                'name': 'Inventory Manager',
                'description': 'Manages inventory, auctions, and item tracking',
                'permissions': [
                    {'app': 'inventory', 'model': '*', 'codenames': ['view', 'add', 'change', 'delete']},
                    {'app': 'loans', 'model': '*', 'codenames': ['view']},
                ]
            },
            {
                'name': 'Accountant',
                'description': 'Handles financial reports, audits, and accounting tasks',
                'permissions': [
                    {'app': 'transactions', 'model': '*', 'codenames': ['view']},
                    {'app': 'loans', 'model': '*', 'codenames': ['view']},
                    {'app': 'reports', 'model': '*', 'codenames': ['view']},
                ]
            },
            {
                'name': 'Customer Service',
                'description': 'Handles customer inquiries and basic transactions',
                'permissions': [
                    {'app': 'customers', 'model': '*', 'codenames': ['view', 'add', 'change']},
                    {'app': 'loans', 'model': '*', 'codenames': ['view']},
                    {'app': 'transactions', 'model': 'payment', 'codenames': ['view']},
                ]
            },
            {
                'name': 'Appraiser',
                'description': 'Specializes in item valuation and authenticity verification',
                'permissions': [
                    {'app': 'inventory', 'model': 'item', 'codenames': ['view', 'change']},
                    {'app': 'loans', 'model': 'pawnitem', 'codenames': ['view', 'change']},
                ]
            }
        ]

        # Create or update each role
        for role_data in roles:
            role, created = Group.objects.get_or_create(name=role_data['name'])
            
            # Add description to role (if your Group model supports it)
            if hasattr(role, 'description'):
                role.description = role_data['description']
                role.save()
            
            # Clear existing permissions
            role.permissions.clear()
            
            # Handle 'all' permissions special case
            if role_data['permissions'] == 'all':
                all_perms = Permission.objects.all()
                role.permissions.add(*all_perms)
                self.stdout.write(f"Added all {all_perms.count()} permissions to {role.name}")
                continue
                
            # Add specific permissions
            for perm_group in role_data['permissions']:
                app = perm_group['app']
                model = perm_group['model']
                codenames = perm_group['codenames']
                
                # Handle wildcard model case
                if model == '*':
                    # Get all models in the app
                    app_models = [
                        model.__name__.lower() 
                        for model in apps.get_app_config(app).get_models()
                    ]
                    for model_name in app_models:
                        self._add_permissions(role, app, model_name, codenames)
                else:
                    self._add_permissions(role, app, model, codenames)
            
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status} role: {role.name} with {role.permissions.count()} permissions")
    
    def _add_permissions(self, role, app, model, codenames):
        """Helper to add permissions for a specific model"""
        try:
            content_type = ContentType.objects.get(app_label=app, model=model)
            for action in codenames:
                perm_codename = f"{action}_{model}"
                try:
                    perm = Permission.objects.get(content_type=content_type, codename=perm_codename)
                    role.permissions.add(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"Permission {perm_codename} does not exist for {app}.{model}"
                    ))
        except ContentType.DoesNotExist:
            self.stdout.write(self.style.WARNING(
                f"Content type for {app}.{model} does not exist"
            ))