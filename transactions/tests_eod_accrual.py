from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command

from accounts.models import CustomUser, Customer, Role
from branches.models import Branch
from schemes.models import Scheme
from transactions.models import Loan, InterestAccrualLog, EODBatchExecutionLog
from transactions.services_eod import (
    compute_daily_loan_interest,
    classify_loan_irac,
    run_daily_eod_batch
)
from accounting.models import AccountHead, JournalEntry, JournalItem, JournalEntryType
from accounting.services import ensure_default_chart_of_accounts


class EODInterestAccrualAndIRACTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.branch = Branch.objects.create(
            name="Salem Gold Hub",
            address="100 Car Street",
            city="Salem",
            state="Tamil Nadu",
            zip_code="636001",
            phone="9876543210"
        )

        self.manager_role, _ = Role.objects.get_or_create(name="Branch Manager")
        self.user = CustomUser.objects.create_user(
            username="bm_eod",
            email="bm@fmg.com",
            password="Password123!",
            role=self.manager_role,
            branch=self.branch
        )
        self.client.login(username="bm_eod", password="Password123!")

        self.customer = Customer.objects.create(
            first_name="Kandasamy",
            last_name="Perumal",
            phone="9876500005",
            id_type="aadhar_card",
            id_number="987654321015",
            branch=self.branch
        )

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

        ensure_default_chart_of_accounts(self.branch)

    def test_01_daily_interest_mathematical_precision(self):
        """
        1. Mathematical Precision Test:
        - Principal: ₹1,00,000
        - Annual Rate: 12.00%
        - Formula: (100000 * 12) / (365 * 100) = 32.8767... -> ₹32.88 / day
        """
        loan = Loan.objects.create(
            loan_number="LN-EOD-001",
            customer=self.customer,
            branch=self.branch,
            scheme=self.scheme,
            principal_amount=Decimal('100000'),
            processing_fee=1000,
            distribution_amount=Decimal('99000'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date() - timedelta(days=10),
            due_date=timezone.now().date() + timedelta(days=354),
            grace_period_end=timezone.now().date() + timedelta(days=359),
            status='active'
        )

        daily_accrual, annual_rate = compute_daily_loan_interest(loan)
        self.assertEqual(annual_rate, Decimal('12.00'))
        self.assertEqual(daily_accrual, Decimal('32.88'))

    def test_02_rbi_irac_asset_classification_transitions(self):
        """
        2. RBI IRAC Classification Test:
        - 0 days overdue -> STANDARD (0.25% prov)
        - 25 days overdue -> SMA_0 (0.25% prov)
        - 45 days overdue -> SMA_1 (0.25% prov)
        - 75 days overdue -> SMA_2 (0.25% prov)
        - 100 days overdue -> NPA_SUBSTANDARD (10.00% prov)
        """
        today = timezone.now().date()

        # 1. Standard Asset
        loan_std = Loan.objects.create(
            loan_number="LN-STD-01", customer=self.customer, branch=self.branch, scheme=self.scheme,
            principal_amount=Decimal('50000'), distribution_amount=Decimal('49500'),
            issue_date=today - timedelta(days=30),
            due_date=today + timedelta(days=300),
            grace_period_end=today + timedelta(days=305),
            status='active'
        )
        status, days, prov, npa = classify_loan_irac(loan_std, as_of_date=today)
        self.assertEqual(status, 'STANDARD')
        self.assertEqual(days, 0)
        self.assertEqual(prov, Decimal('0.25'))

        # 2. SMA-0 (25 days overdue)
        loan_sma0 = Loan.objects.create(
            loan_number="LN-SMA0-01", customer=self.customer, branch=self.branch, scheme=self.scheme,
            principal_amount=Decimal('50000'), distribution_amount=Decimal('49500'),
            issue_date=today - timedelta(days=390),
            due_date=today - timedelta(days=30),
            grace_period_end=today - timedelta(days=25),
            status='active'
        )
        status, days, prov, npa = classify_loan_irac(loan_sma0, as_of_date=today)
        self.assertEqual(status, 'SMA_0')
        self.assertEqual(days, 25)
        self.assertEqual(prov, Decimal('0.25'))

        # 3. SMA-1 (45 days overdue)
        loan_sma1 = Loan.objects.create(
            loan_number="LN-SMA1-01", customer=self.customer, branch=self.branch, scheme=self.scheme,
            principal_amount=Decimal('50000'), distribution_amount=Decimal('49500'),
            issue_date=today - timedelta(days=410),
            due_date=today - timedelta(days=50),
            grace_period_end=today - timedelta(days=45),
            status='active'
        )
        status, days, prov, npa = classify_loan_irac(loan_sma1, as_of_date=today)
        self.assertEqual(status, 'SMA_1')
        self.assertEqual(days, 45)
        self.assertEqual(prov, Decimal('0.25'))

        # 4. SMA-2 (75 days overdue)
        loan_sma2 = Loan.objects.create(
            loan_number="LN-SMA2-01", customer=self.customer, branch=self.branch, scheme=self.scheme,
            principal_amount=Decimal('50000'), distribution_amount=Decimal('49500'),
            issue_date=today - timedelta(days=440),
            due_date=today - timedelta(days=80),
            grace_period_end=today - timedelta(days=75),
            status='active'
        )
        status, days, prov, npa = classify_loan_irac(loan_sma2, as_of_date=today)
        self.assertEqual(status, 'SMA_2')
        self.assertEqual(days, 75)
        self.assertEqual(prov, Decimal('0.25'))

        # 5. NPA Substandard (100 days overdue)
        loan_npa = Loan.objects.create(
            loan_number="LN-NPA-01", customer=self.customer, branch=self.branch, scheme=self.scheme,
            principal_amount=Decimal('50000'), distribution_amount=Decimal('49500'),
            issue_date=today - timedelta(days=470),
            due_date=today - timedelta(days=105),
            grace_period_end=today - timedelta(days=100),
            status='active'
        )
        status, days, prov, npa = classify_loan_irac(loan_npa, as_of_date=today)
        self.assertEqual(status, 'NPA_SUBSTANDARD')
        self.assertEqual(days, 100)
        self.assertEqual(prov, Decimal('10.00'))

    def test_03_eod_batch_execution_and_gl_journal_posting(self):
        """
        3. EOD Batch Execution & General Ledger Integration Test:
        - Creates 2 active loans: ₹1,00,000 and ₹2,00,000 (both 12% p.a.).
        - Daily accruals: ₹32.88 + ₹65.75 = ₹98.63.
        - Verifies automated GL Journal Voucher created (Dr 1060 == Cr 4010 == ₹98.63).
        """
        today = timezone.now().date()
        loan1 = Loan.objects.create(
            loan_number="LN-EOD-B1", customer=self.customer, branch=self.branch, scheme=self.scheme,
            principal_amount=Decimal('100000'), distribution_amount=Decimal('99000'), interest_rate=Decimal('12.00'),
            issue_date=today - timedelta(days=5), due_date=today + timedelta(days=359), grace_period_end=today + timedelta(days=364),
            status='active'
        )
        loan2 = Loan.objects.create(
            loan_number="LN-EOD-B2", customer=self.customer, branch=self.branch, scheme=self.scheme,
            principal_amount=Decimal('200000'), distribution_amount=Decimal('198000'), interest_rate=Decimal('12.00'),
            issue_date=today - timedelta(days=5), due_date=today + timedelta(days=359), grace_period_end=today + timedelta(days=364),
            status='active'
        )

        exec_log = run_daily_eod_batch(date=today, branch=self.branch, user=self.user, post_gl=True)

        self.assertEqual(exec_log.total_loans_processed, 2)
        self.assertEqual(exec_log.total_daily_interest_accrued, Decimal('98.63'))
        self.assertEqual(exec_log.standard_count, 2)
        self.assertEqual(exec_log.status, 'COMPLETED')

        # Verify InterestAccrualLog records
        log1 = InterestAccrualLog.objects.get(loan=loan1, date=today)
        self.assertEqual(log1.daily_interest_accrued, Decimal('32.88'))
        self.assertEqual(log1.cumulative_interest, Decimal('32.88'))

        log2 = InterestAccrualLog.objects.get(loan=loan2, date=today)
        self.assertEqual(log2.daily_interest_accrued, Decimal('65.75'))
        self.assertEqual(log2.cumulative_interest, Decimal('65.75'))

        # Verify General Ledger Entry
        self.assertIsNotNone(exec_log.gl_journal_entry)
        je = exec_log.gl_journal_entry
        self.assertEqual(je.total_debit, Decimal('98.63'))
        self.assertEqual(je.total_credit, Decimal('98.63'))
        self.assertTrue(je.is_balanced)

        accrued_asset = AccountHead.objects.get(code='1060')
        income_acc = AccountHead.objects.get(code='4010')
        self.assertEqual(accrued_asset.get_balance(branch=self.branch), Decimal('98.63'))
        self.assertEqual(income_acc.get_balance(branch=self.branch), Decimal('98.63'))

    def test_04_eod_batch_idempotency(self):
        """
        4. Idempotency Test:
        - Running EOD batch twice on the same date updates records in-place without duplicating amounts.
        """
        today = timezone.now().date()
        loan = Loan.objects.create(
            loan_number="LN-IDEMP-01", customer=self.customer, branch=self.branch, scheme=self.scheme,
            principal_amount=Decimal('100000'), distribution_amount=Decimal('99000'), interest_rate=Decimal('12.00'),
            issue_date=today - timedelta(days=5), due_date=today + timedelta(days=359), grace_period_end=today + timedelta(days=364),
            status='active'
        )

        # Run 1
        run_daily_eod_batch(date=today, branch=self.branch, user=self.user, post_gl=True)
        accrual_count_1 = InterestAccrualLog.objects.filter(loan=loan, date=today).count()
        self.assertEqual(accrual_count_1, 1)

        # Run 2 on same date
        run_daily_eod_batch(date=today, branch=self.branch, user=self.user, post_gl=True)
        accrual_count_2 = InterestAccrualLog.objects.filter(loan=loan, date=today).count()
        self.assertEqual(accrual_count_2, 1)

        # Cumulative amount unchanged
        loan.refresh_from_db()
        self.assertEqual(loan.accrued_interest, Decimal('32.88'))

    def test_05_management_command_execution(self):
        """5. Django Management Command Test: call_command('run_eod_batch')."""
        today = timezone.now().date()
        Loan.objects.create(
            loan_number="LN-MGMT-01", customer=self.customer, branch=self.branch, scheme=self.scheme,
            principal_amount=Decimal('60000'), distribution_amount=Decimal('59400'), interest_rate=Decimal('12.00'),
            issue_date=today - timedelta(days=5), due_date=today + timedelta(days=359), grace_period_end=today + timedelta(days=364),
            status='active'
        )

        call_command('run_eod_batch', f'--date={today.strftime("%Y-%m-%d")}', f'--branch={self.branch.id}')
        self.assertTrue(EODBatchExecutionLog.objects.filter(execution_date=today, branch=self.branch).exists())

    def test_06_eod_web_console_views(self):
        """6. Web UI Console View & Action Endpoint Test."""
        # GET EOD Console
        url = reverse('eod_console')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'EOD Operations &amp; RBI IRAC NPA Console')
        self.assertContains(resp, 'Standard')

        # POST Run EOD Batch
        run_url = reverse('eod_run_batch')
        today_str = timezone.now().date().strftime('%Y-%m-%d')
        resp_post = self.client.post(run_url, {'execution_date': today_str, 'branch_id': self.branch.id}, follow=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertContains(resp_post, 'completed successfully')
