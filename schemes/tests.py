from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from django.urls import reverse
from .forms import NewSchemeForm
from .models import Scheme, DailyGoldRate

class NewSchemeFormTest(TestCase):
    def test_standard_scheme_without_tiered_rates(self):
        """Test form validation for a standard scheme without tiered interest rates"""
        today = timezone.now().date()
        far_future = today.replace(year=today.year + 1)
        
        form_data = {
            'name': 'Standard Gold Scheme',
            'description': 'A simple standard scheme',
            'status': 'active',
            'gold_interest_rate': Decimal('1.20'),
            'expiry_period': 6,
            'minimum_duration': 30,
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('100000.00'),
            'processing_fee_percentage': Decimal('1.50'),
            'start_date': today,
            'end_date': far_future,
            'enable_tiered_rates': False,
        }
        
        form = NewSchemeForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        
        cleaned_data = form.cleaned_data
        self.assertIsNone(cleaned_data['interest_rate_structure'])
        self.assertIsNone(cleaned_data['early_period_months'])
        self.assertIsNone(cleaned_data['early_period_interest_rate'])
        self.assertIsNone(cleaned_data['standard_period_months'])
        self.assertIsNone(cleaned_data['late_period_interest_rate'])
        
        self.assertEqual(cleaned_data['interest_rate'], Decimal('14.40')) # 1.20 * 12
        self.assertEqual(cleaned_data['loan_duration'], 180) # 6 * 30
        self.assertEqual(cleaned_data['additional_conditions']['processing_fee_percentage'], 1.50)

    def test_scheme_with_tiered_rates_valid(self):
        """Test form validation with valid tiered interest rate structure data"""
        today = timezone.now().date()
        far_future = today.replace(year=today.year + 1)
        
        form_data = {
            'name': 'Tiered Gold Scheme',
            'description': 'A tiered gold scheme',
            'status': 'active',
            'gold_interest_rate': Decimal('1.20'),
            'expiry_period': 6,
            'minimum_duration': 30,
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('100000.00'),
            'processing_fee_percentage': Decimal('1.50'),
            'start_date': today,
            'end_date': far_future,
            'enable_tiered_rates': True,
            'early_period_months': 2,
            'early_period_interest_rate': Decimal('0.80'),
            'standard_period_months': 3,
            'late_period_interest_rate': Decimal('1.50'),
        }
        
        form = NewSchemeForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        
        cleaned_data = form.cleaned_data
        expected_structure = {
            '0-2': 0.80,
            '2-5': 1.20,
            '5-6': 1.50,
        }
        self.assertEqual(cleaned_data['interest_rate_structure'], expected_structure)
        self.assertEqual(cleaned_data['additional_conditions']['early_period_months'], 2)
        self.assertEqual(cleaned_data['additional_conditions']['standard_period_months'], 3)
        self.assertEqual(cleaned_data['additional_conditions']['late_period_months'], 1)

    def test_scheme_with_tiered_rates_missing_fields(self):
        """Test form validation with tiered interest rates enabled but missing required fields"""
        today = timezone.now().date()
        far_future = today.replace(year=today.year + 1)
        
        form_data = {
            'name': 'Invalid Tiered Gold Scheme',
            'description': 'A tiered scheme with missing data',
            'status': 'active',
            'gold_interest_rate': Decimal('1.20'),
            'expiry_period': 6,
            'minimum_duration': 30,
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('100000.00'),
            'processing_fee_percentage': Decimal('1.50'),
            'start_date': today,
            'end_date': far_future,
            'enable_tiered_rates': True,
            # early_period_months and others are missing
        }
        
        form = NewSchemeForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('early_period_months', form.errors)
        self.assertIn('early_period_interest_rate', form.errors)
        self.assertIn('standard_period_months', form.errors)
        self.assertIn('late_period_interest_rate', form.errors)

    def test_scheme_with_tiered_rates_invalid_periods(self):
        """Test form validation when early + standard period duration exceeds expiry period"""
        today = timezone.now().date()
        far_future = today.replace(year=today.year + 1)
        
        form_data = {
            'name': 'Invalid Tiered Periods Scheme',
            'description': 'A scheme with invalid periods',
            'status': 'active',
            'gold_interest_rate': Decimal('1.20'),
            'expiry_period': 6,
            'minimum_duration': 30,
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('100000.00'),
            'processing_fee_percentage': Decimal('1.50'),
            'start_date': today,
            'end_date': far_future,
            'enable_tiered_rates': True,
            'early_period_months': 4,
            'early_period_interest_rate': Decimal('0.80'),
            'standard_period_months': 3,  # Total 7 months, exceeds expiry 6
            'late_period_interest_rate': Decimal('1.50'),
        }
        
        form = NewSchemeForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('expiry_period', form.errors)
        self.assertIn('Total loan duration must be greater than early period', form.errors['expiry_period'][0])

    def test_scheme_with_days_based_tiered_rates_valid(self):
        """Test form validation with valid days-based tiered interest rate structure data"""
        today = timezone.now().date()
        far_future = today.replace(year=today.year + 1)
        
        form_data = {
            'name': 'Days Tiered Gold Scheme',
            'description': 'A days-based tiered gold scheme',
            'status': 'active',
            'gold_interest_rate': Decimal('1.20'),
            'minimum_duration': 30,
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('100000.00'),
            'processing_fee_percentage': Decimal('1.50'),
            'start_date': today,
            'end_date': far_future,
            'enable_tiered_rates': True,
            'period1_days': 90,
            'period1_rate': Decimal('16.00'),
            'period2_days': 180,
            'period2_rate': Decimal('15.00'),
            'period3_days': 270,
            'period3_rate': Decimal('14.75'),
            'period4_days': 365,
            'period4_rate': Decimal('14.50'),
            'period5_rate': Decimal('23.34'),
        }
        
        form = NewSchemeForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        
        cleaned_data = form.cleaned_data
        expected_structure = {
            '0-90': 16.00,
            '90-180': 15.00,
            '180-270': 14.75,
            '270-365': 14.50,
            '365+': 23.34,
        }
        self.assertEqual(cleaned_data['interest_rate_structure'], expected_structure)
        self.assertEqual(cleaned_data['interest_rate'], Decimal('23.34'))
        self.assertEqual(cleaned_data['loan_duration'], 365)
        
        # Verify database saving
        scheme = form.save()
        self.assertIsNotNone(scheme.interest_rate_structure)
        self.assertEqual(scheme.interest_rate_structure, expected_structure)
        # gold_interest_rate is now set to Level 1 annual rate (period1_rate)
        self.assertEqual(scheme.gold_interest_rate, Decimal('16.00'))

    def test_scheme_update_preserves_gold_interest_rate_not_1_94(self):
        """Test that updating any detail in a scheme preserves the entered gold_interest_rate and does not overwrite with 1.94"""
        today = timezone.now().date()
        far_future = today.replace(year=today.year + 1)
        
        # Create an existing scheme with gold_interest_rate = 1.00
        scheme = Scheme.objects.create(
            name="Original Scheme",
            description="Original Description",
            status="active",
            is_gold_scheme=True,
            gold_interest_rate=Decimal("1.00"),
            interest_rate=Decimal("12.00"),
            loan_duration=180,
            expiry_period=6,
            minimum_amount=Decimal("1000.00"),
            maximum_amount=Decimal("1000000.00"),
            start_date=today,
        )
        
        # Simulate form submission when modifying description/name, where HTML form sends default period values
        form_data = {
            'name': 'Updated Scheme Name',
            'description': 'Updated Description Text',
            'status': 'active',
            'gold_interest_rate': Decimal('1.00'),
            'expiry_period': 6,
            'minimum_duration': 0,
            'minimum_amount': Decimal('1000.00'),
            'maximum_amount': Decimal('1000000.00'),
            'processing_fee_percentage': Decimal('1.00'),
            'start_date': today,
            'end_date': far_future,
            'enable_tiered_rates': False,
            # Days based fields sent with HTML defaults
            'period1_days': 90,
            'period1_rate': Decimal('16.00'),
            'period2_from_days': 90,
            'period2_days': 180,
            'period2_rate': Decimal('15.00'),
            'period3_from_days': 180,
            'period3_days': 270,
            'period3_rate': Decimal('14.75'),
            'period4_from_days': 270,
            'period4_days': 365,
            'period4_rate': Decimal('14.50'),
            'period5_from_days': 365,
            'period5_rate': Decimal('23.34'),
        }
        
        form = NewSchemeForm(data=form_data, instance=scheme)
        self.assertTrue(form.is_valid(), form.errors)
        saved_scheme = form.save()
        
        # Verify that gold_interest_rate was NOT changed to 1.94
        self.assertEqual(saved_scheme.gold_interest_rate, Decimal('1.00'))
        self.assertEqual(saved_scheme.interest_rate, Decimal('12.00'))
        self.assertIsNone(saved_scheme.interest_rate_structure)


