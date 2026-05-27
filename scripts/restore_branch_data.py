#!/usr/bin/env python
"""
Script to restore branch data from JSON backup files.
Run this script after deployment to restore branch data in the production environment.
"""
import os
import sys
import json
import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up Django
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.db import transaction
from branches.models import Branch, BranchSettings
from django.utils.timezone import make_aware
from datetime import datetime


def restore_branch_data():
    """Restore branch data from the latest backup files"""
    logger.info("Restoring branch data...")
    
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    
    # Check for backup directory
    if not os.path.exists(backup_dir):
        logger.error(f"❌ Backup directory does not exist: {backup_dir}")
        return False
    
    # Find backup files
    branches_file = os.path.join(backup_dir, 'branches_backup_latest.json')
    settings_file = os.path.join(backup_dir, 'branch_settings_backup_latest.json')
    
    if not os.path.exists(branches_file):
        logger.error(f"❌ Branches backup file not found: {branches_file}")
        return False
        
    if not os.path.exists(settings_file):
        logger.warning(f"⚠️ Branch settings backup file not found: {settings_file}")
    
    try:
        # Load branch data
        with open(branches_file, 'r') as f:
            branches_data = json.load(f)
        
        # Load settings data if available
        settings_data = []
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings_data = json.load(f)
        
        # Start a transaction to restore data
        with transaction.atomic():
            # Restore branches
            for branch_data in branches_data:
                # Check if the branch already exists
                branch_id = branch_data.get('id')
                branch_name = branch_data.get('name')
                branch, created = Branch.objects.update_or_create(
                    id=branch_id,
                    defaults={
                        'name': branch_name,
                        'address': branch_data.get('address', ''),
                        'city': branch_data.get('city', ''),
                        'state': branch_data.get('state', ''),
                        'zip_code': branch_data.get('zip_code', ''),
                        'phone': branch_data.get('phone', ''),
                        'email': branch_data.get('email'),
                        'region_id': branch_data.get('region_id'),
                        'manager_id': branch_data.get('manager_id'),
                        'is_active': branch_data.get('is_active', True),
                        'opening_time': branch_data.get('opening_time', '09:00'),
                        'closing_time': branch_data.get('closing_time', '18:00'),
                    }
                )
                
                if created:
                    logger.info(f"✅ Created branch: {branch_name}")
                else:
                    logger.info(f"✅ Updated branch: {branch_name}")
            
            # Restore branch settings
            for setting_data in settings_data:
                branch_id = setting_data.get('branch_id')
                try:
                    branch = Branch.objects.get(id=branch_id)
                    setting, created = BranchSettings.objects.update_or_create(
                        branch=branch,
                        defaults={
                            'max_loan_amount': setting_data.get('max_loan_amount', '5000.00'),
                            'default_interest_rate': setting_data.get('default_interest_rate', '10.00'),
                            'loan_duration_days': setting_data.get('loan_duration_days', 30),
                            'grace_period_days': setting_data.get('grace_period_days', 15),
                            'allow_online_payments': setting_data.get('allow_online_payments', True),
                            'require_id_verification': setting_data.get('require_id_verification', True),
                            'enable_face_recognition': setting_data.get('enable_face_recognition', False),
                            'enable_email_notifications': setting_data.get('enable_email_notifications', True),
                            'enable_sms_notifications': setting_data.get('enable_sms_notifications', False),
                            'auction_delay_days': setting_data.get('auction_delay_days', 7),
                        }
                    )
                    
                    if created:
                        logger.info(f"✅ Created settings for branch: {branch.name}")
                    else:
                        logger.info(f"✅ Updated settings for branch: {branch.name}")
                except Branch.DoesNotExist:
                    logger.warning(f"⚠️ Could not find branch with ID {branch_id} for settings")
        
        logger.info("✅ Branch data restoration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error restoring branch data: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def create_default_branch_if_empty():
    """Create a default branch if no branches exist"""
    if Branch.objects.count() == 0:
        logger.info("No branches found. Creating default branch...")
        
        branch = Branch.objects.create(
            name="Main Branch",
            address="123 Main Street",
            city="City",
            state="State",
            zip_code="12345",
            phone="123-456-7890",
            is_active=True
        )
        
        # Create default settings
        BranchSettings.objects.create(
            branch=branch,
            max_loan_amount=5000.00,
            default_interest_rate=10.00,
            loan_duration_days=30,
            grace_period_days=15
        )
        
        logger.info(f"✅ Created default branch: {branch.name}")


if __name__ == "__main__":
    success = restore_branch_data()
    
    if not success:
        create_default_branch_if_empty()