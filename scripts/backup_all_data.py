#!/usr/bin/env python
"""
Script to backup all critical data to JSON files that can be committed to version control.
Run this script before deployment to ensure all important data can be restored in production.
"""
import os
import sys
import json
import datetime
import logging
from decimal import Decimal

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

# Import all relevant models
from branches.models import Branch, BranchSettings
from schemes.models import Scheme
from accounts.models import Customer, Role, CustomUser
from inventory.models import Category, Item
from biometrics.models import BiometricSetting
from integrations.models import Integration, POSIntegration, AccountingIntegration, CRMIntegration


# Custom JSON encoder to handle Decimal, datetime, etc.
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super().default(obj)


def backup_data():
    """Backup all critical data to JSON files"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    # Dictionary to store all backups
    backups = {}
    
    # 1. Backup Branch Data
    logger.info("Backing up branch data...")
    branches = []
    for branch in Branch.objects.all():
        branches.append({
            'id': branch.id,
            'name': branch.name,
            'address': branch.address,
            'city': branch.city,
            'state': branch.state,
            'zip_code': branch.zip_code,
            'phone': branch.phone,
            'email': branch.email,
            'region_id': branch.region_id,
            'manager_id': branch.manager_id if branch.manager_id else None,
            'is_active': branch.is_active,
            'opening_time': branch.opening_time.strftime('%H:%M') if branch.opening_time else '09:00',
            'closing_time': branch.closing_time.strftime('%H:%M') if branch.closing_time else '18:00',
            'created_at': branch.created_at.isoformat() if branch.created_at else None,
        })
    backups['branches'] = branches
    
    # 2. Backup Branch Settings
    branch_settings = []
    for setting in BranchSettings.objects.all():
        branch_settings.append({
            'id': setting.id,
            'branch_id': setting.branch_id,
            'max_loan_amount': str(setting.max_loan_amount),
            'default_interest_rate': str(setting.default_interest_rate),
            'loan_duration_days': setting.loan_duration_days,
            'grace_period_days': setting.grace_period_days,
            'allow_online_payments': setting.allow_online_payments,
            'require_id_verification': setting.require_id_verification,
            'enable_face_recognition': setting.enable_face_recognition,
            'enable_email_notifications': setting.enable_email_notifications,
            'enable_sms_notifications': setting.enable_sms_notifications,
            'auction_delay_days': setting.auction_delay_days,
        })
    backups['branch_settings'] = branch_settings
    
    # 3. Backup Loan Schemes
    logger.info("Backing up loan schemes...")
    schemes = []
    for scheme in Scheme.objects.all():
        schemes.append({
            'id': scheme.id,
            'name': scheme.name,
            'description': scheme.description,
            'interest_rate': str(scheme.interest_rate),
            'loan_duration': scheme.loan_duration,
            'minimum_amount': str(scheme.minimum_amount),
            'maximum_amount': str(scheme.maximum_amount),
            'additional_conditions': scheme.additional_conditions,
            'start_date': scheme.start_date.isoformat(),
            'end_date': scheme.end_date.isoformat() if scheme.end_date else None,
            'status': scheme.status,
            'branch_id': scheme.branch_id,
            'created_by_id': scheme.created_by_id,
            'updated_by_id': scheme.updated_by_id,
        })
    backups['schemes'] = schemes
    
    # 4. Backup Roles
    logger.info("Backing up roles and permissions...")
    roles = []
    for role in Role.objects.all():
        # Get permission IDs
        permission_ids = list(role.permissions.values_list('id', flat=True))
        roles.append({
            'id': role.id,
            'name': role.name,
            'role_type': role.role_type,
            'category': role.category,
            'description': role.description,
            'permission_ids': permission_ids,
        })
    backups['roles'] = roles
    
    # 5. Backup Category Data
    logger.info("Backing up inventory categories...")
    categories = []
    for category in Category.objects.all():
        categories.append({
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'parent_id': category.parent_id,
            'is_active': category.is_active,
        })
    backups['categories'] = categories
    
    # 6. Backup BiometricSettings
    logger.info("Backing up biometric settings...")
    biometric_settings = []
    for setting in BiometricSetting.objects.all():
        biometric_settings.append({
            'id': setting.id,
            'branch_id': setting.branch_id,
            'face_recognition_enabled': setting.face_recognition_enabled,
            'face_recognition_required_for_staff': setting.face_recognition_required_for_staff,
            'face_recognition_required_for_customers': setting.face_recognition_required_for_customers,
            'fingerprint_enabled': setting.fingerprint_enabled,
            'min_confidence': float(setting.min_confidence) if setting.min_confidence else 0.7,
            'max_attempts': setting.max_attempts,
            'lockout_duration': str(setting.lockout_duration) if setting.lockout_duration else '01:00:00',
        })
    backups['biometric_settings'] = biometric_settings
    
    # 7. Backup Integration Settings
    logger.info("Backing up integration settings...")
    integrations = []
    for integration in Integration.objects.all():
        # Hide sensitive information
        integration_data = {
            'id': integration.id,
            'name': integration.name,
            'integration_type': integration.integration_type,
            'description': integration.description,
            'api_endpoint': integration.api_endpoint,
            'other_credentials': {},  # Don't backup sensitive credentials
            'status': integration.status,
            'branch_id': integration.branch_id,
        }
        integrations.append(integration_data)
    backups['integrations'] = integrations
    
    # Save to a single comprehensive backup file
    backup_file = os.path.join(backup_dir, f'all_data_backup_{timestamp}.json')
    with open(backup_file, 'w') as f:
        json.dump(backups, f, indent=2, cls=CustomJSONEncoder)
    
    # Also save the latest version for restoration
    latest_file = os.path.join(backup_dir, 'all_data_backup_latest.json')
    with open(latest_file, 'w') as f:
        json.dump(backups, f, indent=2, cls=CustomJSONEncoder)
    
    logger.info(f"✅ All data backed up to {backup_file}")
    logger.info(f"✅ Latest version saved to {latest_file} for restoration")
    
    # Return the count of each entity backed up
    backup_stats = {
        'branches': len(branches),
        'branch_settings': len(branch_settings),
        'schemes': len(schemes),
        'roles': len(roles),
        'categories': len(categories),
        'biometric_settings': len(biometric_settings),
        'integrations': len(integrations),
    }
    
    logger.info("Backup statistics:")
    for entity, count in backup_stats.items():
        logger.info(f"  - {entity}: {count} items")
    
    return backup_stats


if __name__ == "__main__":
    backup_data()