from django.test import TestCase, TransactionTestCase
from decimal import Decimal
from django.utils import timezone
from transactions.models import Loan
from schemes.models import Scheme
from branches.models import Branch
from accounts.models import Customer

class LoanInterestPropertiesTest(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            name="Test Branch",
            address="123 Test St",
            city="Test City",
            state="Test State",
            zip_code="12345",
            phone="123-456-7890"
        )
        self.customer = Customer.objects.create(
            first_name="John",
            last_name="Doe",
            phone="9876543210",
            branch=self.branch
        )
        self.scheme = Scheme.objects.create(
            name="Standard Gold Scheme",
            description="Standard Scheme",
            interest_rate=Decimal('12.00'), # 12% p.a.
            loan_duration=90,
            minimum_amount=Decimal('1000.00'),
            maximum_amount=Decimal('100000.00'),
            interest_rate_structure={'30': 12, '60': 12, '90': 12},
            start_date=timezone.now().date()
        )

    def test_daily_interest_calculations(self):
        # Create a loan of Rs. 10,000 principal, Rs. 100 processing fee
        # Base distribution amount = 10,000 - 100 = 9,900
        # For 12% p.a.:
        # Monthly rate = 1%
        # Monthly interest amount = 9,900 * 1% = 99.00
        # Daily interest amount = 9,900 * (12 / 36500) = 3.25
        issue_date = timezone.now().date() - timezone.timedelta(days=15)
        due_date = issue_date + timezone.timedelta(days=90)
        grace_period_end = due_date + timezone.timedelta(days=15)
        
        loan = Loan.objects.create(
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('10000.00'),
            interest_rate=Decimal('12.00'),
            processing_fee=100,
            distribution_amount=Decimal('9900.00'),
            issue_date=issue_date,
            due_date=due_date,
            grace_period_end=grace_period_end,
            status='active'
        )
        
        # Test basic monthly and daily interest rates/amounts
        self.assertEqual(loan.monthly_interest['amount'], Decimal('99.00'))
        self.assertEqual(loan.daily_interest_amount, Decimal('3.25')) # 9900 * 12 / 36500 = 3.25479 -> 3.25
        
        # Test accrued interest till date
        # Since it's a months-based scheme (is_days_based is False by default),
        # 15 days elapsed should enter the 1st month cycle (1 month accrued).
        # First month accrued interest is 1 * 99.00 = 99.00 (since is_first_month_interest_paid is False)
        self.assertEqual(loan.interest_till_date_monthly_basis, Decimal('99.00'))
        
        # Strictly daily-based interest till date:
        # 15 days elapsed * 3.25 = 48.82 (specifically, base_dist_amount * daily_rate * 15)
        # daily_rate = 12 / 36500 = 0.000328767
        # interest = 9900 * 0.000328767 * 15 = 48.82
        self.assertEqual(loan.interest_till_date_daily_basis, Decimal('48.82'))


class LoanNotificationEmailTest(TransactionTestCase):
    """Use TransactionTestCase so that transaction.on_commit() fires during tests."""

    def setUp(self):
        from branches.models import Branch
        from accounts.models import Customer
        from schemes.models import Scheme

        self.branch = Branch.objects.create(
            name="TES Branch",
            address="1 Test St",
            city="Test City",
            state="Test State",
            zip_code="12345",
            phone="0000000000"
        )
        self.customer = Customer.objects.create(
            first_name="John",
            last_name="Doe",
            phone="9999999999",
            branch=self.branch
        )
        self.scheme = Scheme.objects.create(
            name="Gold Scheme",
            description="Test Scheme",
            interest_rate=Decimal('12.00'),
            loan_duration=90,
            minimum_amount=Decimal('1000.00'),
            maximum_amount=Decimal('100000.00'),
            interest_rate_structure={'30': 12, '60': 12, '90': 12},
            start_date=timezone.now().date()
        )

    def test_loan_creation_and_edit_sends_email(self):
        from django.core import mail
        mail.outbox = []

        # Create loan — on_commit fires immediately in TransactionTestCase
        loan = Loan.objects.create(
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('5000.00'),
            interest_rate=Decimal('12.00'),
            processing_fee=50,
            distribution_amount=Decimal('4950.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=90),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=105),
            status='active'
        )

        # Verify creation email sent to recipients
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(sorted(mail.outbox[0].to), sorted(['firstmoneygold@gmail.com', 'hariswealthway@gmail.com']))
        self.assertIn('Loan Created', mail.outbox[0].subject)
        self.assertIn(loan.loan_number, mail.outbox[0].subject)
        self.assertIn('Rs. 5000', mail.outbox[0].body)

        # Clear outbox
        mail.outbox = []

        # Edit loan
        loan.principal_amount = Decimal('6000.00')
        loan.save()

        # Verify edit email sent to recipients
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(sorted(mail.outbox[0].to), sorted(['firstmoneygold@gmail.com', 'hariswealthway@gmail.com']))
        self.assertIn('Loan Edited', mail.outbox[0].subject)


