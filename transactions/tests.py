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

    def test_processing_fee_paid_calculations(self):
        # Create a loan with is_processing_fee_paid = True
        # Base distribution amount = 10,000 (not principal - processing fee)
        # For 12% p.a.:
        # Monthly rate = 1%
        # Monthly interest amount = 10,000 * 1% = 100.00
        # Daily interest amount = 10,000 * (12 / 36500) = 3.29
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
            distribution_amount=Decimal('10000.00'),
            is_processing_fee_paid=True,
            issue_date=issue_date,
            due_date=due_date,
            grace_period_end=grace_period_end,
            status='active'
        )
        
        # Test basic monthly and daily interest rates/amounts (based on 10,000)
        self.assertEqual(loan.original_distribution_amount, Decimal('10000.00'))
        self.assertEqual(loan.monthly_interest['amount'], Decimal('100.00'))
        self.assertEqual(loan.daily_interest_amount, Decimal('3.29')) # 10000 * 12 / 36500 = 3.28767 -> 3.29
        
        # Test accrued interest till date
        # 1 month accrued: 1 * 100.00 = 100.00
        self.assertEqual(loan.interest_till_date_monthly_basis, Decimal('100.00'))
        
        # Strictly daily-based interest till date:
        # interest = 10000 * (12/36500) * 15 = 49.32
        self.assertEqual(loan.interest_till_date_daily_basis, Decimal('49.32'))

    def test_distribution_amount_vs_distribution_with_deduction(self):
        """
        distribution_amount = principal - processing_fee  (always)

        distribution_amount_with_deduction = distribution_amount
            - (processing_fee        if is_processing_fee_paid)
            - (first_month_interest  if is_first_month_interest_paid)

        For principal=10000, proc_fee=100, 12% p.a. (1% monthly = Rs 100):
            Distribution Amount = 10000 - 100 = 9900

            Case 1 (neither paid):       9900 - 0   - 0   = 9900
            Case 2 (proc fee only):      9900 - 100 - 0   = 9800
            Case 3 (1st month only):     9900 - 0   - 100 = 9800
            Case 4 (both paid):          9900 - 100 - 100 = 9700
        """
        base_kwargs = dict(
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('10000.00'),
            interest_rate=Decimal('12.00'),   # 1% monthly = Rs 100
            processing_fee=100,
            distribution_amount=Decimal('9900.00'),  # principal - processing_fee
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=90),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=105),
            status='active'
        )

        # Case 1: Neither paid upfront → distribution_amount unchanged
        loan1 = Loan.objects.create(**{**base_kwargs,
            'is_processing_fee_paid': False,
            'is_first_month_interest_paid': False
        })
        self.assertEqual(loan1.distribution_amount_with_deduction, Decimal('9900.00'))

        # Case 2: Only processing fee paid upfront → deduct proc_fee from distribution_amount
        loan2 = Loan.objects.create(**{**base_kwargs,
            'is_processing_fee_paid': True,
            'is_first_month_interest_paid': False
        })
        self.assertEqual(loan2.distribution_amount_with_deduction, Decimal('9800.00'))  # 9900 - 100

        # Case 3: Only 1st month interest paid upfront → deduct first_month_interest only (based on distribution_amount = 9900)
        # Interest = 9900 * 1% = 99.00. Result = 9900 - 99 = 9801.00
        loan3 = Loan.objects.create(**{**base_kwargs,
            'is_processing_fee_paid': False,
            'is_first_month_interest_paid': True
        })
        self.assertEqual(loan3.distribution_amount_with_deduction, Decimal('9801.00'))

        # Case 4: Both paid upfront → deduct both
        # Result = 9900 - 100 - 99 = 9701.00
        loan4 = Loan.objects.create(**{**base_kwargs,
            'is_processing_fee_paid': True,
            'is_first_month_interest_paid': True
        })
        self.assertEqual(loan4.distribution_amount_with_deduction, Decimal('9701.00'))


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
        creation_mail = mail.outbox[0]
        self.assertEqual(sorted(creation_mail.to), sorted(['firstmoneygold@gmail.com', 'hariswealthway@gmail.com']))
        self.assertIn('Loan Created', creation_mail.subject)
        self.assertIn(loan.loan_number, creation_mail.subject)
        self.assertIn('Rs. 5000', creation_mail.body)
        self.assertEqual(len(creation_mail.alternatives), 1)
        html_content = creation_mail.alternatives[0][0]
        self.assertIn('Loan Created', html_content)
        self.assertIn('Rs. 5000', html_content)

        # Clear outbox
        mail.outbox = []

        # Edit loan
        loan.principal_amount = Decimal('6000.00')
        loan.interest_rate = Decimal('14.00')
        loan.save()

        # Verify edit email sent to recipients with highlighted changes
        self.assertEqual(len(mail.outbox), 1)
        edit_mail = mail.outbox[0]
        self.assertEqual(sorted(edit_mail.to), sorted(['firstmoneygold@gmail.com', 'hariswealthway@gmail.com']))
        self.assertIn('Loan Edited', edit_mail.subject)
        self.assertIn(loan.loan_number, edit_mail.subject)
        
        # Verify plain-text modified values highlighting
        self.assertIn('MODIFIED / EDITED VALUES', edit_mail.body)
        self.assertIn('Principal Amount: Rs. 5000 -> Rs. 6000', edit_mail.body)
        self.assertIn('Interest Rate: 12.00% -> 14.00%', edit_mail.body)
        self.assertIn('[UPDATED] Principal Amount: Rs. 6000 (Previous: Rs. 5000)', edit_mail.body)
        self.assertIn('[UPDATED] Interest Rate: 14.00% (Previous: 12.00%)', edit_mail.body)

        # Verify HTML modified values highlighting
        self.assertEqual(len(edit_mail.alternatives), 1)
        edit_html = edit_mail.alternatives[0][0]
        self.assertIn('Loan Edited / Updated', edit_html)
        self.assertIn('Highlighted Modified Values', edit_html)
        self.assertIn('Rs. 5000', edit_html)
        self.assertIn('Rs. 6000', edit_html)
        self.assertIn('12.00%', edit_html)
        self.assertIn('14.00%', edit_html)
        self.assertIn('UPDATED', edit_html)
        self.assertIn('row-highlighted', edit_html)



