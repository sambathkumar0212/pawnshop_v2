import os
import django
from decimal import Decimal
from datetime import datetime, timedelta, date

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Customer
from branches.models import Branch
from schemes.models import Scheme
from transactions.models import Loan, Payment
from inventory.models import Item, Category
from transactions.models import LoanItem

def create_sample_customers(branch):
    customers = [
        {
            'first_name': 'Rahul',
            'last_name': 'Kumar',
            'email': 'rahul@example.com',
            'phone': '9876543210',
            'branch': branch,
            'address': '789 Customer Street',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'zip_code': '400001',
            'id_type': 'Aadhar Card',
            'id_number': '1234-5678-9012'
        },
        {
            'first_name': 'Priya',
            'last_name': 'Sharma',
            'email': 'priya@example.com',
            'phone': '9876543211',
            'branch': branch,
            'address': '456 Client Road',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'zip_code': '400002',
            'id_type': 'Driving License',
            'id_number': 'DL98765432'
        },
        {
            'first_name': 'Amit',
            'last_name': 'Patel',
            'email': 'amit@example.com',
            'phone': '9876543212',
            'branch': branch,
            'address': '123 Customer Lane',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'zip_code': '400003',
            'id_type': 'PAN Card',
            'id_number': 'ABCDE1234F'
        }
    ]
    
    created_customers = []
    for customer_data in customers:
        customer, created = Customer.objects.get_or_create(
            phone=customer_data['phone'],
            defaults=customer_data
        )
        created_customers.append(customer)
    return created_customers

def create_loan_schemes():
    # Get a user for created_by field
    User = get_user_model()
    admin_user = User.objects.filter(is_superuser=True).first()
    
    schemes = [
        {
            'name': 'Gold Loan - Premium',
            'description': 'Premium gold loan scheme with competitive interest rates',
            'interest_rate': Decimal('12.00'),
            'loan_duration': 90,
            'minimum_amount': Decimal('10000.00'),
            'maximum_amount': Decimal('1000000.00'),
            'additional_conditions': {
                'processing_fee_percent': 1.00,
                'grace_period_days': 15,
                'penalty_rate': 2.00,
                'loan_to_value_ratio': 75.00
            },
            'start_date': date.today(),
            'status': 'active',
            'created_by': admin_user
        },
        {
            'name': 'Electronics Quick Loan',
            'description': 'Fast loans for electronic items',
            'interest_rate': Decimal('15.00'),
            'loan_duration': 60,
            'minimum_amount': Decimal('5000.00'),
            'maximum_amount': Decimal('100000.00'),
            'additional_conditions': {
                'processing_fee_percent': 2.00,
                'grace_period_days': 10,
                'penalty_rate': 2.50,
                'loan_to_value_ratio': 60.00
            },
            'start_date': date.today(),
            'status': 'active',
            'created_by': admin_user
        },
        {
            'name': 'General Items Loan',
            'description': 'Flexible loan scheme for various items',
            'interest_rate': Decimal('18.00'),
            'loan_duration': 45,
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('50000.00'),
            'additional_conditions': {
                'processing_fee_percent': 2.00,
                'grace_period_days': 7,
                'penalty_rate': 3.00,
                'loan_to_value_ratio': 50.00
            },
            'start_date': date.today(),
            'status': 'active',
            'created_by': admin_user
        }
    ]
    
    created_schemes = []
    for scheme_data in schemes:
        scheme, created = Scheme.objects.get_or_create(
            name=scheme_data['name'],
            defaults=scheme_data
        )
        created_schemes.append(scheme)
    return created_schemes

