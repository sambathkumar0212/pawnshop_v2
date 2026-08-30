from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError

from accounts.models import CustomUser, Customer, Role
from branches.models import Branch
from schemes.models import Scheme, DailyGoldRate
from inventory.models import Item, Category
from transactions.models import Loan, LoanItem, Payment, PartialReleaseRecord
from transactions.services_partial_release import (
    calculate_item_market_value,
    evaluate_partial_release,
    execute_partial_release
)
from accounting.services import ensure_default_chart_of_accounts


class PartialOrnamentReleaseTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.branch = Branch.objects.create(
            name="Madurai Gold Hub",
            address="50 West Tower Street",
            city="Madurai",
            state="Tamil Nadu",
            zip_code="625001",
            phone="9876543211"
        )

        self.manager_role, _ = Role.objects.get_or_create(name="Branch Manager")
        self.user = CustomUser.objects.create_user(
            username="bm_madurai",
            email="bm_madurai@fmg.com",
            password="Password123!",
            role=self.manager_role,
            branch=self.branch
        )
        self.client.login(username="bm_madurai", password="Password123!")

        self.customer = Customer.objects.create(
            first_name="Meenakshi",
            last_name="Sundaram",
            phone="9876500008",
            id_type="aadhar_card",
            id_number="987654321099",
            branch=self.branch
        )

        self.category = Category.objects.create(name="Gold Jewellery", slug="gold-jewellery")

        self.scheme = Scheme.objects.create(
            name="12M Classic Gold Scheme",
            interest_rate=Decimal('12.00'),
            loan_duration=364,
            minimum_amount=Decimal('1000.00'),
            maximum_amount=Decimal('10000000.00'),
            start_date=timezone.now().date(),
            status='active',
            branch=self.branch
        )

        # Set 22K daily gold rate = Rs. 7,000 / gram
        self.gold_rate = DailyGoldRate.objects.create(
            date=timezone.now().date(),
            rate_22k_per_gram=Decimal('7000.00'),
            rate_24k_per_gram=Decimal('7600.00'),
            rate_18k_per_gram=Decimal('5700.00'),
            updated_by=self.user
        )

        ensure_default_chart_of_accounts(self.branch)

        # Create Loan with ₹1,00,000 principal
        self.loan = Loan.objects.create(
            loan_number="LN-PART-001",
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('100000'),
            distribution_amount=Decimal('99000'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date() - timedelta(days=15),
            due_date=timezone.now().date() + timedelta(days=349),
            grace_period_end=timezone.now().date() + timedelta(days=354),
            status='active'
        )

        # Create 3 Ornaments:
        # Item 1: Gold Ring (7.143g @ 22K -> ₹50,001 approx)
        # Item 2: Gold Bangle (7.143g @ 22K -> ₹50,001 approx)
        # Item 3: Gold Chain (7.143g @ 22K -> ₹50,001 approx)
        # Total Collateral Market Value = ~₹1,50,000
        self.inv_item1 = Item.objects.create(name="22K Gold Ring", category=self.category, branch=self.branch, status='pawned')
        self.loan_item1 = LoanItem.objects.create(
            loan=self.loan, item=self.inv_item1, quantity=1,
            gold_karat=Decimal('22.00'), gross_weight=Decimal('7.500'), net_weight=Decimal('7.143'),
            market_price_22k=Decimal('7000.00'), status='pledged'
        )

        self.inv_item2 = Item.objects.create(name="22K Gold Bangle", category=self.category, branch=self.branch, status='pawned')
        self.loan_item2 = LoanItem.objects.create(
            loan=self.loan, item=self.inv_item2, quantity=1,
            gold_karat=Decimal('22.00'), gross_weight=Decimal('7.500'), net_weight=Decimal('7.143'),
            market_price_22k=Decimal('7000.00'), status='pledged'
        )

        self.inv_item3 = Item.objects.create(name="22K Gold Chain", category=self.category, branch=self.branch, status='pawned')
        self.loan_item3 = LoanItem.objects.create(
            loan=self.loan, item=self.inv_item3, quantity=1,
            gold_karat=Decimal('22.00'), gross_weight=Decimal('7.500'), net_weight=Decimal('7.143'),
            market_price_22k=Decimal('7000.00'), status='pledged'
        )

    def test_01_collateral_valuation_and_initial_ltv(self):
        """1. Verify individual item valuation and loan collateral total."""
        val1 = calculate_item_market_value(self.loan_item1, self.gold_rate.rate_22k_per_gram)
        self.assertEqual(val1, Decimal('50001.00'))

        eval_res = evaluate_partial_release(self.loan, [], principal_repayment=Decimal('0.00'))
        self.assertEqual(eval_res['total_collateral_value'], Decimal('150003.00'))
        self.assertEqual(eval_res['current_ltv'], Decimal('66.67'))  # 100000 / 150003 * 100

    def test_02_ltv_breach_blocks_partial_release(self):
        """
        2. LTV Safety Gate Test:
        - Customer attempts to release Item 1 and Item 2 (total released = ~₹1,00,000).
        - Retained collateral = Item 3 (Chain = ₹50,001).
        - Customer offers only ₹10,000 principal reduction.
        - Resulting Principal = ₹90,000.
        - Resulting LTV = 90000 / 50001 = 179.99% (> 75% max cap).
        - Verify system rejects release with ValidationError and computes exact required shortfall.
        """
        eval_res = evaluate_partial_release(
            self.loan,
            [self.loan_item1.pk, self.loan_item2.pk],
            principal_repayment=Decimal('10000.00')
        )
        self.assertFalse(eval_res['is_eligible'])
        self.assertGreater(eval_res['new_ltv'], Decimal('75.00'))
        self.assertEqual(eval_res['min_principal_required'], Decimal('67664.35'))
        self.assertEqual(eval_res['shortfall'], Decimal('57664.35'))


        # Direct execution attempt must raise ValidationError
        with self.assertRaises(ValidationError):
            execute_partial_release(
                loan=self.loan,
                items_to_release_pks=[self.loan_item1.pk, self.loan_item2.pk],
                principal_paid=Decimal('10000.00'),
                payment_method='cash',
                user=self.user
            )

    def test_03_successful_partial_release_with_compliant_ltv(self):
        """
        3. Compliant Partial Release Test:
        - Releasing Item 1 (Ring) and Item 2 (Bangle).
        - Retained collateral = Item 3 (Chain = ₹50,001).
        - Customer pays ₹65,000 principal (New principal = ₹35,000).
        - Resulting LTV = 35000 / 50001 = 69.99% (<= 75% max cap).
        - Verify release succeeds, item status updates, and voucher record is created.
        """
        record = execute_partial_release(
            loan=self.loan,
            items_to_release_pks=[self.loan_item1.pk, self.loan_item2.pk],
            principal_paid=Decimal('65000.00'),
            interest_paid=Decimal('500.00'),
            payment_method='cash',
            user=self.user,
            witness_name="Branch Custodian",
            notes="Returned 2 ornaments in good condition"
        )

        self.assertIsNotNone(record)
        self.assertTrue(record.release_number.startswith('REL-'))
        self.assertEqual(record.principal_paid, Decimal('65000.00'))
        self.assertEqual(record.interest_paid, Decimal('500.00'))
        self.assertEqual(record.new_outstanding_principal, Decimal('35000.00'))
        self.assertLessEqual(record.new_ltv_percentage, Decimal('75.00'))
        self.assertEqual(record.released_items.count(), 2)

        # Verify Loan financial state
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.principal_amount, Decimal('35000.00'))

        # Verify Item statuses
        self.loan_item1.refresh_from_db()
        self.assertEqual(self.loan_item1.status, 'released')
        self.assertIsNotNone(self.loan_item1.released_at)

        self.loan_item2.refresh_from_db()
        self.assertEqual(self.loan_item2.status, 'released')

        self.loan_item3.refresh_from_db()
        self.assertEqual(self.loan_item3.status, 'pledged')

        # Verify Payment record
        payment = Payment.objects.filter(loan=self.loan).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal('65500.00'))

    def test_04_partial_release_views_and_voucher_download(self):
        """4. Web UI Form, AJAX Simulation, and Voucher View Test."""
        # 1. GET Partial Release Form
        url = reverse('loan_partial_release', kwargs={'loan_number': self.loan.loan_number})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Partial Ornament Release')
        self.assertContains(resp, '22K Gold Ring')

        # 2. AJAX Simulation Endpoint
        sim_resp = self.client.get(url, {
            'simulate': '1',
            'item_ids[]': [self.loan_item1.pk],
            'principal_payment': '30000.00'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(sim_resp.status_code, 200)
        sim_data = sim_resp.json()
        self.assertTrue(sim_data['is_eligible'])
        self.assertEqual(sim_data['released_count'], 1)

        # 3. POST Release Form
        post_resp = self.client.post(url, {
            'item_ids': [self.loan_item1.pk],
            'principal_paid': '40000.00',
            'interest_paid': '0.00',
            'payment_method': 'cash'
        }, follow=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertContains(post_resp, 'PARTIAL ORNAMENT RELEASE VOUCHER')

        # 4. GET Release Voucher
        record = PartialReleaseRecord.objects.filter(loan=self.loan).first()
        self.assertIsNotNone(record)
        voucher_url = reverse('loan_partial_release_voucher', kwargs={'loan_number': self.loan.loan_number, 'release_id': record.id})
        voucher_resp = self.client.get(voucher_url)
        self.assertEqual(voucher_resp.status_code, 200)
        self.assertContains(voucher_resp, record.release_number)
        self.assertContains(voucher_resp, 'Ornaments Released to Customer')
        self.assertContains(voucher_resp, 'Ornaments Retained in Safe Custody')
