from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from accounts.models import Organization

User = get_user_model()


class Command(BaseCommand):
    help = 'Setup super admin functionality for organization management'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a new superuser account',
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the superuser',
            default='superadmin'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email for the superuser',
            default='superadmin@example.com'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for the superuser',
            default='SuperAdmin123!'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up Super Admin functionality...'))
        
        if options['create_superuser']:
            self.create_superuser(options)
        
        self.display_access_info()
        
        self.stdout.write(self.style.SUCCESS('\nSuper Admin setup completed successfully!'))

    def create_superuser(self, options):
        """Create a superuser account"""
        username = options['username']
        email = options['email']
        password = options['password']
        
        # Check if superuser already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Superuser "{username}" already exists. Skipping creation.')
            )
            return
        
        try:
            with transaction.atomic():
                superuser = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    first_name='Super',
                    last_name='Admin'
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created superuser: {username}')
                )
                self.stdout.write(f'  Email: {email}')
                self.stdout.write(f'  Password: {password}')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {str(e)}')
            )

    def display_access_info(self):
        """Display information about accessing super admin features"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUPER ADMIN ACCESS INFORMATION'))
        self.stdout.write('='*60)
        
        # Count organizations
        total_orgs = Organization.objects.count()
        active_orgs = Organization.objects.filter(status='active').count()
        suspended_orgs = Organization.objects.filter(status='suspended').count()
        
        self.stdout.write(f'\nCurrent System Status:')
        self.stdout.write(f'  Total Organizations: {total_orgs}')
        self.stdout.write(f'  Active Organizations: {active_orgs}')
        self.stdout.write(f'  Suspended Organizations: {suspended_orgs}')
        
        self.stdout.write(f'\nSuper Admin URLs:')
        self.stdout.write(f'  Dashboard: /accounts/superadmin/')
        self.stdout.write(f'  Organization Management: /accounts/superadmin/organizations/')
        self.stdout.write(f'  Django Admin: /admin/')
        
        self.stdout.write(f'\nFeatures Available:')
        self.stdout.write(f'  ✓ View all organizations with detailed statistics')
        self.stdout.write(f'  ✓ Suspend/Reactivate organizations (disables all users)')
        self.stdout.write(f'  ✓ Permanently delete organizations and all data')
        self.stdout.write(f'  ✓ Search and filter organizations')
        self.stdout.write(f'  ✓ View organization details and activity')
        self.stdout.write(f'  ✓ Enhanced Django admin interface')
        
        self.stdout.write(f'\nSafety Features:')
        self.stdout.write(f'  ✓ Multiple confirmation steps for deletion')
        self.stdout.write(f'  ✓ Activity logging for all admin actions')
        self.stdout.write(f'  ✓ Detailed impact assessment before deletion')
        self.stdout.write(f'  ✓ Only superusers can access these features')
        
        # Show superusers
        superusers = User.objects.filter(is_superuser=True)
        if superusers.exists():
            self.stdout.write(f'\nExisting Superusers:')
            for user in superusers:
                self.stdout.write(f'  - {user.username} ({user.email})')
        else:
            self.stdout.write(
                self.style.WARNING('\nNo superusers found! Run with --create-superuser to create one.')
            )