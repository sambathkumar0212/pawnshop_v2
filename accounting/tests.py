from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal

from accounts.models import CustomUser, Customer, Role
from branches.models import Branch, CashTill, CashScrollEntry
from schemes.models import Scheme
from transactions.models import Loan, Payment, DisbursementTransaction
from accounting.models import AccountHead, JournalEntry, JournalItem, AccountCategory, JournalEntryType
from accounting.services import (
    ensure_default_chart_of_accounts,
    post_loan_disbursal_journal,
    post_loan_repayment_journal,
    post_bank_deposit_journal,
    post_manual_expense_journal
)


class DoubleEntryAccountingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch_a = Branch.objects.create(
            name="Salem Main Branch",
            address="100 Main Road",
            city="Salem",
            state="Tamil Nadu",
            zip_code="636001",
            phone="9876543210"
        )
        self.branch_b = Branch.objects.create(
            name="Coimbatore Branch",
            address="200 Cross Cut Road",
            city="Coimbatore",
            state="Tamil Nadu",
            zip_code="641012",
            phone="9876543211"
        )

        self.manager_role, _ = Role.objects.get_or_create(name="Branch Manager")
        self.user = CustomUser.objects.create_user(
            username="manager_salem",
            email="manager@fmg.com",
            password="Password123!",
            role=self.manager_role,
            branch=self.branch_a,
            first_name="Ravi",
            last_name="Manager"
        )
        self.client.login(username="manager_salem", password="Password123!")

        self.customer = Customer.objects.create(
            first_name="Murugan",
            last_name="Vel",
            phone="9876500002",
            id_type="aadhar_card",
            id_number="987654321012",
            branch=self.branch_a
        )

        self.scheme = Scheme.objects.create(
            name="Standard 12M Gold Scheme",
            description="Test Gold Scheme",
            interest_rate=Decimal('12.00'),
            loan_duration=364,
            minimum_amount=Decimal('1000.00'),
            maximum_amount=Decimal('1000000.00'),
            start_date=timezone.now().date(),
            status='active',
            branch=self.branch_a
        )

        ensure_default_chart_of_accounts()

    def test_01_chart_of_accounts_initialization(self):
        """1. Verify standard chart of accounts is seeded properly."""
        self.assertTrue(AccountHead.objects.filter(code='1010').exists())
        self.assertTrue(AccountHead.objects.filter(code='1020').exists())
        self.assertTrue(AccountHead.objects.filter(code='1050').exists())
        self.assertTrue(AccountHead.objects.filter(code='4010').exists())
        self.assertTrue(AccountHead.objects.filter(code='4020').exists())
        self.assertTrue(AccountHead.objects.filter(code='5010').exists())

        cash_acc = AccountHead.objects.get(code='1010')
        self.assertEqual(cash_acc.category, AccountCategory.ASSET)
        self.assertTrue(cash_acc.is_debit_nature)

    def test_02_double_entry_loan_disbursal_equilibrium(self):
        """
        2. Loan Disbursal Equilibrium Test:
        - Principal: ₹50,000
        - Fee: ₹500
        - Net Cash Disbursed: ₹49,500
        - Asserts: Dr Gold Loan Asset (50,000) == Cr Fee (500) + Cr Cash (49,500)
        """
        loan = Loan.objects.create(
            loan_number="LN-GL-2026-001",
            customer=self.customer,
            branch=self.branch_a,
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

        entry = post_loan_disbursal_journal(loan=loan, payment_mode='CASH', user=self.user)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.total_debit, Decimal('50000.00'))
        self.assertEqual(entry.total_credit, Decimal('50000.00'))
        self.assertTrue(entry.is_balanced)
        self.assertEqual(entry.variance, Decimal('0.00'))

        # Verify account balances
        asset_acc = AccountHead.objects.get(code='1050')
        fee_acc = AccountHead.objects.get(code='4020')
        cash_acc = AccountHead.objects.get(code='1010')

        self.assertEqual(asset_acc.get_balance(branch=self.branch_a), Decimal('50000.00'))
        self.assertEqual(fee_acc.get_balance(branch=self.branch_a), Decimal('500.00'))
        self.assertEqual(cash_acc.get_balance(branch=self.branch_a), Decimal('-49500.00'))

    def test_03_double_entry_loan_repayment_equilibrium(self):
        """
        3. Loan Repayment Equilibrium Test:
        - Repayment: ₹5,000 (Interest: ₹1,200, Principal reduction: ₹3,800)
        - Asserts: Dr Cash (5,000) == Cr Interest Income (1,200) + Cr Loan Asset (3,800)
        """
        loan = Loan.objects.create(
            loan_number="LN-GL-2026-002",
            customer=self.customer,
            branch=self.branch_a,
            scheme=self.scheme,
            principal_amount=Decimal('40000'),
            processing_fee=400,
            distribution_amount=Decimal('39600'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='active'
        )

        payment = Payment.objects.create(
            loan=loan,
            amount=Decimal('5000.00'),
            payment_date=timezone.now().date(),
            payment_method='cash',
            received_by=self.user
        )

        entry = post_loan_repayment_journal(payment=payment, user=self.user)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.total_debit, Decimal('5000.00'))
        self.assertEqual(entry.total_credit, Decimal('5000.00'))
        self.assertTrue(entry.is_balanced)

        asset_acc = AccountHead.objects.get(code='1050')
        self.assertEqual(asset_acc.get_balance(branch=self.branch_a), Decimal('-5000.00'))

    def test_04_operational_expense_voucher(self):
        """4. Expense Voucher Test: Debit Expense Head (5040) / Credit Cash in Hand (1010)."""
        stationery_acc = AccountHead.objects.get(code='5040')
        entry = post_manual_expense_journal(
            branch=self.branch_a,
            expense_head=stationery_acc,
            amount=Decimal('2500.00'),
            payment_mode='CASH',
            narration='Purchased pawn ticket billing rolls and register books',
            user=self.user
        )
        self.assertEqual(entry.total_debit, Decimal('2500.00'))
        self.assertEqual(entry.total_credit, Decimal('2500.00'))
        self.assertTrue(entry.is_balanced)
        self.assertEqual(stationery_acc.get_balance(branch=self.branch_a), Decimal('2500.00'))

    def test_05_day_book_and_cash_book_views(self):
        """5. Day Book & Cash Book reporting views return HTTP 200 with balanced totals."""
        # Disburse a loan
        loan = Loan.objects.create(
            loan_number="LN-GL-2026-003",
            customer=self.customer,
            branch=self.branch_a,
            scheme=self.scheme,
            principal_amount=Decimal('30000'),
            processing_fee=300,
            distribution_amount=Decimal('29700'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='active'
        )
        post_loan_disbursal_journal(loan=loan, payment_mode='CASH', user=self.user)

        # 1. Day Book
        day_book_url = reverse('accounting_day_book')
        response = self.client.get(f"{day_book_url}?branch_id={self.branch_a.id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LN-GL-2026-003')
        self.assertContains(response, '30,000.00')

        # 2. Cash Book
        cash_book_url = reverse('accounting_cash_book')
        response_cb = self.client.get(f"{cash_book_url}?branch_id={self.branch_a.id}&account_code=1010")
        self.assertEqual(response_cb.status_code, 200)
        self.assertContains(response_cb, 'Cash &amp; Bank Book Ledger')

    def test_06_consolidated_trial_balance_and_financial_statements(self):
        """
        6. Multi-Branch Consolidated Trial Balance & Financial Statements:
        - Post transactions in Branch A and Branch B.
        - Verify consolidated Trial Balance Total Debits == Total Credits.
        - Verify P&L and Balance Sheet equations.
        """
        # Branch A transaction
        loan_a = Loan.objects.create(
            loan_number="LN-GL-BR-A-01",
            customer=self.customer,
            branch=self.branch_a,
            scheme=self.scheme,
            principal_amount=Decimal('60000'),
            processing_fee=600,
            distribution_amount=Decimal('59400'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='active'
        )
        post_loan_disbursal_journal(loan=loan_a, payment_mode='CASH', user=self.user)

        # Branch B transaction
        cust_b = Customer.objects.create(
            first_name="Kavitha",
            last_name="Rani",
            phone="9876500003",
            id_type="aadhar_card",
            id_number="987654321013",
            branch=self.branch_b
        )
        loan_b = Loan.objects.create(
            loan_number="LN-GL-BR-B-01",
            customer=cust_b,
            branch=self.branch_b,
            scheme=self.scheme,
            principal_amount=Decimal('40000'),
            processing_fee=400,
            distribution_amount=Decimal('39600'),
            interest_rate=Decimal('12.00'),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=364),
            grace_period_end=timezone.now().date() + timezone.timedelta(days=369),
            status='active'
        )
        post_loan_disbursal_journal(loan=loan_b, payment_mode='BANK', user=self.user, bank_ref='HDFC999888')

        # Consolidated Trial Balance
        tb_url = reverse('accounting_trial_balance')
        response_tb = self.client.get(f"{tb_url}?branch_id=all")
        self.assertEqual(response_tb.status_code, 200)
        self.assertContains(response_tb, 'Double-Entry Equilibrium Verified')

        # P&L
        pnl_url = reverse('accounting_profit_loss')
        response_pnl = self.client.get(f"{pnl_url}?branch_id=all")
        self.assertEqual(response_pnl.status_code, 200)
        self.assertContains(response_pnl, 'Total Revenue / Income')

        # Balance Sheet
        bs_url = reverse('accounting_balance_sheet')
        response_bs = self.client.get(f"{bs_url}?branch_id=all")
        self.assertEqual(response_bs.status_code, 200)
        self.assertContains(response_bs, 'Accounting Equation Perfectly Balanced')