def create_sample_loans(customers, schemes, branch):
    # Get a loan officer
    User = get_user_model()
    loan_officer = User.objects.filter(role__role_type='loan_officer').first()
    
    # Get or create some items for loans
    jewelry_category = Category.objects.get(name='Jewelry')
    electronics_category = Category.objects.get(name='Electronics')
    
    items = [
        {
            'name': '22K Gold Chain',
            'description': '22K gold chain, 25 grams',
            'category': jewelry_category,
            'branch': branch,
            'condition': 'excellent',
            'appraised_value': Decimal('85000.00'),
            'created_by': loan_officer
        },
        {
            'name': 'MacBook Pro 2023',
            'description': '16-inch MacBook Pro M2, 512GB',
            'category': electronics_category,
            'branch': branch,
            'condition': 'good',
            'appraised_value': Decimal('95000.00'),
            'created_by': loan_officer
        }
    ]
    
    created_items = []
    for item_data in items:
        item, created = Item.objects.get_or_create(
            name=item_data['name'],
            branch=item_data['branch'],
            defaults=item_data
        )
        created_items.append(item)
    
    # Create loans
    today = date.today()
    loans = [
        {
            'loan_number': f'GL{today.year}{today.month:02d}001',
            'customer': customers[0],
            'branch': branch,
            'scheme': schemes[0],  # Gold loan scheme
            'principal_amount': Decimal('60000.00'),
            'interest_rate': schemes[0].interest_rate,
            'processing_fee': 600,
            'distribution_amount': Decimal('59400.00'),  # Principal - processing fee
            'issue_date': today,
            'due_date': today + timedelta(days=schemes[0].loan_duration),
            'grace_period_end': today + timedelta(days=schemes[0].loan_duration + 15),
            'created_by': loan_officer,
            'status': 'active'
        },
        {
            'loan_number': f'EL{today.year}{today.month:02d}001',
            'customer': customers[1],
            'branch': branch,
            'scheme': schemes[1],  # Electronics scheme
            'principal_amount': Decimal('45000.00'),
            'interest_rate': schemes[1].interest_rate,
            'processing_fee': 900,
            'distribution_amount': Decimal('44100.00'),  # Principal - processing fee
            'issue_date': today,
            'due_date': today + timedelta(days=schemes[1].loan_duration),
            'grace_period_end': today + timedelta(days=schemes[1].loan_duration + 10),
            'created_by': loan_officer,
            'status': 'active'
        }
    ]
    
    created_loans = []
    for i, loan_data in enumerate(loans):
        loan = Loan.objects.create(**loan_data)
        
        # Create loan item with gold details for the first loan (gold item)
        if i == 0:
            LoanItem.objects.create(
                loan=loan,
                item=created_items[i],
                gold_karat=Decimal('22.00'),
                gross_weight=Decimal('25.000'),
                net_weight=Decimal('24.500'),
                stone_weight=Decimal('0.500'),
                market_price_22k=Decimal('5500.00')
            )
        else:
            # For non-gold items, just associate the item
            LoanItem.objects.create(
                loan=loan,
                item=created_items[i],
                gold_karat=Decimal('0.00'),
                gross_weight=Decimal('0.000'),
                net_weight=Decimal('0.000'),
                market_price_22k=Decimal('0.00')
            )
        
        created_loans.append(loan)
        
        # Create a payment for the processing fee
        Payment.objects.create(
            loan=loan,
            amount=Decimal(str(loan.processing_fee)),
            payment_date=today,
            payment_method='cash',
            received_by=loan_officer,
            notes='Processing fee payment'
        )
    
    return created_loans

def main():
    print("Creating loan-related sample data...")
    
    # Get the main branch
    branch = Branch.objects.get(name='Main Branch')
    
    # Create customers
    print("Creating sample customers...")
    customers = create_sample_customers(branch)
    
    # Create loan schemes
    print("Creating loan schemes...")
    schemes = create_loan_schemes()
    
    # Create sample loans
    print("Creating sample loans...")
    loans = create_sample_loans(customers, schemes, branch)
    
    print("Loan-related sample data created successfully!")
    print("\nSample data summary:")
    print(f"- Created {len(customers)} customers")
    print(f"- Created {len(schemes)} loan schemes")
    print(f"- Created {len(loans)} active loans")

if __name__ == '__main__':
    main() 