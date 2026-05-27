import os
import django
from decimal import Decimal

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Role, Region, CustomUser
from branches.models import Branch, BranchSettings
from inventory.models import Category, Item

def create_regions():
    regions = [
        {'name': 'North Region', 'description': 'Northern branches of the pawnshop'},
        {'name': 'South Region', 'description': 'Southern branches of the pawnshop'},
        {'name': 'Central Region', 'description': 'Central area branches'}
    ]
    
    created_regions = []
    for region_data in regions:
        region, created = Region.objects.get_or_create(**region_data)
        created_regions.append(region)
    return created_regions

def create_branches(regions):
    branches = [
        {
            'name': 'Main Branch',
            'address': '123 Main Street',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'zip_code': '400001',
            'phone': '022-12345678',
            'email': 'main@pawnshop.com',
            'region': regions[0],
            'is_active': True
        },
        {
            'name': 'South City Branch',
            'address': '456 South Avenue',
            'city': 'Bangalore',
            'state': 'Karnataka',
            'zip_code': '560001',
            'phone': '080-87654321',
            'email': 'south@pawnshop.com',
            'region': regions[1],
            'is_active': True
        }
    ]
    
    created_branches = []
    for branch_data in branches:
        branch, created = Branch.objects.get_or_create(**branch_data)
        
        # Create branch settings
        BranchSettings.objects.get_or_create(
            branch=branch,
            defaults={
                'max_loan_amount': Decimal('50000.00'),
                'default_interest_rate': Decimal('12.00'),
                'loan_duration_days': 30,
                'grace_period_days': 7
            }
        )
        created_branches.append(branch)
    return created_branches

def create_staff_members(branches):
    # Create roles first
    roles = {
        'Branch Manager': Role.BRANCH_MANAGER,
        'Loan Officer': Role.LOAN_OFFICER,
        'Cashier': Role.CASHIER,
        'Appraiser': Role.APPRAISER
    }
    
    created_roles = {}
    for role_name, role_type in roles.items():
        role, created = Role.objects.get_or_create(
            name=role_name,
            defaults={
                'role_type': role_type,
                'category': Role.MANAGEMENT if role_type == Role.BRANCH_MANAGER else Role.FRONTLINE
            }
        )
        created_roles[role_name] = role

    # Create staff members
    staff = [
        {
            'username': 'manager1',
            'email': 'manager1@pawnshop.com',
            'first_name': 'John',
            'last_name': 'Manager',
            'role': created_roles['Branch Manager'],
            'branch': branches[0],
            'is_staff': True
        },
        {
            'username': 'loanofficer1',
            'email': 'loanofficer1@pawnshop.com',
            'first_name': 'Sarah',
            'last_name': 'Officer',
            'role': created_roles['Loan Officer'],
            'branch': branches[0],
            'is_staff': True
        },
        {
            'username': 'cashier1',
            'email': 'cashier1@pawnshop.com',
            'first_name': 'Mike',
            'last_name': 'Cashier',
            'role': created_roles['Cashier'],
            'branch': branches[0],
            'is_staff': True
        }
    ]
    
    User = get_user_model()
    created_staff = []
    for staff_data in staff:
        user, created = User.objects.get_or_create(
            username=staff_data['username'],
            defaults={
                **staff_data,
                'password': 'password123'  # This should be changed on first login
            }
        )
        if created:
            user.set_password('password123')
            user.save()
        created_staff.append(user)
    return created_staff

def create_inventory_categories():
    categories = [
        {
            'name': 'Jewelry',
            'description': 'Precious metals and gemstones',
            'icon': 'fa-gem'
        },
        {
            'name': 'Electronics',
            'description': 'Phones, laptops, and other electronic devices',
            'icon': 'fa-laptop'
        },
        {
            'name': 'Watches',
            'description': 'Luxury and regular timepieces',
            'icon': 'fa-clock'
        },
        {
            'name': 'Musical Instruments',
            'description': 'Guitars, pianos, and other instruments',
            'icon': 'fa-music'
        }
    ]
    
    created_categories = []
    for cat_data in categories:
        category, created = Category.objects.get_or_create(**cat_data)
        created_categories.append(category)
    return created_categories

def create_sample_items(categories, branch, created_by):
    items = [
        {
            'name': '18K Gold Necklace',
            'description': 'Beautiful 18K gold necklace with pendant',
            'category': categories[0],  # Jewelry
            'branch': branch,
            'condition': 'excellent',
            'appraised_value': Decimal('25000.00'),
            'created_by': created_by
        },
        {
            'name': 'iPhone 13 Pro',
            'description': '256GB iPhone 13 Pro in excellent condition',
            'category': categories[1],  # Electronics
            'branch': branch,
            'condition': 'good',
            'appraised_value': Decimal('45000.00'),
            'created_by': created_by
        }
    ]
    
    created_items = []
    for item_data in items:
        item, created = Item.objects.get_or_create(**item_data)
        created_items.append(item)
    return created_items

def main():
    print("Creating basic data for the pawnshop system...")
    
    # Create regions
    print("Creating regions...")
    regions = create_regions()
    
    # Create branches
    print("Creating branches...")
    branches = create_branches(regions)
    
    # Create staff members
    print("Creating staff members...")
    staff = create_staff_members(branches)
    
    # Create inventory categories
    print("Creating inventory categories...")
    categories = create_inventory_categories()
    
    # Create sample items
    print("Creating sample items...")
    items = create_sample_items(categories, branches[0], staff[0])
    
    print("Basic data setup completed successfully!")

if __name__ == '__main__':
    main() 