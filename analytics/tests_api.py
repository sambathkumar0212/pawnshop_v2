from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from decimal import Decimal

from branches.models import Branch
from accounts.models import Customer
from inventory.models import Item, Category
from transactions.models import Loan, Payment, LoanItem

User = get_user_model()


class DashboardSummaryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.branch = Branch.objects.create(
            name="Main Gold Branch",
            phone="9876543210",
            address="100 Jeweler Street",
            city="Chennai",
            state="Tamil Nadu",
            zip_code="600001",
            is_active=True
        )
        self.user = User.objects.create_user(
            username="owner_user",
            email="owner@pawnshop.com",
            password="ownerPassword123!",
            first_name="Shop",
            last_name="Owner",
            branch=self.branch,
            is_superuser=True,
            is_active=True
        )
        self.customer = Customer.objects.create(
            first_name="Ramesh",
            last_name="Kumar",
            phone="9840112233",
            address="45 Market Road",
            branch=self.branch
        )
        self.category = Category.objects.create(name="Gold Bangles", slug="gold-bangles")
        self.item = Item.objects.create(
            item_id="ITEM-TEST-001",
            name="22K Gold Bangles",
            description="Gold Bangles 22K",
            category=self.category,
            branch=self.branch,
            status="pawned",
            appraised_value=Decimal('50000.00')
        )
        self.today = timezone.now().date()
        self.loan = Loan.objects.create(
            loan_number="TEST-LN-001",
            customer=self.customer,
            branch=self.branch,
            principal_amount=Decimal('40000.00'),
            interest_rate=Decimal('18.00'),
            issue_date=self.today,
            due_date=self.today + timezone.timedelta(days=90),
            grace_period_end=self.today + timezone.timedelta(days=97),
            status="active"
        )
        self.loan_item = LoanItem.objects.create(
            loan=self.loan,
            item=self.item,
            quantity=1,
            gold_karat=Decimal('22.00'),
            gross_weight=Decimal('16.500'),
            net_weight=Decimal('15.800'),
            market_price_22k=Decimal('6200.00'),
            status="pledged"
        )
        self.payment = Payment.objects.create(
            loan=self.loan,
            amount=Decimal('2000.00'),
            payment_date=self.today,
            payment_method="cash",
            reference_number="RCP-001"
        )

    def test_dashboard_summary_authenticated_success(self):
        login_res = self.client.post('/api/v1/auth/login/', {
            'username': 'owner_user',
            'password': 'ownerPassword123!'
        }, format='json')
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = self.client.get('/api/v1/dashboard/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        kpis = response.data['kpis']
        self.assertEqual(Decimal(str(kpis['today_disbursed_amount'])), Decimal('40000.00'))
        self.assertEqual(kpis['today_disbursed_count'], 1)
        self.assertEqual(Decimal(str(kpis['today_collection_amount'])), Decimal('2000.00'))
        self.assertEqual(Decimal(str(kpis['today_cash_collected'])), Decimal('2000.00'))
        self.assertEqual(kpis['active_loans_count'], 1)
        self.assertEqual(Decimal(str(kpis['active_loans_principal'])), Decimal('40000.00'))
        self.assertEqual(Decimal(str(kpis['total_pledged_gross_weight_grams'])), Decimal('16.500'))
        self.assertEqual(Decimal(str(kpis['total_pledged_net_weight_grams'])), Decimal('15.800'))
        self.assertEqual(kpis['total_active_pledge_items'], 1)

        # Verify recent items
        self.assertEqual(len(response.data['recent_loans']), 1)
        self.assertEqual(response.data['recent_loans'][0]['loan_number'], 'TEST-LN-001')
        self.assertEqual(len(response.data['recent_payments']), 1)
        self.assertEqual(response.data['recent_payments'][0]['loan_number'], 'TEST-LN-001')

    def test_dashboard_summary_branch_filter(self):
        login_res = self.client.post('/api/v1/auth/login/', {
            'username': 'owner_user',
            'password': 'ownerPassword123!'
        }, format='json')
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = self.client.get(f'/api/v1/dashboard/summary/?branch_id={self.branch.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['branch_filter'])
        self.assertEqual(response.data['branch_filter']['id'], self.branch.id)

    def test_dashboard_summary_unauthenticated_rejected(self):
        self.client.credentials()  # Clear token
        response = self.client.get('/api/v1/dashboard/summary/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
