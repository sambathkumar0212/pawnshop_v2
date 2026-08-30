from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from accounts.models import CustomUser, Customer, Role
from branches.models import Branch, CashTill, CashScrollEntry
from schemes.models import Scheme
from transactions.models import Loan, Payment, DisbursementTransaction


class CashTillAndScrollTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(
            name="Salem Main Branch",
            address="100 Main Road",
            city="Salem",
            state="Tamil Nadu",
            zip_code="636001",
            phone="9876543210"
        )
        self.cashier_role, _ = Role.objects.get_or_create(name="Cashier")
        self.manager_role, _ = Role.objects.get_or_create(name="Branch Manager")

        self.cashier = CustomUser.objects.create_user(
            username="cashier_salem",
            email="cashier@fmg.com",
            password="Password123!",
            role=self.cashier_role,
            branch=self.branch,
            first_name="Priya",
            last_name="Cashier"
        )
        self.manager = CustomUser.objects.create_user(
            username="manager_salem",
            email="manager@fmg.com",
            password="Password123!",
            role=self.manager_role,
            branch=self.branch,
            first_name="Mani",
            last_name="Manager"
        )
        self.branch.manager = self.manager
        self.branch.save()

        self.customer = Customer.objects.create(
            first_name="Ramesh",
            last_name="Kumar",
            phone="9876500001",
            id_type="AADHAAR",
            id_number="123456789012",
            branch=self.branch
        )
        self.scheme = Scheme.objects.create(
            name="Standard Gold Scheme",
            description="Test Gold Scheme",
            interest_rate=Decimal('12.00'),
            loan_duration=364,
            minimum_amount=Decimal('1000.00'),
            maximum_amount=Decimal('500000.00'),
            start_date=timezone.now().date(),
            status='active',
            branch=self.branch
        )

        self.client.login(username="cashier_salem", password="Password123!")

    def test_01_cash_till_bod_opening(self):
        """1. Opening Till Test: Open register with ₹50,000."""
        url = reverse('cash_till_open')
        response = self.client.post(url, {
            'opening_balance': '50000.00'
        })
        self.assertEqual(response.status_code, 302)

        till = CashTill.objects.get(branch=self.branch, date=timezone.now().date(), cashier=self.cashier)
        self.assertEqual(till.opening_balance, Decimal('50000.00'))
        self.assertEqual(till.closing_balance_system, Decimal('50000.00'))
        self.assertEqual(till.status, 'open')
        self.assertEqual(till.entries.filter(entry_type='OPENING').count(), 1)

    def test_02_live_scroll_stream_and_balance_sync(self):
        """
        2. Live Scroll Test:
        - Open till with ₹50,000.
        - Disburse cash loan of ₹15,000.
        - Receive cash repayment of ₹5,000.
        - Verify till balance updates to ₹40,000 in real time.
        """
        # Open till
        till = CashTill.objects.create(
            branch=self.branch,
            cashier=self.cashier,
            date=timezone.now().date(),
            opening_balance=Decimal('50000.00'),
            status='open'
        )

        # Disburse cash loan of ₹15,000
        loan1 = Loan.objects.create(
            loan_number="LN-CASH-01",
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('15000'),
            processing_fee=150,
            distribution_amount=Decimal('14850'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='active'
        )
        DisbursementTransaction.objects.create(
            loan=loan1,
            payment_mode='CASH',
            amount=Decimal('15000'),
            disbursed_by=self.cashier
        )

        # Receive cash repayment of ₹5,000 on another loan
        loan2 = Loan.objects.create(
            loan_number="LN-CASH-02",
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('30000'),
            processing_fee=300,
            distribution_amount=Decimal('29700'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date() - timezone.timedelta(days=30),
            due_date=timezone.now().date() + timezone.timedelta(days=334),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=339),
            status='active'
        )
        Payment.objects.create(
            loan=loan2,
            amount=Decimal('5000.00'),
            payment_date=timezone.now().date(),
            payment_method='cash',
            received_by=self.cashier
        )

        # Sync live till transactions
        till.sync_live_transactions()
        self.assertEqual(till.cash_inwards, Decimal('5000.00'))
        self.assertEqual(till.cash_outwards, Decimal('15000.00'))
        # 50,000 + 5,000 - 15,000 = 40,000
        self.assertEqual(till.closing_balance_system, Decimal('40000.00'))

        # Check Dashboard view
        dash_url = reverse('cash_till_dashboard')
        response = self.client.get(dash_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '40,000.00')

    def test_03_denomination_reconciliation_zero_variance(self):
        """
        3. Denomination Calculator Test:
        - Enter 80 notes of ₹500 (= ₹40,000).
        - Verify physical balance equals system balance and status becomes 'reconciled'.
        """
        till = CashTill.objects.create(
            branch=self.branch,
            cashier=self.cashier,
            date=timezone.now().date(),
            opening_balance=Decimal('40000.00'),
            closing_balance_system=Decimal('40000.00'),
            status='open'
        )

        reconcile_url = reverse('cash_till_reconcile', kwargs={'pk': till.pk})
        response = self.client.post(reconcile_url, {
            'count_500': 80,
            'count_200': 0,
            'count_100': 0,
            'count_50': 0,
            'count_20': 0,
            'count_10': 0,
            'count_5': 0,
            'count_coins': 0,
            'closing_balance_physical': '40000.00',
            'discrepancy_reason': ''
        })
        self.assertEqual(response.status_code, 302)

        till.refresh_from_db()
        self.assertEqual(till.closing_balance_physical, Decimal('40000.00'))
        self.assertEqual(till.variance, Decimal('0.00'))
        self.assertEqual(till.status, 'reconciled')
        self.assertEqual(till.denomination_breakdown.get('500'), 80)

    def test_04_mismatch_warning_and_mandatory_discrepancy_explanation(self):
        """
        4. Mismatch Warning Test:
        - Physical cash entered is ₹39,000 (Shortage of ₹1,000 against ₹40,000 system balance).
        - Submitting without explanation must fail validation.
        - Submitting with explanation records status 'mismatched'.
        """
        till = CashTill.objects.create(
            branch=self.branch,
            cashier=self.cashier,
            date=timezone.now().date(),
            opening_balance=Decimal('40000.00'),
            closing_balance_system=Decimal('40000.00'),
            status='open'
        )

        reconcile_url = reverse('cash_till_reconcile', kwargs={'pk': till.pk})
        # Attempt without discrepancy reason
        response = self.client.post(reconcile_url, {
            'count_500': 78,  # 78 * 500 = 39,000
            'count_200': 0,
            'count_100': 0,
            'count_50': 0,
            'count_20': 0,
            'count_10': 0,
            'count_5': 0,
            'count_coins': 0,
            'closing_balance_physical': '39000.00',
            'discrepancy_reason': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'discrepancy_reason', 'Discrepancy explanation is required when physical cash does not match system balance.')

        # Submit with valid discrepancy reason
        response2 = self.client.post(reconcile_url, {
            'count_500': 78,
            'count_200': 0,
            'count_100': 0,
            'count_50': 0,
            'count_20': 0,
            'count_10': 0,
            'count_5': 0,
            'count_coins': 0,
            'closing_balance_physical': '39000.00',
            'discrepancy_reason': 'Temporary shortage of Rs 1,000 pending investigation.'
        })
        self.assertEqual(response2.status_code, 302)

        till.refresh_from_db()
        self.assertEqual(till.closing_balance_physical, Decimal('39000.00'))
        self.assertEqual(till.variance, Decimal('-1000.00'))
        self.assertEqual(till.status, 'mismatched')

    def test_05_cash_bank_deposit(self):
        """5. Bank Deposit Test: Transfer ₹10,000 from till to bank."""
        till = CashTill.objects.create(
            branch=self.branch,
            cashier=self.cashier,
            date=timezone.now().date(),
            opening_balance=Decimal('50000.00'),
            status='open'
        )

        deposit_url = reverse('cash_till_bank_deposit', kwargs={'pk': till.pk})
        response = self.client.post(deposit_url, {
            'amount': '10000.00',
            'reference_id': 'CHALLAN-99901',
            'description': 'Remitted cash to HDFC Bank Main Account'
        })
        self.assertEqual(response.status_code, 302)

        till.refresh_from_db()
        till.sync_live_transactions()
        self.assertEqual(till.cash_to_bank, Decimal('10000.00'))
        self.assertEqual(till.closing_balance_system, Decimal('40000.00'))

    def test_06_manager_signoff_and_close_register(self):
        """6. Manager Sign-off Test: Manager approves and closes daily register."""
        till = CashTill.objects.create(
            branch=self.branch,
            cashier=self.cashier,
            date=timezone.now().date(),
            opening_balance=Decimal('40000.00'),
            closing_balance_system=Decimal('40000.00'),
            closing_balance_physical=Decimal('40000.00'),
            status='reconciled'
        )

        # Login as manager
        self.client.login(username="manager_salem", password="Password123!")

        signoff_url = reverse('cash_till_signoff', kwargs={'pk': till.pk})
        response = self.client.post(signoff_url)
        self.assertEqual(response.status_code, 302)

        till.refresh_from_db()
        self.assertEqual(till.status, 'closed')
        self.assertEqual(till.verified_by_manager, self.manager)
        self.assertIsNotNone(till.reconciled_at)

    def test_07_printable_cash_scroll_and_history_views(self):
        """7. Printable Scroll & History Views return HTTP 200 with proper context."""
        till = CashTill.objects.create(
            branch=self.branch,
            cashier=self.cashier,
            date=timezone.now().date(),
            opening_balance=Decimal('50000.00'),
            closing_balance_system=Decimal('50000.00'),
            closing_balance_physical=Decimal('50000.00'),
            denomination_breakdown={'500': 100},
            status='closed',
            verified_by_manager=self.manager
        )

        print_url = reverse('cash_till_print', kwargs={'pk': till.pk})
        response = self.client.get(print_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DAILY CASH SCROLL')
        self.assertContains(response, 'Salem Main Branch')
        self.assertContains(response, '50,000.00')

        hist_url = reverse('cash_till_history')
        response_hist = self.client.get(hist_url)
        self.assertEqual(response_hist.status_code, 200)
        self.assertContains(response_hist, 'Daily Cash Register Logs')