class DailyGoldRateAndLtvEngineTests(TestCase):
    def setUp(self):
        from accounts.models import CustomUser, Organization, Customer
        from branches.models import Branch
        from inventory.models import Category

        self.user = CustomUser.objects.create_superuser(
            username="admin_ho",
            password="testpassword123",
            email="admin@pawnshop.com"
        )
        self.org = Organization.objects.create(
            name="Muthoot Manappuram Scale NBFC",
            slug="mms-nbfc",
            owner=self.user,
            status="active"
        )
        self.branch = Branch.objects.create(
            name="Central HO Branch",
            address="1 Banking Enclave",
            city="Chennai",
            state="TN",
            organization=self.org
        )
        self.customer = Customer.objects.create(
            first_name="Ramesh",
            last_name="Kumar",
            phone="9876543210",
            address="22 Gandhi Rd",
            branch=self.branch
        )
        self.category, _ = Category.objects.get_or_create(
            name="Mixed Items",
            defaults={"description": "Mixed Items"}
        )
        self.scheme = Scheme.objects.create(
            name="Standard Gold Scheme",
            description="Standard Scheme",
            interest_rate=Decimal("12.00"),
            loan_duration=364,
            minimum_amount=Decimal("1000.00"),
            maximum_amount=Decimal("1000000.00"),
            start_date=timezone.now().date(),
            status="active"
        )

        # Broadcast daily gold rate
        self.rate = DailyGoldRate.objects.create(
            organization=self.org,
            date=timezone.now().date(),
            rate_24k_per_gram=Decimal("7200.00"),
            rate_22k_per_gram=Decimal("6600.00"),
            rate_20k_per_gram=Decimal("6000.00"),
            rate_18k_per_gram=Decimal("5400.00"),
            maximum_ltv_percentage=Decimal("75.00"),
            is_active=True,
            updated_by=self.user
        )

    def test_daily_gold_rate_model_and_purity_derivation(self):
        """Test rate lookup and dynamic purity calculations"""
        self.assertEqual(self.rate.get_rate_for_karat('24'), Decimal('7200.00'))
        self.assertEqual(self.rate.get_rate_for_karat('22'), Decimal('6600.00'))
        self.assertEqual(self.rate.get_rate_for_karat('18'), Decimal('5400.00'))
        # 14K derivation: 7200 * (14/24) = 4200.00
        self.assertEqual(self.rate.get_rate_for_karat('14'), Decimal('4200.00'))

    def test_gold_valuation_and_rbi_ltv_math(self):
        """Test Market Value and Maximum Eligible Loan calculation under RBI 75% LTV Cap"""
        # 10.00 grams 22K @ ₹6,600 = ₹66,000 market value
        val_75 = DailyGoldRate.calculate_valuation(
            net_weight=Decimal('10.000'),
            karat='22',
            scheme_ltv=Decimal('75.00'),
            organization=self.org
        )
        self.assertEqual(val_75['market_value'], Decimal('66000.00'))
        self.assertEqual(val_75['effective_ltv'], Decimal('75.00'))
        self.assertEqual(val_75['max_eligible_loan'], Decimal('49500.00')) # 66000 * 0.75

    def test_loan_form_hard_blocks_principal_exceeding_rbi_ltv_cap(self):
        """Test that LoanForm rejects principal exceeding maximum eligible loan amount"""
        from transactions.forms import LoanForm

        form_data = {
            'customer': self.customer.id,
            'branch': self.branch.id,
            'scheme': self.scheme.id,
            'item_name': 'Gold Chain 916',
            'item_category': self.category.id,
            'gold_karat': '22',
            'market_price_22k': '6000.00', # ₹6,000/g
            'gross_weight': '10.000',
            'stone_weight': '0.000',
            'net_weight': '10.000', # Market Value = ₹60,000 | 75% Cap = ₹45,000 | 90% Hard Cap = ₹54,000
            'principal_amount': '55000', # EXCEEDS ₹54,000 (90%) and ₹45,000 (75%)
            'interest_rate': '12.00',
            'issue_date': timezone.now().date(),
            'due_date': timezone.now().date() + timezone.timedelta(days=364),
        }

        form = LoanForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('principal_amount', form.errors)
        self.assertTrue(any('exceeds the maximum eligible loan' in str(err) for err in form.errors['principal_amount']))

    def test_loan_form_allows_compliant_principal(self):
        """Test that compliant principal within LTV cap passes validation"""
        from transactions.forms import LoanForm

        form_data = {
            'customer': self.customer.id,
            'branch': self.branch.id,
            'scheme': self.scheme.id,
            'item_name': 'Gold Bangles 22K',
            'item_category': self.category.id,
            'gold_karat': '22',
            'market_price_22k': '6000.00',
            'gross_weight': '10.000',
            'stone_weight': '0.000',
            'net_weight': '10.000', # Market Value = ₹60,000 | 75% = ₹45,000
            'principal_amount': '45000', # Compliant
            'interest_rate': '12.00',
            'issue_date': timezone.now().date(),
            'due_date': timezone.now().date() + timezone.timedelta(days=364),
            'disbursement_mode': 'BANK_TRANSFER',
            'bank_account_number': '50100234567890',
            'bank_ifsc_code': 'HDFC0001234',
        }

        form = LoanForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_head_office_rate_broadcast_and_api_endpoint(self):
        """Test broadcasting new rates from HO panel and fetching via JSON API"""
        from django.test import Client
        client = Client()
        client.login(username="admin_ho", password="testpassword123")

        # Broadcast new rate
        response = client.post(reverse('daily_gold_rates'), {
            'rate_24k_per_gram': '7350.00',
            'rate_22k_per_gram': '6737.50',
            'rate_20k_per_gram': '6125.00',
            'rate_18k_per_gram': '5512.50',
            'maximum_ltv_percentage': '75.00',
            'notes': 'IBJA Mid-Day Bullion Update'
        })
        self.assertEqual(response.status_code, 302)

        # Verify JSON API endpoint returns updated rate
        api_res = client.get(reverse('api_today_gold_rate'))
        self.assertEqual(api_res.status_code, 200)
        data = api_res.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['rate_24k_per_gram'], 7350.0)
        self.assertEqual(data['rate_22k_per_gram'], 6737.5)
        self.assertEqual(data['maximum_ltv_percentage'], 75.0)


