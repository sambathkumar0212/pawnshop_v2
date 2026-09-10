from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from decimal import Decimal

from branches.models import Branch
from accounts.models import Customer
from inventory.models import Item, Category
from transactions.models import Loan, Payment, LoanItem, DisbursementTransaction

User = get_user_model()


class LoanAndPaymentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.branch = Branch.objects.create(
            name="Pawn Central Branch",
            phone="9876543210",
            address="50 Temple Street",
            city="Madurai",
            state="Tamil Nadu",
            zip_code="625001",
            is_active=True
        )
        self.user = User.objects.create_user(
            username="loan_officer",
            email="officer@pawnshop.com",
            password="officerPassword123!",
            first_name="Loan",
            last_name="Officer",
            branch=self.branch,
            is_superuser=True,
            is_active=True
        )
        self.customer = Customer.objects.create(
            first_name="Suresh",
            last_name="Raina",
            phone="9876500001",
            address="12 South Mada Street",
            branch=self.branch
        )
        self.category = Category.objects.create(name="Gold Ring", slug="gold-ring")
        self.item = Item.objects.create(
            item_id="ITEM-RING-001",
            name="22K Gold Ring",
            description="Gold Ring 22K Purity",
            category=self.category,
            branch=self.branch,
            status="pawned",
            appraised_value=Decimal('35000.00')
        )
        self.today = timezone.now().date()
        self.loan = Loan.objects.create(
            loan_number="TEST-MOB-LN-001",
            customer=self.customer,
            branch=self.branch,
            principal_amount=Decimal('25000.00'),
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
            gross_weight=Decimal('8.500'),
            net_weight=Decimal('8.200'),
            market_price_22k=Decimal('6200.00'),
            status="pledged"
        )

        # Authenticate client
        login_res = self.client.post('/api/v1/auth/login/', {
            'username': 'loan_officer',
            'password': 'officerPassword123!'
        }, format='json')
        self.token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

    def test_list_loans_and_search(self):
        response = self.client.get('/api/v1/loans/?search=Suresh')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['loan_number'], 'TEST-MOB-LN-001')
        self.assertEqual(response.data['results'][0]['customer_name'], 'Suresh Raina')

    def test_get_loan_detail(self):
        response = self.client.get('/api/v1/loans/TEST-MOB-LN-001/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['loan_number'], 'TEST-MOB-LN-001')
        self.assertEqual(len(response.data['loan_items']), 1)
        self.assertEqual(Decimal(str(response.data['loan_items'][0]['net_weight'])), Decimal('8.200'))

    def test_create_loan_via_api(self):
        payload = {
            'customer_first_name': 'Karthik',
            'customer_last_name': 'Subbaraj',
            'customer_phone': '9944332211',
            'customer_address': '77 Cinema Nagar, Madurai',
            'branch_id': self.branch.id,
            'principal_amount': '60000.00',
            'interest_rate': '15.00',
            'duration_months': 6,
            'disbursement_payment_mode': 'CASH',
            'items': [
                {
                    'name': '22K Gold Chain',
                    'gross_weight': '24.500',
                    'net_weight': '24.000',
                    'gold_karat': '22.00',
                    'quantity': 1,
                    'market_price_22k': '6200.00'
                }
            ],
            'item_photos': ['data:image/jpeg;base64,/9j/4AAQSkZJRg...']
        }
        response = self.client.post('/api/v1/loans/create/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('loan', response.data)
        created_loan = response.data['loan']
        self.assertEqual(Decimal(str(created_loan['principal_amount'])), Decimal('60000.00'))
        self.assertEqual(len(created_loan['loan_items']), 1)
        self.assertEqual(Decimal(str(created_loan['loan_items'][0]['gross_weight'])), Decimal('24.500'))

    def test_record_loan_repayment(self):
        payload = {
            'amount': '5000.00',
            'payment_method': 'cash',
            'reference_number': 'TEST-RCP-01',
            'notes': 'Mobile cash collection'
        }
        response = self.client.post('/api/v1/loans/TEST-MOB-LN-001/repay/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('payment', response.data)
        self.assertEqual(Decimal(str(response.data['payment']['amount'])), Decimal('5000.00'))

    def test_section_269st_cash_ceiling_violation_rejected(self):
        payload = {
            'amount': '200000.00',  # ₹2 Lakhs in cash violates Sec 269ST
            'payment_method': 'cash',
            'reference_number': 'EXCESS-CASH',
            'notes': 'Illegal cash repayment test'
        }
        response = self.client.post('/api/v1/loans/TEST-MOB-LN-001/repay/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Section 269ST Violation', response.data['error'])

    def test_list_payments(self):
        # Record payment first
        Payment.objects.create(
            loan=self.loan,
            amount=Decimal('1500.00'),
            payment_date=self.today,
            payment_method='upi',
            reference_number='UPI-12345678'
        )
        response = self.client.get('/api/v1/payments/?loan_number=TEST-MOB-LN-001')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
