#!/usr/bin/env python
"""
Enhanced script to migrate existing pawnshop data to the multi-tenant SaaS organization model.
This script fixes the issue where customers and loans created before implementing
the organization filter are visible to all organizations after signup.

To run this script:
python manage.py shell < scripts/migrate_data_to_organizations_fix.py
"""

import os
import sys
import django
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone
from django.db.models import Q

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

# Import models after Django setup
from accounts.models import Organization, CustomUser, Customer, Region
from branches.models import Branch
from inventory.models import Item, Category
from transactions.models import Loan, Payment, LoanItem, Sale, LoanExtension
from schemes.models import Scheme

# Set up logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def count_unassigned_data():
    """Count data that is not assigned to any organization"""
    users_count = CustomUser.objects.filter(organization__isnull=True).count()
    branches_count = Branch.objects.filter(organization__isnull=True).count()
    customers_count = Customer.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)).count()
    schemes_count = Scheme.objects.filter(organization__isnull=True).count()
    items_count = Item.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)).count()
    loans_count = Loan.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)).count()
    sales_count = Sale.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)).count()
    
    return {
        'users': users_count,
        'branches': branches_count,
        'customers': customers_count,
        'schemes': schemes_count,
        'items': items_count,
        'loans': loans_count,
        'sales': sales_count
    }

def create_legacy_organization():
    """Create a default organization for legacy data"""
    # First, check if we have a superuser to assign as owner
    superuser = CustomUser.objects.filter(is_superuser=True).first()
    
    if not superuser:
        # Create a superuser if none exists
        logger.info("No superuser found. Creating one...")
        superuser = CustomUser.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='ChangeMe123!',
            first_name='System',
            last_name='Admin'
        )
        logger.info(f"Created superuser: {superuser.username}")
    
    # Check if legacy organization already exists
    legacy_org = Organization.objects.filter(Q(name='Legacy System') | Q(slug='legacy-system')).first()
    
    if not legacy_org:
        logger.info("Creating legacy organization...")
        legacy_org = Organization.objects.create(
            name='Legacy System',
            slug='legacy-system',
            owner=superuser,
            plan='enterprise',  # Give it unlimited capabilities
            status='active',
            contact_email=superuser.email,
            contact_phone='',
            max_branches=999999,
            max_users=999999,
            max_customers=999999,
            max_loans=999999,
            enable_biometrics=True,
            subscription_end=timezone.now() + timezone.timedelta(days=365*10)  # 10 years
        )
        logger.info(f"Created legacy organization: {legacy_org.name}")
    else:
        logger.info(f"Using existing legacy organization: {legacy_org.name}")
    
    # Make sure the superuser is part of this organization
    if not superuser.organization:
        superuser.organization = legacy_org
        superuser.is_organization_admin = True
        superuser.save()
        logger.info(f"Associated superuser {superuser.username} with legacy organization")
    
    return legacy_org

