from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from .forms import NewSchemeForm
from .models import Scheme

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

