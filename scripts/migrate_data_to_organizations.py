#!/usr/bin/env python
"""
Script to migrate existing pawnshop data to the multi-tenant SaaS organization model.
This will ensure that data created before the SaaS implementation is properly isolated
and not visible to new organizations.

To run this script:
python manage.py shell < scripts/migrate_data_to_organizations.py
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
from accounts.models import Organization, CustomUser, Customer
from branches.models import Branch
from inventory.models import Item, Category
from transactions.models import Loan, Sale
from schemes.models import Scheme

# Set up logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def count_unassigned_data():
    """Count data that is not assigned to any organization"""
    users_count = CustomUser.objects.filter(organization__isnull=True).count()
    branches_count = Branch.objects.filter(organization__isnull=True).count()
    customers_count = Customer.objects.filter(branch__organization__isnull=True).count()
    schemes_count = Scheme.objects.filter(organization__isnull=True).count()
    items_count = Item.objects.filter(branch__organization__isnull=True).count()
    loans_count = Loan.objects.filter(branch__organization__isnull=True).count()
    sales_count = Sale.objects.filter(branch__organization__isnull=True).count()
    
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
    # Step 1: Migrate branches first
    branches_updated = 0
    for branch in Branch.objects.filter(organization__isnull=True):
        branch.organization = legacy_org
        branch.save()
        branches_updated += 1
    
    logger.info(f"Migrated {branches_updated} branches to legacy organization")
    
    # Step 2: Migrate users
    users_updated = 0
    for user in CustomUser.objects.filter(organization__isnull=True):
        user.organization = legacy_org
        user.save()
        users_updated += 1
    
    logger.info(f"Migrated {users_updated} users to legacy organization")
    
    # Step 3: Migrate schemes
    schemes_updated = 0
    for scheme in Scheme.objects.filter(organization__isnull=True):
        scheme.organization = legacy_org
        scheme.save()
        schemes_updated += 1
    
    logger.info(f"Migrated {schemes_updated} schemes to legacy organization")
    
    # Step 4: Update categories if they exist
    try:
        categories_updated = 0
        for category in Category.objects.filter(organization__isnull=True):
            category.organization = legacy_org
            category.save()
            categories_updated += 1
        
        logger.info(f"Migrated {categories_updated} categories to legacy organization")
    except Exception as e:
        logger.warning(f"Could not migrate categories: {str(e)}")
    
    # Step 5: Check if any data remains unassigned
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
        'schemes': schemes_updated
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