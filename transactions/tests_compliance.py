from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from accounts.models import CustomUser, Customer, Role
from branches.models import Branch
from schemes.models import Scheme, DailyGoldRate
from transactions.models import Loan, Payment, DisbursementTransaction
from inventory.models import Category
from transactions.forms import LoanForm


class IncomeTaxComplianceTests(TestCase):
    """
    Test suite for Income Tax Act statutory compliance:
    - Section 269SS / 269T: Disbursal limits (No cash for amounts >= ₹20,000)
    - Section 269ST: Repayment cash ceiling (<= ₹1,99,999 per customer per day)
    - Bank Transfer Advice Mandate generation
    """

    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(
            name="Salem Main Branch",
            address="123 Market Street, Salem",
            city="Salem",
            state="Tamil Nadu",
            zip_code="636001",
            phone="9876543210",
            is_active=True
        )
        self.role, _ = Role.objects.get_or_create(name="Branch Manager")
        self.user = CustomUser.objects.create_user(
            username="manager1",
            email="manager1@example.com",
            password="testpassword123",
            branch=self.branch,
            role=self.role
        )
        self.client.login(username="manager1", password="testpassword123")

        self.customer = Customer.objects.create(
            first_name="Ramesh",
            last_name="Kumar",
            phone="9876543210",
            branch=self.branch,
            id_type="aadhar_card",
            id_number="123456789012",
            bank_account_number="50100234567890",
            bank_ifsc_code="HDFC0001234",
            bank_name="HDFC Bank, Salem",
            bank_beneficiary_name="Ramesh Kumar"
        )

        self.scheme = Scheme.objects.create(
            name="Standard Gold Scheme",
            description="Standard Gold Loan Scheme for Testing",
            interest_rate=Decimal('12.00'),
            loan_duration=364,
            minimum_amount=Decimal('1000.00'),
            maximum_amount=Decimal('1000000.00'),
            start_date=timezone.now().date(),
            status='active',
            branch=self.branch,
            processing_fee_percentage=Decimal('1.00'),
            additional_conditions={'processing_fee_percentage': 1.0}
        )

        self.category, _ = Category.objects.get_or_create(name="Ring")

        # Set up Daily Gold Rate at ₹6,000/g for 22K
        DailyGoldRate.objects.create(
            date=timezone.now().date(),
            rate_24k_per_gram=Decimal('6545'),
            rate_22k_per_gram=Decimal('6000'),
            rate_20k_per_gram=Decimal('5455'),
            rate_18k_per_gram=Decimal('4909'),
            maximum_ltv_percentage=Decimal('75.00'),
            is_active=True,
            updated_by=self.user
        )

    def test_sec_269ss_cash_disbursal_blocked_for_20000_or_above(self):
        """
        Verify that loan disbursal of ₹20,000 or above via CASH is blocked with Sec 269SS error.
        """
        form_data = {
            'customer': self.customer.id,
            'branch': self.branch.id,
            'scheme': self.scheme.id,
            'item_name': 'Gold Ring (1)',
            'item_category': self.category.id,
            'gold_karat': '22',
            'market_price_22k': '6000',
            'gross_weight': '10.000',
            'stone_weight': '0.000',
            'net_weight': '10.000',
            'principal_amount': '25000',
            'processing_fee': '250',
            'distribution_amount': '24750',
            'interest_rate': '12.00',
            'issue_date': timezone.now().date(),
            'due_date': timezone.now().date() + timezone.timedelta(days=364),
            'disbursement_mode': 'CASH',
        }
        form = LoanForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('disbursement_mode', form.errors)
        self.assertTrue(any('Section 269SS' in err for err in form.errors['disbursement_mode']))

    def test_sec_269ss_bank_transfer_for_20000_or_above_succeeds(self):
        """
        Verify that loan disbursal of ₹20,000 or above via BANK_TRANSFER with valid IFSC & Account succeeds.
        """
        form_data = {
            'customer': self.customer.id,
            'branch': self.branch.id,
            'scheme': self.scheme.id,
            'item_name': 'Gold Chain (1)',
            'item_category': self.category.id,
            'gold_karat': '22',
            'market_price_22k': '6000',
            'gross_weight': '10.000',
            'stone_weight': '0.000',
            'net_weight': '10.000',
            'principal_amount': '30000',
            'processing_fee': '300',
            'distribution_amount': '29700',
            'interest_rate': '12.00',
            'issue_date': timezone.now().date(),
            'due_date': timezone.now().date() + timezone.timedelta(days=364),
            'disbursement_mode': 'BANK_TRANSFER',
            'bank_account_number': '50100234567890',
            'bank_ifsc_code': 'HDFC0001234',
            'bank_name': 'HDFC Bank, Salem',
            'bank_beneficiary_name': 'Ramesh Kumar',
            'disbursement_utr': 'UTR987654321',
        }
        form = LoanForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        loan = form.save()
        self.assertIsNotNone(loan.pk)

        # Verify DisbursementTransaction was automatically created
        disbursement = DisbursementTransaction.objects.filter(loan=loan).first()
        self.assertIsNotNone(disbursement)
        self.assertEqual(disbursement.payment_mode, 'BANK_TRANSFER')
        self.assertEqual(disbursement.amount, Decimal('29700'))
        self.assertEqual(disbursement.account_number, '50100234567890')
        self.assertEqual(disbursement.ifsc_code, 'HDFC0001234')

    def test_sec_269ss_invalid_ifsc_format_rejected(self):
        """
        Verify that bank transfer with invalid IFSC code format is rejected.
        """
        form_data = {
            'customer': self.customer.id,
            'branch': self.branch.id,
            'scheme': self.scheme.id,
            'item_name': 'Gold Chain (1)',
            'item_category': self.category.id,
            'gold_karat': '22',
            'market_price_22k': '6000',
            'gross_weight': '10.000',
            'stone_weight': '0.000',
            'net_weight': '10.000',
            'principal_amount': '30000',
            'processing_fee': '300',
            'distribution_amount': '29700',
            'interest_rate': '12.00',
            'issue_date': timezone.now().date(),
            'due_date': timezone.now().date() + timezone.timedelta(days=364),
            'disbursement_mode': 'BANK_TRANSFER',
            'bank_account_number': '50100234567890',
            'bank_ifsc_code': 'INVALID123',  # Invalid format
            'bank_name': 'HDFC Bank',
            'bank_beneficiary_name': 'Ramesh Kumar',
        }
        form = LoanForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('bank_ifsc_code', form.errors)

    def test_sec_269ss_cash_allowed_under_20000(self):
        """
        Verify that loan disbursals < ₹20,000 are permitted in CASH.
        """
        form_data = {
            'customer': self.customer.id,
            'branch': self.branch.id,
            'scheme': self.scheme.id,
            'item_name': 'Gold Earring (1)',
            'item_category': self.category.id,
            'gold_karat': '22',
            'market_price_22k': '6000',
            'gross_weight': '5.000',
            'stone_weight': '0.000',
            'net_weight': '5.000',
            'principal_amount': '15000',
            'processing_fee': '150',
            'distribution_amount': '14850',
            'interest_rate': '12.00',
            'issue_date': timezone.now().date(),
            'due_date': timezone.now().date() + timezone.timedelta(days=364),
            'disbursement_mode': 'CASH',
        }
        form = LoanForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        loan = form.save()
        self.assertIsNotNone(loan.pk)
        
        disbursement = DisbursementTransaction.objects.filter(loan=loan).first()
        self.assertIsNotNone(disbursement)
        self.assertEqual(disbursement.payment_mode, 'CASH')
        self.assertEqual(disbursement.amount, Decimal('14850'))

    def test_sec_269st_daily_cash_repayment_cap(self):
        """
        Verify that aggregate daily cash repayments >= ₹2,00,000 for a single customer are blocked.
        """
        loan = Loan.objects.create(
            loan_number="LN-TEST-269ST-01",
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('300000'),
            processing_fee=3000,
            distribution_amount=Decimal('297000'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='active'
        )

        today = timezone.now().date()

        # Payment 1: ₹1,50,000 in cash -> succeeds
        p1 = Payment.objects.create(
            loan=loan,
            amount=Decimal('150000.00'),
            payment_date=today,
            payment_method='cash',
            received_by=self.user
        )
        self.assertIsNotNone(p1.pk)

        # Payment 2: Attempt another ₹55,000 cash payment on same day (Total = ₹2,05,000 >= ₹2,00,000)
        p2_url = reverse('payment_create', kwargs={'loan_number': loan.loan_number})
        response = self.client.post(p2_url, {
            'amount': '55000.00',
            'payment_date': str(today),
            'payment_method': 'cash',
            'reference_number': '',
            'notes': 'Second cash installment'
        })
        # Should re-render payment form with Section 269ST error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Section 269ST Statutory Violation')

        # Payment 3: Switch to digital mode ('bank_transfer') with ₹55,000 -> succeeds
        response_digital = self.client.post(p2_url, {
            'amount': '55000.00',
            'payment_date': str(today),
            'payment_method': 'bank_transfer',
            'reference_number': 'NEFT123456789',
            'notes': 'Digital settlement'
        })
        self.assertEqual(response_digital.status_code, 302)

    def test_bank_transfer_advice_view(self):
        """
        Verify that Bank Transfer Advice slip view renders with HTTP 200 and correct details.
        """
        loan = Loan.objects.create(
            loan_number="LN-TEST-ADVICE-01",
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('50000'),
            processing_fee=500,
            distribution_amount=Decimal('49500'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='active'
        )
        DisbursementTransaction.objects.create(
            loan=loan,
            payment_mode='BANK_TRANSFER',
            amount=Decimal('49500'),
            account_number='50100234567890',
            ifsc_code='HDFC0001234',
            bank_name='HDFC Bank, Salem',
            beneficiary_name='Ramesh Kumar',
            utr_number='UTR888999111',
            disbursed_by=self.user
        )

    def test_excess_payment_amount_prevented(self):
        """
        Verify that payment amount exceeding outstanding balance (e.g. ₹90,000 for ₹50,000 loan) is blocked.
        """
        loan = Loan.objects.create(
            loan_number="LN-TEST-EXCESS-01",
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('50000'),
            processing_fee=500,
            distribution_amount=Decimal('49500'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='active'
        )

        p_url = reverse('payment_create', kwargs={'loan_number': loan.loan_number})
        # Attempt paying ₹90,000 when total payable is ₹50,000
        response = self.client.post(p_url, {
            'amount': '90000.00',
            'payment_date': str(timezone.now().date()),
            'payment_method': 'bank_transfer',
            'reference_number': 'REF123456',
            'notes': 'Excess test'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'exceeds the outstanding balance')
        self.assertEqual(Payment.objects.filter(loan=loan).count(), 0)

