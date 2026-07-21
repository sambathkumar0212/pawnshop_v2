from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from accounts.models import Customer
from branches.models import Branch
from schemes.models import Scheme
from transactions.models import Loan
from transactions.forms import LoanForm

class LoanFirstMonthInterestPaidTestCase(TestCase):
    def setUp(self):
        # Create Branch
        self.branch = Branch.objects.create(
            name="Test Branch",
            address="123 Street",
            city="Chennai",
            state="TN",
            zip_code="600001",
            phone="1234567890"
        )
        # Create Customer
        self.customer = Customer.objects.create(
            first_name="John",
            last_name="Doe",
            phone="9876543210",
            branch=self.branch
        )
        # Create Scheme
        self.scheme = Scheme.objects.create(
            name="Standard Gold Loan Test",
            description="12% annual interest scheme",
            interest_rate=Decimal('12.00'),
            loan_duration=364,
            minimum_amount=Decimal('1000'),
            maximum_amount=Decimal('1000000'),
            start_date=timezone.now().date(),
            processing_fee_percentage=Decimal('1.00')
        )

    def test_loan_calculations_without_first_month_interest_paid(self):
        # Create loan without first month interest paid
        loan = Loan.objects.create(
            loan_number="TEST-0001",
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('25000'),
            interest_rate=Decimal('12.00'),
            processing_fee=250, # 1%
            distribution_amount=Decimal('24750'), # 25000 - 250
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            is_first_month_interest_paid=False
        )
        
        # Verify monthly interest amount: (24750 * 1%) = 247.50
        monthly_interest = loan.monthly_interest
        self.assertEqual(monthly_interest['amount'], Decimal('247.50'))
        
        # Verify total payable at maturity: principal + 12 months interest
        # 25000 + 12 * 247.50 = 25000 + 2970 = 27970
        self.assertEqual(loan.total_payable_mature, Decimal('27970.00'))
        self.assertEqual(loan.remaining_balance, Decimal('27970.00'))

    def test_loan_calculations_with_first_month_interest_paid(self):
        # Create loan with first month interest paid upfront
        # Processing fee = 250
        # Monthly interest = (25000 - 250) * 1% = 247.50
        # Distribution amount = principal - processing_fee - monthly_interest = 25000 - 250 - 247.50 = 24502.50
        # Under banker's rounding: 24502
        loan = Loan.objects.create(
            loan_number="TEST-0002",
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('25000'),
            interest_rate=Decimal('12.00'),
            processing_fee=250,
            distribution_amount=Decimal('24502'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            is_first_month_interest_paid=True
        )
        
        # Verify monthly interest amount: should still be calculated based on base distribution amount (24750)
        # So monthly interest is 247.50
        monthly_interest = loan.monthly_interest
        self.assertEqual(monthly_interest['amount'], Decimal('247.50'))
        
        # Verify total payable at maturity is reduced by 1 month of interest (12 - 1 = 11 months):
        # 25000 + 11 * 247.50 = 25000 + 2722.50 = 27722.50
        self.assertEqual(loan.total_payable_mature, Decimal('27722.50'))
        self.assertEqual(loan.remaining_balance, Decimal('27722.50'))

    def test_loan_form_validation_and_clean(self):
        # Verify form clean method logic for upfront deduction
        # Test case: Is first month interest paid = True
        form_data = {
            'customer': self.customer.id,
            'branch': self.branch.id,
            'scheme': self.scheme.id,
            'principal_amount': 25000,
            'processing_fee': 250,
            'interest_rate': 12.00,
            'issue_date': timezone.now().date(),
            'due_date': timezone.now().date() + timezone.timedelta(days=364),
            'is_first_month_interest_paid': True,
            # Required fields for creating a new item
            'item_name': 'Test Gold Ring',
            'item_category': 1, # Just some ID
            'gold_karat': '22',
            'market_price_22k': 5000,
            'gross_weight': 10.0,
            'net_weight': 9.0,
        }
        
        # Mock item category creation
        from inventory.models import Category
        category = Category.objects.create(name="Ring")
        form_data['item_category'] = category.id
        
        # Instantiate form with custom user branch mapping
        form = LoanForm(data=form_data)
        
        # We might need to mock self.user for the form
        class MockUser:
            id = 1
            branch = self.branch
            is_superuser = True
        form.user = MockUser()
        
        # Verify form is valid and cleaned data for distribution_amount is correct (24502)
        self.assertTrue(form.is_valid(), form.errors.as_data())
        self.assertEqual(form.cleaned_data['distribution_amount'], Decimal('24502'))