@transaction.atomic
def migrate_data_to_organization(legacy_org):
    """Migrate all existing data without organization to the legacy organization"""
    # Step 1: Migrate all regions first if they exist
    regions_updated = 0
    for region in Region.objects.all():
        region.save()
        regions_updated += 1
    
    logger.info(f"Updated {regions_updated} regions")
    
    # Step 2: Migrate branches first
    branches_updated = 0
    for branch in Branch.objects.filter(organization__isnull=True):
        branch.organization = legacy_org
        branch.save()
        branches_updated += 1
    
    logger.info(f"Migrated {branches_updated} branches to legacy organization")
    
    # Step 3: Migrate users
    users_updated = 0
    for user in CustomUser.objects.filter(organization__isnull=True):
        user.organization = legacy_org
        user.save()
        users_updated += 1
    
    logger.info(f"Migrated {users_updated} users to legacy organization")
    
    # Step 4: Migrate schemes
    schemes_updated = 0
    for scheme in Scheme.objects.filter(organization__isnull=True):
        scheme.organization = legacy_org
        scheme.save()
        schemes_updated += 1
    
    logger.info(f"Migrated {schemes_updated} schemes to legacy organization")
    
    # Step 5: Update categories if they exist
    try:
        categories_updated = 0
        for category in Category.objects.filter(organization__isnull=True):
            category.organization = legacy_org
            category.save()
            categories_updated += 1
        
        logger.info(f"Migrated {categories_updated} categories to legacy organization")
    except Exception as e:
        logger.warning(f"Could not migrate categories: {str(e)}")
    
    # Step 6: Update customers - this is critical for fixing the visibility issue
    customers_updated = 0
    orphaned_customers = 0
    
    # Handle customers with no branch or whose branch has no organization
    for customer in Customer.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)):
        # If customer has no branch, assign to first branch of legacy org
        if not customer.branch:
            default_branch = Branch.objects.filter(organization=legacy_org).first()
            if default_branch:
                customer.branch = default_branch
                customer.save()
                customers_updated += 1
            else:
                orphaned_customers += 1
                logger.warning(f"Customer {customer.id} has no branch and no default branch found")
        # If customer has branch but branch has no org, update the branch
        elif customer.branch and not customer.branch.organization:
            customer.branch.organization = legacy_org
            customer.branch.save()
            customers_updated += 1
    
    logger.info(f"Updated {customers_updated} customers, {orphaned_customers} orphaned customers")
    
    # Step 7: Update items - ensure all inventory items are associated with branches that have organizations
    items_updated = 0
    for item in Item.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)):
        if not item.branch:
            default_branch = Branch.objects.filter(organization=legacy_org).first()
            if default_branch:
                item.branch = default_branch
                item.save()
                items_updated += 1
        elif item.branch and not item.branch.organization:
            item.branch.organization = legacy_org
            item.branch.save()
            items_updated += 1
    
    logger.info(f"Updated {items_updated} inventory items")
    
    # Step 8: Update loans - this is the key to fix visibility issues
    loans_updated = 0
    for loan in Loan.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)):
        if not loan.branch:
            default_branch = Branch.objects.filter(organization=legacy_org).first()
            if default_branch:
                loan.branch = default_branch
                loan.save()
                loans_updated += 1
        elif loan.branch and not loan.branch.organization:
            loan.branch.organization = legacy_org
            loan.branch.save()
            loans_updated += 1
    
    logger.info(f"Updated {loans_updated} loans")
    
    # Step 9: Update sales
    sales_updated = 0
    for sale in Sale.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)):
        if not sale.branch:
            default_branch = Branch.objects.filter(organization=legacy_org).first()
            if default_branch:
                sale.branch = default_branch
                sale.save()
                sales_updated += 1
        elif sale.branch and not sale.branch.organization:
            sale.branch.organization = legacy_org
            sale.branch.save()
            sales_updated += 1
    
    logger.info(f"Updated {sales_updated} sales")
    
    # Step 10: Check if any data remains unassigned
    unassigned = count_unassigned_data()
    
    if sum(unassigned.values()) > 0:
        logger.warning("Some data still not assigned to organizations:")
        for data_type, count in unassigned.items():
            if count > 0:
                logger.warning(f"- {data_type}: {count}")
    else:
        logger.info("All data has been successfully assigned to organizations!")
    
    return {
        'branches': branches_updated,
        'users': users_updated,
        'schemes': schemes_updated,
        'customers': customers_updated,
        'items': items_updated,
        'loans': loans_updated,
        'sales': sales_updated
    }

def main():
    """Main function to run the migration"""
    logger.info("Starting data migration to organizations...")
    
    # Check how much data needs migration
    before_counts = count_unassigned_data()
    logger.info("Data without organization assignment:")
    for data_type, count in before_counts.items():
        logger.info(f"- {data_type}: {count}")
    
    if sum(before_counts.values()) == 0:
        logger.info("No data needs migration. All data already has organization assignments.")
        return
    
    # Create or get legacy organization
    legacy_org = create_legacy_organization()
    
    # Migrate data
    migration_results = migrate_data_to_organization(legacy_org)
    
    # Check final state
    after_counts = count_unassigned_data()
    
    logger.info("\nMigration completed!")
    logger.info(f"Legacy organization: {legacy_org.name} (ID: {legacy_org.id})")
    logger.info(f"Data migrated: {migration_results}")
    
    # Check if any data still needs migration
    if sum(after_counts.values()) > 0:
        logger.warning("\nWARNING: Some data still doesn't have organization assignments:")
        for data_type, count in after_counts.items():
            if count > 0:
                logger.warning(f"- {data_type}: {count}")
    else:
        logger.info("\nSUCCESS: All data has been successfully assigned to organizations!")

if __name__ == "__main__":
    main()