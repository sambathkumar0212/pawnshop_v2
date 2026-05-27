#!/usr/bin/env python
"""
Script to restore all critical data from JSON backup files.
Run this script after deployment to restore all important data in the production environment.
"""
import os
import sys
import json
import datetime
import logging
from decimal import Decimal
import shutil

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
from django.contrib.auth.models import Permission
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import make_aware, is_aware

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


def parse_time_str(time_str):
    """Parse a time string like '09:00' into a datetime.time object"""
    try:
        hours, minutes = time_str.split(':')
        from datetime import time
        return time(int(hours), int(minutes))
    except (ValueError, AttributeError):
        return None


def check_fixtures_for_backup():
    """Check if there are fixture files that can be used as backups"""
    project_root = os.path.dirname(os.path.dirname(__file__))
    fixture_paths = [
        os.path.join(project_root, 'schemes', 'fixtures', 'default_schemes.json'),
    ]
    
    for path in fixture_paths:
        if os.path.exists(path):
            logger.info(f"✅ Found fixture file that can be used for backup: {path}")
            return True
    
    return False


def create_backup_of_default_data(data_dict):
    """Create a backup file from the default data we just created"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # Save to a backup file
    backup_file = os.path.join(backup_dir, f'default_data_backup_{timestamp}.json')
    with open(backup_file, 'w') as f:
        json.dump(data_dict, f, indent=2, cls=CustomJSONEncoder)
    
    # Also save as the latest version
    latest_file = os.path.join(backup_dir, 'all_data_backup_latest.json')
    with open(latest_file, 'w') as f:
        json.dump(data_dict, f, indent=2, cls=CustomJSONEncoder)
    
    logger.info(f"✅ Default data backed up to {backup_file}")
    logger.info(f"✅ Latest version saved to {latest_file}")


def restore_data():
    """Restore all critical data from the latest backup file"""
    logger.info("Starting data restoration...")
    
    # Create backup directory if it doesn't exist
    project_root = os.path.dirname(os.path.dirname(__file__))
    backup_dir = os.path.join(project_root, 'backups')
    if not os.path.exists(backup_dir):
        logger.warning(f"⚠️ Backup directory does not exist, creating it now: {backup_dir}")
        os.makedirs(backup_dir, exist_ok=True)
    
    # Check for alternative backup sources
    has_fixtures = check_fixtures_for_backup()
    
    # Find backup file
    backup_file = os.path.join(backup_dir, 'all_data_backup_latest.json')
    if not os.path.exists(backup_file):
        # If the file does not exist, try to find any JSON file in the backups directory
        json_files = [f for f in os.listdir(backup_dir) if f.endswith('.json')] if os.path.exists(backup_dir) else []
        
        if json_files:
            # Sort files by modification time (most recent first)
            json_files.sort(key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)), reverse=True)
            backup_file = os.path.join(backup_dir, json_files[0])
            logger.warning(f"⚠️ Using alternative backup file: {json_files[0]}")
        else:
            logger.error(f"❌ No backup files found in directory: {backup_dir}")
            
            # Check if we should try using fixture data
            if has_fixtures:
                logger.info("Trying to use fixture data as backup...")
                # Copy fixtures to backup directory if they exist
                fixture_path = os.path.join(project_root, 'schemes', 'fixtures', 'default_schemes.json')
                if os.path.exists(fixture_path):
                    backup_file = os.path.join(backup_dir, 'schemes_fixture_backup.json')
                    shutil.copy2(fixture_path, backup_file)
                    logger.info(f"✅ Copied scheme fixtures to: {backup_file}")
                else:
                    logger.warning("No suitable fixtures found to use as backup")
                    return False
            else:
                return False
    
    try:
        # Load backup data
        with open(backup_file, 'r') as f:
            backups = json.load(f)
        
        # Start a transaction for all data restoration
        with transaction.atomic():
            # 1. Restore Branch Data
            if 'branches' in backups:
                logger.info("Restoring branch data...")
                for branch_data in backups['branches']:
                    branch_id = branch_data.get('id')
                    branch_name = branch_data.get('name')
                    
                    # Parse time strings
                    opening_time = parse_time_str(branch_data.get('opening_time', '09:00'))
                    closing_time = parse_time_str(branch_data.get('closing_time', '18:00'))
                    
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
                            'opening_time': opening_time,
                            'closing_time': closing_time,
                        }
                    )
                    
                    if created:
                        logger.info(f"✅ Created branch: {branch_name}")
                    else:
                        logger.info(f"✅ Updated branch: {branch_name}")
            
            # 2. Restore Branch Settings
            if 'branch_settings' in backups:
                logger.info("Restoring branch settings...")
                for setting_data in backups['branch_settings']:
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
            
            # 3. Restore Roles
            if 'roles' in backups:
                logger.info("Restoring roles...")
                for role_data in backups['roles']:
                    role_id = role_data.get('id')
                    role_name = role_data.get('name')
                    permission_ids = role_data.get('permission_ids', [])
                    
                    role, created = Role.objects.update_or_create(
                        id=role_id,
                        defaults={
                            'name': role_name,
                            'role_type': role_data.get('role_type', ''),
                            'category': role_data.get('category', ''),
                            'description': role_data.get('description', ''),
                        }
                    )
                    
                    # Assign permissions if they exist
                    if permission_ids:
                        permissions = Permission.objects.filter(id__in=permission_ids)
                        role.permissions.set(permissions)
                    
                    if created:
                        logger.info(f"✅ Created role: {role_name}")
                    else:
                        logger.info(f"✅ Updated role: {role_name}")
            
            # 4. Restore Categories
            if 'categories' in backups:
                logger.info("Restoring inventory categories...")
                for category_data in backups['categories']:
                    category_id = category_data.get('id')
                    category_name = category_data.get('name')
                    
                    category, created = Category.objects.update_or_create(
                        id=category_id,
                        defaults={
                            'name': category_name,
                            'description': category_data.get('description', ''),
                            'parent_id': category_data.get('parent_id'),
                            'is_active': category_data.get('is_active', True),
                        }
                    )
                    
                    if created:
                        logger.info(f"✅ Created category: {category_name}")
                    else:
                        logger.info(f"✅ Updated category: {category_name}")
            
            # 5. Restore Schemes
            if 'schemes' in backups:
                logger.info("Restoring loan schemes...")
                for scheme_data in backups['schemes']:
                    scheme_id = scheme_data.get('id')
                    scheme_name = scheme_data.get('name')
                    
                    # Parse dates
                    start_date = parse_date(scheme_data.get('start_date'))
                    end_date = parse_date(scheme_data.get('end_date')) if scheme_data.get('end_date') else None
                    
                    try:
                        scheme, created = Scheme.objects.update_or_create(
                            id=scheme_id,
                            defaults={
                                'name': scheme_name,
                                'description': scheme_data.get('description', ''),
                                'interest_rate': Decimal(scheme_data.get('interest_rate', '10.00')),
                                'loan_duration': int(scheme_data.get('loan_duration', 30)),
                                'minimum_amount': Decimal(scheme_data.get('minimum_amount', '1000.00')),
                                'maximum_amount': Decimal(scheme_data.get('maximum_amount', '50000.00')),
                                'additional_conditions': scheme_data.get('additional_conditions', {}),
                                'start_date': start_date,
                                'end_date': end_date,
                                'status': scheme_data.get('status', 'active'),
                                'branch_id': scheme_data.get('branch_id'),
                                'created_by_id': scheme_data.get('created_by_id'),
                                'updated_by_id': scheme_data.get('updated_by_id'),
                            }
                        )
                        
                        if created:
                            logger.info(f"✅ Created scheme: {scheme_name}")
                        else:
                            logger.info(f"✅ Updated scheme: {scheme_name}")
                    except Exception as e:
                        logger.error(f"❌ Error restoring scheme {scheme_name}: {str(e)}")
            
            # 6. Restore Biometric Settings
            if 'biometric_settings' in backups:
                logger.info("Restoring biometric settings...")
                for setting_data in backups['biometric_settings']:
                    branch_id = setting_data.get('branch_id')
                    
                    try:
                        branch = Branch.objects.get(id=branch_id)
                        setting, created = BiometricSetting.objects.update_or_create(
                            branch=branch,
                            defaults={
                                'face_recognition_enabled': setting_data.get('face_recognition_enabled', False),
                                'face_recognition_required_for_staff': setting_data.get('face_recognition_required_for_staff', False),
                                'face_recognition_required_for_customers': setting_data.get('face_recognition_required_for_customers', False),
                                'fingerprint_enabled': setting_data.get('fingerprint_enabled', False),
                                'min_confidence': float(setting_data.get('min_confidence', 0.7)),
                                'max_attempts': int(setting_data.get('max_attempts', 3)),
                                'lockout_duration': setting_data.get('lockout_duration', '01:00:00'),
                            }
                        )
                        
                        if created:
                            logger.info(f"✅ Created biometric settings for branch: {branch.name}")
                        else:
                            logger.info(f"✅ Updated biometric settings for branch: {branch.name}")
                    except Branch.DoesNotExist:
                        logger.warning(f"⚠️ Could not find branch with ID {branch_id} for biometric settings")
            
            # 7. Restore Integrations (skip sensitive data)
            if 'integrations' in backups:
                logger.info("Restoring integration settings (without sensitive data)...")
                for integration_data in backups['integrations']:
                    integration_id = integration_data.get('id')
                    integration_name = integration_data.get('name')
                    
                    try:
                        integration, created = Integration.objects.update_or_create(
                            id=integration_id,
                            defaults={
                                'name': integration_name,
                                'integration_type': integration_data.get('integration_type', 'other'),
                                'description': integration_data.get('description', ''),
                                'api_endpoint': integration_data.get('api_endpoint', ''),
                                'status': integration_data.get('status', 'inactive'),
                                'branch_id': integration_data.get('branch_id'),
                            }
                        )
                        
                        if created:
                            logger.info(f"✅ Created integration: {integration_name}")
                        else:
                            logger.info(f"✅ Updated integration: {integration_name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Error restoring integration {integration_name}: {str(e)}")
        
        logger.info("✅ All data restoration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error restoring data: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def create_defaults_if_empty():
    """Create default data if there's nothing in the database"""
    logger.info("Creating default data as no backup was found or restoration failed")
    
    # Dictionary to store all default data to back up
    default_data = {
        'branches': [],
        'branch_settings': [],
        'schemes': [],
        'categories': []
    }
    
    # Check if branches exist
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
        
        # Create default branch settings
        settings = BranchSettings.objects.create(
            branch=branch,
            max_loan_amount=5000.00,
            default_interest_rate=10.00,
            loan_duration_days=30,
            grace_period_days=15
        )
        
        # Add to default data
        default_data['branches'].append({
            'id': branch.id,
            'name': branch.name,
            'address': branch.address,
            'city': branch.city,
            'state': branch.state,
            'zip_code': branch.zip_code,
            'phone': branch.phone,
            'email': branch.email,
            'is_active': branch.is_active,
            'opening_time': '09:00',
            'closing_time': '18:00'
        })
        
        default_data['branch_settings'].append({
            'id': settings.id,
            'branch_id': settings.branch_id,
            'max_loan_amount': str(settings.max_loan_amount),
            'default_interest_rate': str(settings.default_interest_rate),
            'loan_duration_days': settings.loan_duration_days,
            'grace_period_days': settings.grace_period_days,
            'allow_online_payments': settings.allow_online_payments,
            'require_id_verification': settings.require_id_verification,
            'enable_face_recognition': settings.enable_face_recognition,
            'enable_email_notifications': settings.enable_email_notifications,
            'enable_sms_notifications': settings.enable_sms_notifications,
            'auction_delay_days': settings.auction_delay_days
        })
        
        logger.info(f"✅ Created default branch: {branch.name}")
    
    # Check if schemes exist
    if Scheme.objects.count() == 0:
        logger.info("No loan schemes found. Creating default scheme...")
        
        from django.utils import timezone
        
        try:
            scheme = Scheme.objects.create(
                name="Standard Gold Loan",
                description="Standard gold loan with 12% annual interest",
                interest_rate=Decimal('12.00'),
                loan_duration=364,  # Just under a year
                minimum_amount=Decimal('1000.00'),
                maximum_amount=Decimal('100000.00'),
                start_date=timezone.now().date(),
                status='active',
                additional_conditions={
                    'processing_fee_percentage': 1.0,
                    'late_fee_percentage': 2.0,
                    'no_interest_period_days': 15
                }
            )
            
            # Add to default data
            default_data['schemes'].append({
                'id': scheme.id,
                'name': scheme.name,
                'description': scheme.description,
                'interest_rate': str(scheme.interest_rate),
                'loan_duration': scheme.loan_duration,
                'minimum_amount': str(scheme.minimum_amount),
                'maximum_amount': str(scheme.maximum_amount),
                'additional_conditions': scheme.additional_conditions,
                'start_date': scheme.start_date.isoformat(),
                'end_date': None,
                'status': scheme.status,
                'branch_id': scheme.branch_id,
                'created_by_id': scheme.created_by_id,
                'updated_by_id': scheme.updated_by_id
            })
            
            logger.info(f"✅ Created default scheme: {scheme.name}")
        except Exception as e:
            logger.error(f"❌ Error creating default scheme: {str(e)}")
    
    # Check if categories exist
    if Category.objects.count() == 0:
        logger.info("No categories found. Creating default categories...")
        
        categories = [
            {
                'name': 'Gold',
                'description': 'Gold jewelry and items'
            },
            {
                'name': 'Electronics',
                'description': 'Electronic devices and gadgets'
            },
            {
                'name': 'Vehicles',
                'description': 'Cars, motorcycles, and other vehicles'
            }
        ]
        
        for cat_data in categories:
            category = Category.objects.create(**cat_data)
            
            # Add to default data
            default_data['categories'].append({
                'id': category.id,
                'name': category.name,
                'description': category.description,
                'parent_id': None,
                'is_active': True
            })
            
            logger.info(f"✅ Created default category: {category.name}")
    
    # Create a backup of the default data we just created
    try:
        create_backup_of_default_data(default_data)
    except Exception as e:
        logger.error(f"❌ Error creating backup of default data: {str(e)}")


if __name__ == "__main__":
    success = restore_data()
    
    if not success:
        create_defaults_if_empty()