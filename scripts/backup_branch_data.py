#!/usr/bin/env python
"""
Script to backup branch data to JSON files that can be committed to version control.
Run this script before deployment to ensure branch data can be restored in production.
"""
import os
import sys
import json
import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up Django
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from branches.models import Branch, BranchSettings


def backup_branch_data():
    """Backup all branch data to a JSON file"""
    print("Backing up branch data...")
    
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    branches_file = os.path.join(backup_dir, f'branches_backup_{timestamp}.json')
    settings_file = os.path.join(backup_dir, f'branch_settings_backup_{timestamp}.json')
    
    # Backup branch data
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
    
    # Backup branch settings
    settings = []
    for setting in BranchSettings.objects.all():
        settings.append({
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
    
    # Write data to files
    with open(branches_file, 'w') as f:
        json.dump(branches, f, indent=2)
        
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)
    
    # Create the latest version file for restoration
    latest_branches_file = os.path.join(backup_dir, 'branches_backup_latest.json')
    latest_settings_file = os.path.join(backup_dir, 'branch_settings_backup_latest.json')
    
    with open(latest_branches_file, 'w') as f:
        json.dump(branches, f, indent=2)
        
    with open(latest_settings_file, 'w') as f:
        json.dump(settings, f, indent=2)
    
    print(f"✅ Branch data backed up to {branches_file}")
    print(f"✅ Branch settings backed up to {settings_file}")
    print(f"✅ Latest versions saved for restoration")


if __name__ == "__main__":
    backup_branch_data()