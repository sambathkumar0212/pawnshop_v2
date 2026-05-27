from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Customer
from branches.models import Branch


class Command(BaseCommand):
    help = 'Move customers without a branch to the default (first) branch'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--default-branch-id',
            type=int,
            help='Specific branch ID to use as default (if not provided, uses the first branch)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        default_branch_id = options.get('default_branch_id')

        # Get the default branch
        try:
            if default_branch_id:
                default_branch = Branch.objects.get(id=default_branch_id)
                self.stdout.write(f"Using specified branch: {default_branch.name} (ID: {default_branch.id})")
            else:
                default_branch = Branch.objects.first()
                if not default_branch:
                    self.stdout.write(
                        self.style.ERROR('No branches found in the database. Please create at least one branch first.')
                    )
                    return
                self.stdout.write(f"Using first branch as default: {default_branch.name} (ID: {default_branch.id})")
        except Branch.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Branch with ID {default_branch_id} does not exist.')
            )
            return

        # Find customers without a branch
        customers_without_branch = Customer.objects.filter(branch__isnull=True)
        count = customers_without_branch.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('All customers already have a branch assigned. No action needed.')
            )
            return

        self.stdout.write(f"Found {count} customers without a branch assignment:")

        # List customers that will be affected
        for customer in customers_without_branch:
            self.stdout.write(f"  - {customer.full_name} (ID: {customer.id}) - Phone: {customer.phone}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'\nDRY RUN: Would assign {count} customers to branch "{default_branch.name}"')
            )
            return

        # Confirm action
        confirm = input(f'\nDo you want to assign these {count} customers to branch "{default_branch.name}"? (y/N): ')
        if confirm.lower() != 'y':
            self.stdout.write('Operation cancelled.')
            return

        # Update customers in a transaction
        try:
            with transaction.atomic():
                updated_count = customers_without_branch.update(branch=default_branch)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully assigned {updated_count} customers to branch "{default_branch.name}"'
                    )
                )

                # Log the assignment for each customer
                for customer in Customer.objects.filter(branch=default_branch).filter(
                    id__in=customers_without_branch.values_list('id', flat=True)
                ):
                    self.stdout.write(f"  ✓ {customer.full_name} → {default_branch.name}")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error updating customers: {str(e)}')
            )
            return

        # Final verification
        remaining_customers_without_branch = Customer.objects.filter(branch__isnull=True).count()
        if remaining_customers_without_branch == 0:
            self.stdout.write(
                self.style.SUCCESS('\n✓ All customers now have a branch assigned!')
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠ Warning: {remaining_customers_without_branch} customers still without a branch'
                )
            )

        # Show branch statistics
        self.stdout.write('\nBranch Statistics:')
        for branch in Branch.objects.all():
            customer_count = branch.customers.count()
            self.stdout.write(f"  {branch.name}: {customer_count} customers")