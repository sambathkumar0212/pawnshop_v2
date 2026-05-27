#!/usr/bin/env python
"""
Script to migrate existing pawnshop data to the Theni organization and Tamil R Gold Loan branch.
This will ensure that data created before the SaaS implementation is properly assigned
to the specific organization and branch, and only accessible to older users.

To run this script:
python manage.py shell < scripts/migrate_to_theni_organization.py
"""

import os
import sys
import django
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone
from django.db.models import Q
import datetime

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

# Import models after Django setup
from accounts.models import Organization, CustomUser, Customer, Region
from branches.models import Branch, BranchSettings
from inventory.models import Item, Category
from transactions.models import Loan, Payment, LoanItem, Sale, LoanExtension
from schemes.models import Scheme

# Set up logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the cutoff date - users created before this date are considered "old users"
CUTOFF_DATE = timezone.now().date()  # Today's date (August 3, 2025)

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

def create_theni_organization_and_branch():
    """Create the Theni organization and Tamil R Gold Loan branch"""
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
    
    # Check if Theni organization already exists
    theni_org = Organization.objects.filter(Q(name='Theni') | Q(slug='theni')).first()
    
    if not theni_org:
        logger.info("Creating Theni organization...")
        theni_org = Organization.objects.create(
            name='Theni',
            slug='theni',
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
        logger.info(f"Created Theni organization: {theni_org.name}")
    else:
        logger.info(f"Using existing Theni organization: {theni_org.name}")
    
    # Make sure the superuser is part of this organization
    if not superuser.organization:
        superuser.organization = theni_org
        superuser.is_organization_admin = True
        superuser.save()
        logger.info(f"Associated superuser {superuser.username} with Theni organization")
    
    # Create or get the Tamil R Gold Loan branch
    tamil_r_branch = Branch.objects.filter(name='Tamil R Gold Loan').first()
    
    if not tamil_r_branch:
        logger.info("Creating Tamil R Gold Loan branch...")
        tamil_r_branch = Branch.objects.create(
            name='Tamil R Gold Loan',
            address='Main Street',
            city='Theni',
            state='Tamil Nadu',
            zip_code='625531',
            phone='+91 9876543210',
            email='tamilr@goldloan.com',
            organization=theni_org,
            is_active=True,
            opening_time='09:00',
            closing_time='18:00'
        )
        logger.info(f"Created Tamil R Gold Loan branch: {tamil_r_branch.name}")
        
        # Create branch settings
        BranchSettings.objects.create(
            branch=tamil_r_branch,
            max_loan_amount=1000000.00,  # 10 lakhs
            default_interest_rate=12.00,
            loan_duration_days=90,
            grace_period_days=30,
            allow_online_payments=True,
            require_id_verification=True,
            enable_face_recognition=True,
            enable_email_notifications=True,
            enable_sms_notifications=True,
            auction_delay_days=30
        )
        logger.info("Created settings for Tamil R Gold Loan branch")
    else:
        # Update the branch to ensure it's part of the Theni organization
        if tamil_r_branch.organization != theni_org:
            tamil_r_branch.organization = theni_org
            tamil_r_branch.save()
            logger.info(f"Updated Tamil R Gold Loan branch to be part of Theni organization")
        else:
            logger.info(f"Using existing Tamil R Gold Loan branch")
    
    return theni_org, tamil_r_branch

@transaction.atomic
def migrate_data_to_theni(theni_org, tamil_r_branch):
    """Migrate all existing data to the Theni organization and Tamil R Gold Loan branch"""
    # Step 1: Migrate all regions if they exist
    regions_updated = 0
    for region in Region.objects.all():
        region.save()
        regions_updated += 1
    
    logger.info(f"Updated {regions_updated} regions")
    
    # Step 2: Migrate branches that need to be part of the Theni organization
    branches_updated = 0
    for branch in Branch.objects.filter(organization__isnull=True):
        branch.organization = theni_org
        branch.save()
        branches_updated += 1
    
    logger.info(f"Migrated {branches_updated} branches to Theni organization")
    
    # Step 3: Migrate users created before the cutoff date
    users_updated = 0
    for user in CustomUser.objects.filter(
        Q(organization__isnull=True) & 
        Q(date_joined__date__lt=CUTOFF_DATE)
    ):
        user.organization = theni_org
        user.branch = tamil_r_branch
        user.save()
        users_updated += 1
    
    logger.info(f"Migrated {users_updated} users to Theni organization and Tamil R Gold Loan branch")
    
    # Step 4: Migrate schemes
    schemes_updated = 0
    for scheme in Scheme.objects.filter(organization__isnull=True):
        scheme.organization = theni_org
        scheme.save()
        schemes_updated += 1
    
    logger.info(f"Migrated {schemes_updated} schemes to Theni organization")
    
    # Step 5: Update categories if they exist
    try:
        categories_updated = 0
        for category in Category.objects.filter(organization__isnull=True):
            category.organization = theni_org
            category.save()
            categories_updated += 1
        
        logger.info(f"Migrated {categories_updated} categories to Theni organization")
    except Exception as e:
        logger.warning(f"Could not migrate categories: {str(e)}")
    
    # Step 6: Update customers - assign to Tamil R Gold Loan branch
    customers_updated = 0
    
    # Handle customers with no branch or whose branch has no organization
    for customer in Customer.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)):
        # Assign to Tamil R Gold Loan branch
        customer.branch = tamil_r_branch
        customer.save()
        customers_updated += 1
    
    logger.info(f"Updated {customers_updated} customers to Tamil R Gold Loan branch")
    
    # Step 7: Update items - assign to Tamil R Gold Loan branch
    items_updated = 0
    for item in Item.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)):
        item.branch = tamil_r_branch
        item.save()
        items_updated += 1
    
    logger.info(f"Updated {items_updated} inventory items to Tamil R Gold Loan branch")
    
    # Step 8: Update loans - assign to Tamil R Gold Loan branch
    loans_updated = 0
    for loan in Loan.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)):
        loan.branch = tamil_r_branch
        loan.save()
        loans_updated += 1
    
    logger.info(f"Updated {loans_updated} loans to Tamil R Gold Loan branch")
    
    # Step 9: Update sales - assign to Tamil R Gold Loan branch
    sales_updated = 0
    for sale in Sale.objects.filter(Q(branch__isnull=True) | Q(branch__organization__isnull=True)):
        sale.branch = tamil_r_branch
        sale.save()
        sales_updated += 1
    
    logger.info(f"Updated {sales_updated} sales to Tamil R Gold Loan branch")
    
    # Step 10: Check if any data remains unassigned
    unassigned = count_unassigned_data()
    
    if sum(unassigned.values()) > 0:
        logger.warning("Some data still not assigned to organizations:")
        for data_type, count in unassigned.items():
            if count > 0:
                logger.warning(f"- {data_type}: {count}")
    else:
        logger.info("All data has been successfully assigned to the Theni organization and Tamil R Gold Loan branch!")
    
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
    logger.info("Starting data migration to Theni organization and Tamil R Gold Loan branch...")
    
    # Check how much data needs migration
    before_counts = count_unassigned_data()
    logger.info("Data without organization assignment:")
    for data_type, count in before_counts.items():
        logger.info(f"- {data_type}: {count}")
    
    if sum(before_counts.values()) == 0:
        logger.info("No data needs migration. All data already has organization assignments.")
        return
    
    # Create or get Theni organization and Tamil R Gold Loan branch
    theni_org, tamil_r_branch = create_theni_organization_and_branch()
    
    # Migrate data
    migration_results = migrate_data_to_theni(theni_org, tamil_r_branch)
    
    # Check final state
    after_counts = count_unassigned_data()
    
    logger.info("\nMigration completed!")
    logger.info(f"Theni organization: {theni_org.name} (ID: {theni_org.id})")
    logger.info(f"Tamil R Gold Loan branch: {tamil_r_branch.name} (ID: {tamil_r_branch.id})")
    logger.info(f"Data migrated: {migration_results}")
    
    # Check if any data still needs migration
    if sum(after_counts.values()) > 0:
        logger.warning("\nWARNING: Some data still doesn't have organization assignments:")
        for data_type, count in after_counts.items():
            if count > 0:
                logger.warning(f"- {data_type}: {count}")
    else:
        logger.info("\nSUCCESS: All data has been successfully assigned to the Theni organization and Tamil R Gold Loan branch!")

if __name__ == "__main__":
    main()