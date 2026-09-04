from django import forms
from .models import Scheme
from django.utils import timezone
from decimal import Decimal

class SchemeForm(forms.ModelForm):
    """Form for creating and updating schemes"""
    
    # Fields for gold scheme
    is_gold_scheme = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Check if this is a gold loan scheme"
    )
    
    gold_interest_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'e.g., 1.00'
        }),
        help_text="Base interest rate for gold loans (Rupees per 100 Rupees per month)"
    )
    
    # Early repayment period and interest rate (made optional for days-based structure compatibility)
    early_period_months = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2'
        }),
        help_text="First period in months for early repayment benefits"
    )
    
    early_period_interest_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'e.g., 0.80'
        }),
        help_text="Reduced interest rate for early repayment (Rupees per 100 Rupees per month)"
    )
    
    # Standard period and interest rate
    standard_period_months = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 4'
        }),
        help_text="Second period in months for standard interest rate"
    )
    
    # Late period automatically calculated but with increased interest rate
    late_period_interest_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'e.g., 1.20'
        }),
        help_text="Increased interest rate for late period (Rupees per 100 Rupees per month)"
    )
    
    expiry_period = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter number of months'
        }),
        help_text="Total loan duration in months (must be greater than early + standard periods)"
    )

    # New Days-based Tiered Interest Rate Structure fields
    period1_days = forms.IntegerField(
        required=False,
        initial=90,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'placeholder': 'e.g., 90'
        }),
        label="Period 1 (days)",
        help_text="First period in days"
    )
    period1_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=16.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'step': '0.01',
            'placeholder': 'e.g., 16.00'
        }),
        label="Period 1 Interest Rate (% Yearly)",
        help_text="Yearly interest rate for Period 1"
    )
    period2_from_days = forms.IntegerField(
        required=False,
        initial=90,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days period2-from-days',
            'placeholder': 'e.g., 90'
        }),
        label="Period 2 From (days)",
        help_text="Start of Period 2 in days"
    )
    period2_days = forms.IntegerField(
        required=False,
        initial=180,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'placeholder': 'e.g., 180'
        }),
        label="Period 2 (days)",
        help_text="Second period in days"
    )
    period2_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=15.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'step': '0.01',
            'placeholder': 'e.g., 15.00'
        }),
        label="Period 2 Interest Rate (% Yearly)",
        help_text="Yearly interest rate for Period 2"
    )
    period3_from_days = forms.IntegerField(
        required=False,
        initial=180,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days period3-from-days',
            'placeholder': 'e.g., 180'
        }),
        label="Period 3 From (days)",
        help_text="Start of Period 3 in days"
    )
    period3_days = forms.IntegerField(
        required=False,
        initial=270,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'placeholder': 'e.g., 270'
        }),
        label="Period 3 (days)",
        help_text="Third period in days"
    )
    period3_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=14.75,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'step': '0.01',
            'placeholder': 'e.g., 14.75'
        }),
        label="Period 3 Interest Rate (% Yearly)",
        help_text="Yearly interest rate for Period 3"
    )
    period4_from_days = forms.IntegerField(
        required=False,
        initial=270,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days period4-from-days',
            'placeholder': 'e.g., 270'
        }),
        label="Period 4 From (days)",
        help_text="Start of Period 4 in days"
    )
    period4_days = forms.IntegerField(
        required=False,
        initial=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'placeholder': 'e.g., 365'
        }),
        label="Period 4 (days)",
        help_text="Fourth period in days"
    )
    period4_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=14.50,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'step': '0.01',
            'placeholder': 'e.g., 14.50'
        }),
        label="Period 4 Interest Rate (% Yearly)",
        help_text="Yearly interest rate for Period 4"
    )
    period5_from_days = forms.IntegerField(
        required=False,
        initial=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days period5-from-days',
            'placeholder': 'e.g., 365'
        }),
        label="Period 5 From (days)",
        help_text="Start of Period 5 in days"
    )
    period5_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=23.34,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'step': '0.01',
            'placeholder': 'e.g., 23.34'
        }),
        label="Period 5 Interest Rate (% Yearly)",
        help_text="Yearly interest rate for Period 5 (Late/Default rate)"
    )
    
    minimum_duration = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter number of days'
        }),
        help_text="Minimum duration for gold loans in days (0 means no minimum)"
    )
    
    # Changed to DecimalField for proper number input
    late_payment_interest = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'e.g., 0.30'
        }),
        help_text="Additional interest for late payment (Rupees per 100 Rupees per month)"
    )
    
    payment_due_day = forms.IntegerField(
        required=True,
        min_value=1,
        max_value=31,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter day of month (1-31)'
        }),
        help_text="Day of month when payment is due"
    )
    
    # Hidden fields - set automatically based on gold scheme data
    interest_rate = forms.DecimalField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    loan_duration = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    # Required amount fields
    minimum_amount = forms.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'value': '1000.00'
        }),
        help_text="Minimum loan amount"
    )
    
    maximum_amount = forms.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'value': '1000000.00'
        }),
        help_text="Maximum loan amount"
    )
    
    special_conditions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter special conditions for gold loans'
        }),
        help_text="Special conditions for gold loans"
    )
    
    is_fixed_interest = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Check if the interest rate is fixed (no additional charges)"
    )
    
    auction_on_expiry = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Check if the gold will be auctioned if not redeemed by expiry"
    )
    
    # Process fee field (will go into additional_conditions)
    processing_fee_percentage = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'e.g., 1.00'
        }),
        help_text="Processing fee percentage (if applicable)"
    )
    
    class Meta:
        model = Scheme
        fields = [
            'name', 'description', 'status', 'branch', 'start_date', 'end_date',
            'is_gold_scheme', 'gold_interest_rate', 'expiry_period', 'minimum_duration',
            'early_period_months', 'early_period_interest_rate',
            'standard_period_months', 'late_period_interest_rate',
            'late_payment_interest', 'payment_due_day', 'special_conditions',
            'is_fixed_interest', 'auction_on_expiry', 'processing_fee_percentage',
            'interest_rate', 'loan_duration', 'minimum_amount', 'maximum_amount',
            'interest_rate_structure', 'additional_conditions'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            })
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Always set is_gold_scheme to True 
        self.initial['is_gold_scheme'] = True
        self.fields['is_gold_scheme'].initial = True
        
        # Set default values for NEW schemes only
        if not self.instance.pk:
            today = timezone.now().date()
            far_future = today.replace(year=today.year + 30)
            
            self.fields['start_date'].initial = today
            self.fields['end_date'].initial = far_future
            self.fields['minimum_amount'].initial = 1000.00
            self.fields['maximum_amount'].initial = 1000000.00
            self.fields['processing_fee_percentage'].initial = 1.00
            self.fields['gold_interest_rate'].initial = 1.00
            self.fields['early_period_months'].initial = 2
            self.fields['early_period_interest_rate'].initial = 0.80
            self.fields['standard_period_months'].initial = 4
            self.fields['late_period_interest_rate'].initial = 1.20
            self.fields['expiry_period'].initial = 6
            self.fields['payment_due_day'].initial = 5
            
            # Days based fields initialization
            self.fields['period1_days'].initial = 90
            self.fields['period1_rate'].initial = 16.00
            self.fields['period2_days'].initial = 180
            self.fields['period2_rate'].initial = 15.00
            self.fields['period3_days'].initial = 270
            self.fields['period3_rate'].initial = 14.75
            self.fields['period4_days'].initial = 365
            self.fields['period4_rate'].initial = 14.50
            self.fields['period5_rate'].initial = 23.34
        else:
            # For EXISTING schemes, populate tiered interest rate fields from existing data
            if self.instance.processing_fee_percentage:
                self.fields['processing_fee_percentage'].initial = self.instance.processing_fee_percentage
            elif self.instance.additional_conditions and 'processing_fee_percentage' in self.instance.additional_conditions:
                self.fields['processing_fee_percentage'].initial = self.instance.additional_conditions['processing_fee_percentage']
            
            # Populate days-based fields if structure exists
            if self.instance.interest_rate_structure:
                structure = self.instance.interest_rate_structure
                sorted_ranges = []
                for k, v in structure.items():
                    if '-' in k:
                        try:
                            start, end = k.split('-')
                            sorted_ranges.append((int(start), int(end), float(v)))
                        except ValueError:
                            pass
                    elif k.endswith('+'):
                        try:
                            start = k.rstrip('+')
                            sorted_ranges.append((int(start), 999999, float(v)))
                        except ValueError:
                            pass
                sorted_ranges.sort()
                
                # Check if it's month-based or days-based (months will have small upper bounds like <= 12)
                is_actually_days = False
                for start, end, rate in sorted_ranges:
                    if end != 999999 and end > 12:
                        is_actually_days = True
                        break
                
                if not is_actually_days and sorted_ranges:
                    # Convert months to days for display
                    sorted_ranges = [(s*30, (e*30 if e != 999999 else 999999), r) for s, e, r in sorted_ranges]
                
                if len(sorted_ranges) >= 1:
                    self.fields['period1_days'].initial = sorted_ranges[0][1]
                    self.fields['period1_rate'].initial = sorted_ranges[0][2]
                if len(sorted_ranges) >= 2:
                    self.fields['period2_from_days'].initial = sorted_ranges[1][0]
                    self.fields['period2_days'].initial = sorted_ranges[1][1]
                    self.fields['period2_rate'].initial = sorted_ranges[1][2]
                if len(sorted_ranges) >= 3:
                    self.fields['period3_from_days'].initial = sorted_ranges[2][0]
                    self.fields['period3_days'].initial = sorted_ranges[2][1]
                    self.fields['period3_rate'].initial = sorted_ranges[2][2]
                if len(sorted_ranges) >= 4:
                    self.fields['period4_from_days'].initial = sorted_ranges[3][0]
                    self.fields['period4_days'].initial = sorted_ranges[3][1]
                    self.fields['period4_rate'].initial = sorted_ranges[3][2]
                
                for r in sorted_ranges:
                    if r[1] == 999999:
                        self.fields['period5_from_days'].initial = r[0]
                        self.fields['period5_rate'].initial = r[2]
                        break
            
            # If the scheme has tiered structure data in additional_conditions, populate the form
            if self.instance.additional_conditions:
                conditions = self.instance.additional_conditions
                
                if 'early_period_months' in conditions and not self.instance.early_period_months:
                    self.fields['early_period_months'].initial = conditions['early_period_months']
                
                if 'standard_period_months' in conditions and not self.instance.standard_period_months:
                    self.fields['standard_period_months'].initial = conditions['standard_period_months']
            
            # Parse interest_rate_structure to populate form fields if direct fields are empty
            if self.instance.interest_rate_structure and not (self.instance.early_period_interest_rate or self.instance.late_period_interest_rate):
                structure = self.instance.interest_rate_structure
                
                # Try to extract early period rate from structure
                for range_key, rate in structure.items():
                    if range_key.startswith('0-'):
                        self.fields['early_period_interest_rate'].initial = rate
                        break
                
                # Try to extract late period rate from structure
                for range_key, rate in structure.items():
                    if '-' in range_key:
                        parts = range_key.split('-')
                        if len(parts) == 2 and parts[1] == str(self.instance.expiry_period):
                            self.fields['late_period_interest_rate'].initial = rate
                            break
        
        # Make branch field optional
        self.fields['branch'].required = False
        
        # If there's a user and they have a branch, limit choices
        if user and not user.is_superuser:
            if user.branch:
                if user.role and user.role.name.lower() == 'branch manager':
                    self.fields['branch'].initial = user.branch
                    self.fields['branch'].widget.attrs['readonly'] = True
                    self.fields['branch'].disabled = True
                elif user.role and user.role.name.lower() == 'regional manager':
                    managed_branches = user.managed_branches.all()
                    if managed_branches.exists():
                        self.fields['branch'].queryset = managed_branches
        
        # Make end_date optional
        self.fields['end_date'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Always set is_gold_scheme to True
        cleaned_data['is_gold_scheme'] = True
        
        # Get period values with defaults for days-based structure
        period1_days = cleaned_data.get('period1_days')
        period1_rate = cleaned_data.get('period1_rate')
        
        period2_from_days = cleaned_data.get('period2_from_days')
        period2_days = cleaned_data.get('period2_days')
        period2_rate = cleaned_data.get('period2_rate')
        
        period3_from_days = cleaned_data.get('period3_from_days')
        period3_days = cleaned_data.get('period3_days')
        period3_rate = cleaned_data.get('period3_rate')
        
        period4_from_days = cleaned_data.get('period4_from_days')
        period4_days = cleaned_data.get('period4_days')
        period4_rate = cleaned_data.get('period4_rate')
        
        period5_from_days = cleaned_data.get('period5_from_days')
        period5_rate = cleaned_data.get('period5_rate')

        if period1_days is not None and period1_rate is not None:
            # Validate days-based tiered rates
            if period2_days and period2_days <= period1_days:
                self.add_error('period2_days', "Period 2 days must be greater than Period 1 days")
            if period3_days and period3_days <= period2_days:
                self.add_error('period3_days', "Period 3 days must be greater than Period 2 days")
            if period4_days and period4_days <= period3_days:
                self.add_error('period4_days', "Period 4 days must be greater than Period 3 days")

            # Build days-based interest_rate_structure
            interest_rate_structure = {}
            interest_rate_structure[f"0-{period1_days}"] = float(period1_rate)
            if period2_days and period2_rate is not None:
                p2_from = period2_from_days if period2_from_days is not None else period1_days
                interest_rate_structure[f"{p2_from}-{period2_days}"] = float(period2_rate)
            if period3_days and period3_rate is not None:
                p3_from = period3_from_days if period3_from_days is not None else period2_days
                interest_rate_structure[f"{p3_from}-{period3_days}"] = float(period3_rate)
            if period4_days and period4_rate is not None:
                p4_from = period4_from_days if period4_from_days is not None else period3_days
                interest_rate_structure[f"{p4_from}-{period4_days}"] = float(period4_rate)
            if period5_rate is not None:
                p5_from = period5_from_days if period5_from_days is not None else (period4_days or period3_days or period2_days or period1_days)
                interest_rate_structure[f"{p5_from}+"] = float(period5_rate)

            cleaned_data['interest_rate_structure'] = interest_rate_structure

            # Update base rate and duration fields
            if period5_rate is not None:
                cleaned_data['interest_rate'] = period5_rate
            
            # Preserve existing or user-entered gold_interest_rate if available, otherwise derive from period1_rate / 12
            if not cleaned_data.get('gold_interest_rate'):
                if self.instance and self.instance.gold_interest_rate:
                    cleaned_data['gold_interest_rate'] = self.instance.gold_interest_rate
                elif period1_rate is not None:
                    cleaned_data['gold_interest_rate'] = (period1_rate / Decimal('12')).quantize(Decimal('0.01'))
            if period4_days:
                cleaned_data['loan_duration'] = period4_days
                cleaned_data['expiry_period'] = int(period4_days / 30)

            # Build additional_conditions
            conditions = {}
            processing_fee = cleaned_data.get('processing_fee_percentage')
            if processing_fee:
                conditions['processing_fee_percentage'] = float(processing_fee)
            
            # Store period info in additional_conditions in days format
            conditions['period1_days'] = period1_days
            if period2_from_days is not None: conditions['period2_from_days'] = period2_from_days
            if period2_days: conditions['period2_days'] = period2_days
            if period3_from_days is not None: conditions['period3_from_days'] = period3_from_days
            if period3_days: conditions['period3_days'] = period3_days
            if period4_from_days is not None: conditions['period4_from_days'] = period4_from_days
            if period4_days: conditions['period4_days'] = period4_days
            if period5_from_days is not None: conditions['period5_from_days'] = period5_from_days
            cleaned_data['additional_conditions'] = conditions if conditions else None
            
        else:
            # Fallback to old months-based logic
            early_period_months = cleaned_data.get('early_period_months') or 0
            standard_period_months = cleaned_data.get('standard_period_months') or 0
            expiry_period = cleaned_data.get('expiry_period') or 0
            
            # Validate that expiry_period is greater than early_period + standard_period
            total_specified_periods = early_period_months + standard_period_months
            if expiry_period > 0 and expiry_period <= total_specified_periods:
                self.add_error('expiry_period', 
                    f"Total loan duration must be greater than early period ({early_period_months} months) + standard period ({standard_period_months} months) = {total_specified_periods} months")
            
            # Get interest rates
            gold_interest_rate = cleaned_data.get('gold_interest_rate')
            early_period_interest_rate = cleaned_data.get('early_period_interest_rate')
            late_period_interest_rate = cleaned_data.get('late_period_interest_rate')
            
            # Build interest rate structure JSON
            interest_rate_structure = {}
            
            # Only build structure if we have tiered rates
            if early_period_months and early_period_interest_rate:
                key = f"0-{early_period_months}"
                interest_rate_structure[key] = float(early_period_interest_rate)
            
            if standard_period_months and gold_interest_rate:
                key = f"{early_period_months}-{early_period_months + standard_period_months}"
                interest_rate_structure[key] = float(gold_interest_rate)
            
            if late_period_interest_rate and expiry_period:
                key = f"{early_period_months + standard_period_months}-{expiry_period}"
                interest_rate_structure[key] = float(late_period_interest_rate)
            
            # Only store the interest rate structure if it has entries
            if interest_rate_structure:
                cleaned_data['interest_rate_structure'] = interest_rate_structure
            else:
                # Ensure we don't set an empty dict
                cleaned_data['interest_rate_structure'] = None
            
            # Calculate interest_rate from gold_interest_rate (for backward compatibility)
            if gold_interest_rate:
                cleaned_data['interest_rate'] = gold_interest_rate * 12
            
            if expiry_period:
                # Convert expiry_period (months) to loan_duration (days)
                cleaned_data['loan_duration'] = expiry_period * 30
            
            # Build additional_conditions dictionary
            conditions = {}
            processing_fee = cleaned_data.get('processing_fee_percentage')
            if processing_fee:
                conditions['processing_fee_percentage'] = float(processing_fee)
            
            # Add period information to additional_conditions only if periods are defined
            if early_period_months or standard_period_months:
                conditions['early_period_months'] = early_period_months
                conditions['standard_period_months'] = standard_period_months
                if expiry_period:
                    conditions['late_period_months'] = expiry_period - (early_period_months + standard_period_months)
            
            cleaned_data['additional_conditions'] = conditions if conditions else None
            
        return cleaned_data
    

class NewSchemeForm(forms.ModelForm):
    """A simplified form for creating and updating loan schemes"""
    
    # Primary fields with clear labels and validation
    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    description = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    
    # Add checkbox to enable tiered interest rates
    enable_tiered_rates = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'enableTieredRates'
        }),
        label="Enable Tiered Interest Rate Structure",
        help_text="Check to set different interest rates for different periods"
    )
    
    gold_interest_rate = forms.DecimalField(
        required=True,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'e.g., 1.00'
        }),
        help_text="Monthly interest rate for gold loans per Rs: 100"
    )
    
    # Tiered interest rate fields (shown only when enable_tiered_rates is checked)
    early_period_months = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field',
            'placeholder': 'e.g., 2'
        }),
        label="Early Period (months)",
        help_text="First period in months for reduced interest rate"
    )
    
    early_period_interest_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field',
            'step': '0.01',
            'placeholder': 'e.g., 0.80'
        }),
        label="Early Period Rate",
        help_text="Reduced interest rate for early repayment (Rs per 100 per month)"
    )
    
    standard_period_months = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field',
            'placeholder': 'e.g., 4'
        }),
        label="Standard Period (months)",
        help_text="Second period in months for standard interest rate"
    )
    
    late_period_interest_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field',
            'step': '0.01',
            'placeholder': 'e.g., 1.20'
        }),
        label="Late Period Rate",
        help_text="Increased interest rate for late period (Rs per 100 per month)"
    )
    
    expiry_period = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 6'
        }),
        help_text="Loan term in months"
    )

    # New Days-based Tiered Interest Rate Structure fields for NewSchemeForm
    period1_days = forms.IntegerField(
        required=False,
        initial=90,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'placeholder': 'e.g., 90'
        }),
        label="Period 1 (days)",
        help_text="First period in days"
    )
    period1_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=16.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'step': '0.01',
            'placeholder': 'e.g., 16.00'
        }),
        label="Period 1 Interest Rate (% Yearly)",
        help_text="Yearly interest rate for Period 1"
    )
    period2_from_days = forms.IntegerField(
        required=False,
        initial=90,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days period2-from-days',
            'placeholder': 'e.g., 90'
        }),
        label="Period 2 From (days)",
        help_text="Start of Period 2 in days"
    )
    period2_days = forms.IntegerField(
        required=False,
        initial=180,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'placeholder': 'e.g., 180'
        }),
        label="Period 2 (days)",
        help_text="Second period in days"
    )
    period2_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=15.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'step': '0.01',
            'placeholder': 'e.g., 15.00'
        }),
        label="Period 2 Interest Rate (% Yearly)",
        help_text="Yearly interest rate for Period 2"
    )
    period3_from_days = forms.IntegerField(
        required=False,
        initial=180,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days period3-from-days',
            'placeholder': 'e.g., 180'
        }),
        label="Period 3 From (days)",
        help_text="Start of Period 3 in days"
    )
    period3_days = forms.IntegerField(
        required=False,
        initial=270,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'placeholder': 'e.g., 270'
        }),
        label="Period 3 (days)",
        help_text="Third period in days"
    )
    period3_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=14.75,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'step': '0.01',
            'placeholder': 'e.g., 14.75'
        }),
        label="Period 3 Interest Rate (% Yearly)",
        help_text="Yearly interest rate for Period 3"
    )
    period4_from_days = forms.IntegerField(
        required=False,
        initial=270,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days period4-from-days',
            'placeholder': 'e.g., 270'
        }),
        label="Period 4 From (days)",
        help_text="Start of Period 4 in days"
    )
    period4_days = forms.IntegerField(
        required=False,
        initial=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'placeholder': 'e.g., 365'
        }),
        label="Period 4 (days)",
        help_text="Fourth period in days"
    )
    period4_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=14.50,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'step': '0.01',
            'placeholder': 'e.g., 14.50'
        }),
        label="Period 4 Interest Rate (% Yearly)",
        help_text="Yearly interest rate for Period 4"
    )
    period5_from_days = forms.IntegerField(
        required=False,
        initial=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days period5-from-days',
            'placeholder': 'e.g., 365'
        }),
        label="Period 5 From (days)",
        help_text="Start of Period 5 in days"
    )
    period5_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=23.34,
        widget=forms.NumberInput(attrs={
            'class': 'form-control tiered-field-days',
            'step': '0.01',
            'placeholder': 'e.g., 23.34'
        }),
        label="Period 5 Interest Rate (% Yearly)",
        help_text="Yearly interest rate for Period 5 (Late/Default rate)"
    )
    
    # Add minimum_duration field
    minimum_duration = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 30'
        }),
        help_text="Minimum term in days (0 = no minimum)"
    )
    
    # Add hidden fields for interest_rate and loan_duration
    interest_rate = forms.DecimalField(
        required=False,  # We'll set this in clean()
        widget=forms.HiddenInput()
    )
    
    loan_duration = forms.IntegerField(
        required=False,  # We'll set this in clean()
        widget=forms.HiddenInput()
    )
    
    minimum_amount = forms.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        initial=1000.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    maximum_amount = forms.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        initial=1000000.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    processing_fee_percentage = forms.DecimalField(
        required=True,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        initial=1.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        help_text="Processing fee as percentage of loan amount"
    )
    
    # Optional field for special conditions
    special_conditions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Any special terms or conditions'
        })
    )
    
    # Dates
    start_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Leave blank for ongoing schemes"
    )
    
    class Meta:
        model = Scheme
        fields = [
            'name', 'description', 'enable_tiered_rates', 'gold_interest_rate', 
            'early_period_months', 'early_period_interest_rate', 
            'standard_period_months', 'late_period_interest_rate',
            'expiry_period', 'minimum_duration',
            'minimum_amount', 'maximum_amount', 'processing_fee_percentage',
            'special_conditions', 'start_date', 'end_date', 'status', 'branch',
            'interest_rate', 'loan_duration', 'interest_rate_structure', 'additional_conditions'
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'branch': forms.Select(attrs={'class': 'form-select'})
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default values for dates
        if not self.instance.pk:  # Only for new schemes
            today = timezone.now().date()
            far_future = today.replace(year=today.year + 30)
            
            self.fields['start_date'].initial = today
            self.fields['end_date'].initial = far_future
            
            # Days based fields initialization
            self.fields['period1_days'].initial = 90
            self.fields['period1_rate'].initial = 16.00
            self.fields['period2_from_days'].initial = 90
            self.fields['period2_days'].initial = 180
            self.fields['period2_rate'].initial = 15.00
            self.fields['period3_from_days'].initial = 180
            self.fields['period3_days'].initial = 270
            self.fields['period3_rate'].initial = 14.75
            self.fields['period4_from_days'].initial = 270
            self.fields['period4_days'].initial = 365
            self.fields['period4_rate'].initial = 14.50
            self.fields['period5_from_days'].initial = 365
            self.fields['period5_rate'].initial = 23.34
        else:
            # For existing schemes, check if tiered rates are enabled
            if self.instance.interest_rate_structure or \
               (self.instance.early_period_months and self.instance.early_period_months > 0) or \
               (self.instance.early_period_interest_rate and self.instance.early_period_interest_rate > 0):
                self.fields['enable_tiered_rates'].initial = True
            
            # Populate processing fee
            if self.instance.processing_fee_percentage:
                self.fields['processing_fee_percentage'].initial = self.instance.processing_fee_percentage
            elif self.instance.additional_conditions and 'processing_fee_percentage' in self.instance.additional_conditions:
                self.fields['processing_fee_percentage'].initial = self.instance.additional_conditions['processing_fee_percentage']
            
            # Populate days-based fields if structure exists
            if self.instance.interest_rate_structure:
                structure = self.instance.interest_rate_structure
                sorted_ranges = []
                for k, v in structure.items():
                    if '-' in k:
                        try:
                            start, end = k.split('-')
                            sorted_ranges.append((int(start), int(end), float(v)))
                        except ValueError:
                            pass
                    elif k.endswith('+'):
                        try:
                            start = k.rstrip('+')
                            sorted_ranges.append((int(start), 999999, float(v)))
                        except ValueError:
                            pass
                sorted_ranges.sort()
                
                # Check if actually days or months
                is_actually_days = False
                for start, end, rate in sorted_ranges:
                    if end != 999999 and end > 12:
                        is_actually_days = True
                        break
                
                if not is_actually_days and sorted_ranges:
                    sorted_ranges = [(s*30, (e*30 if e != 999999 else 999999), r) for s, e, r in sorted_ranges]
                
                if len(sorted_ranges) >= 1:
                    self.fields['period1_days'].initial = sorted_ranges[0][1]
                    self.fields['period1_rate'].initial = sorted_ranges[0][2]
                if len(sorted_ranges) >= 2:
                    self.fields['period2_from_days'].initial = sorted_ranges[1][0]
                    self.fields['period2_days'].initial = sorted_ranges[1][1]
                    self.fields['period2_rate'].initial = sorted_ranges[1][2]
                if len(sorted_ranges) >= 3:
                    self.fields['period3_from_days'].initial = sorted_ranges[2][0]
                    self.fields['period3_days'].initial = sorted_ranges[2][1]
                    self.fields['period3_rate'].initial = sorted_ranges[2][2]
                if len(sorted_ranges) >= 4:
                    self.fields['period4_from_days'].initial = sorted_ranges[3][0]
                    self.fields['period4_days'].initial = sorted_ranges[3][1]
                    self.fields['period4_rate'].initial = sorted_ranges[3][2]
                
                for r in sorted_ranges:
                    if r[1] == 999999:
                        self.fields['period5_from_days'].initial = r[0]
                        self.fields['period5_rate'].initial = r[2]
                        break
            
            # Populate other tiered fields from additional_conditions if they are not set on model directly
            if self.instance.additional_conditions:
                conditions = self.instance.additional_conditions
                if 'early_period_months' in conditions and not self.instance.early_period_months:
                    self.fields['early_period_months'].initial = conditions['early_period_months']
                if 'standard_period_months' in conditions and not self.instance.standard_period_months:
                    self.fields['standard_period_months'].initial = conditions['standard_period_months']
            
            # Parse interest_rate_structure to populate form fields if direct fields are empty
            if self.instance.interest_rate_structure and not (self.instance.early_period_interest_rate or self.instance.late_period_interest_rate):
                structure = self.instance.interest_rate_structure
                for range_key, rate in structure.items():
                    if range_key.startswith('0-'):
                        self.fields['early_period_interest_rate'].initial = rate
                        break
                for range_key, rate in structure.items():
                    if '-' in range_key:
                        parts = range_key.split('-')
                        if len(parts) == 2 and parts[1] == str(self.instance.expiry_period):
                            self.fields['late_period_interest_rate'].initial = rate
                            break
        
        # Make end_date optional
        self.fields['end_date'].required = False
        
        # Branch field logic
        self.fields['branch'].required = False
        
        # User-specific branch restrictions
        if user and not user.is_superuser:
            if user.branch:
                if user.role and user.role.name.lower() == 'branch manager':
                    self.fields['branch'].initial = user.branch
                    self.fields['branch'].widget.attrs['readonly'] = True
                    self.fields['branch'].disabled = True
                elif user.role and user.role.name.lower() == 'regional manager':
                    managed_branches = user.managed_branches.all()
                    if managed_branches.exists():
                        self.fields['branch'].queryset = managed_branches
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Always set is_gold_scheme to True
        cleaned_data['is_gold_scheme'] = True
        
        enable_tiered = cleaned_data.get('enable_tiered_rates', False)
        
        # Check if days-based fields are filled
        period1_days = cleaned_data.get('period1_days')
        period1_rate = cleaned_data.get('period1_rate')
        
        period2_from_days = cleaned_data.get('period2_from_days')
        period2_days = cleaned_data.get('period2_days')
        period2_rate = cleaned_data.get('period2_rate')
        
        period3_from_days = cleaned_data.get('period3_from_days')
        period3_days = cleaned_data.get('period3_days')
        period3_rate = cleaned_data.get('period3_rate')
        
        period4_from_days = cleaned_data.get('period4_from_days')
        period4_days = cleaned_data.get('period4_days')
        period4_rate = cleaned_data.get('period4_rate')
        
        period5_from_days = cleaned_data.get('period5_from_days')
        period5_rate = cleaned_data.get('period5_rate')
        
        if enable_tiered and period1_days is not None and period1_rate is not None:
            # Validate days-based tiered rates
            if period2_days and period2_days <= period1_days:
                self.add_error('period2_days', "Period 2 days must be greater than Period 1 days")
            if period3_days and period3_days <= period2_days:
                self.add_error('period3_days', "Period 3 days must be greater than Period 2 days")
            if period4_days and period4_days <= period3_days:
                self.add_error('period4_days', "Period 4 days must be greater than Period 3 days")

            # Build days-based interest_rate_structure
            interest_rate_structure = {}
            interest_rate_structure[f"0-{period1_days}"] = float(period1_rate)
            if period2_days and period2_rate is not None:
                p2_from = period2_from_days if period2_from_days is not None else period1_days
                interest_rate_structure[f"{p2_from}-{period2_days}"] = float(period2_rate)
            if period3_days and period3_rate is not None:
                p3_from = period3_from_days if period3_from_days is not None else period2_days
                interest_rate_structure[f"{p3_from}-{period3_days}"] = float(period3_rate)
            if period4_days and period4_rate is not None:
                p4_from = period4_from_days if period4_from_days is not None else period3_days
                interest_rate_structure[f"{p4_from}-{period4_days}"] = float(period4_rate)
            if period5_rate is not None:
                p5_from = period5_from_days if period5_from_days is not None else (period4_days or period3_days or period2_days or period1_days)
                interest_rate_structure[f"{p5_from}+"] = float(period5_rate)

            cleaned_data['interest_rate_structure'] = interest_rate_structure

            # Update base rate and duration fields
            if period5_rate is not None:
                cleaned_data['interest_rate'] = period5_rate

            # When tiered rates are enabled, gold_interest_rate = Level 1 annual rate (period1_rate)
            if period1_rate is not None:
                cleaned_data['gold_interest_rate'] = period1_rate
            if period4_days:
                cleaned_data['loan_duration'] = period4_days
                cleaned_data['expiry_period'] = int(period4_days / 30)

            # Store period information in additional_conditions in days format
            processing_fee = cleaned_data.get('processing_fee_percentage', 1.0)
            conditions = {
                'processing_fee_percentage': float(processing_fee) if processing_fee else 1.0,
                'period1_days': period1_days,
                'period2_from_days': period2_from_days,
                'period2_days': period2_days,
                'period3_from_days': period3_from_days,
                'period3_days': period3_days,
                'period4_from_days': period4_from_days,
                'period4_days': period4_days,
                'period5_from_days': period5_from_days,
            }
            cleaned_data['additional_conditions'] = conditions
        elif cleaned_data.get('early_period_months') or cleaned_data.get('early_period_interest_rate'):
            # Validate months-based tiered rate fields
            early_period_months = cleaned_data.get('early_period_months')
            early_period_interest_rate = cleaned_data.get('early_period_interest_rate')
            standard_period_months = cleaned_data.get('standard_period_months')
            late_period_interest_rate = cleaned_data.get('late_period_interest_rate')
            expiry_period = cleaned_data.get('expiry_period')
            gold_interest_rate = cleaned_data.get('gold_interest_rate')
            
            # Ensure all tiered fields are provided
            if not early_period_months:
                self.add_error('early_period_months', 'This field is required when tiered rates are enabled.')
            if not early_period_interest_rate:
                self.add_error('early_period_interest_rate', 'This field is required when tiered rates are enabled.')
            if not standard_period_months:
                self.add_error('standard_period_months', 'This field is required when tiered rates are enabled.')
            if not late_period_interest_rate:
                self.add_error('late_period_interest_rate', 'This field is required when tiered rates are enabled.')
            
            # Validate that expiry_period is greater than early + standard periods
            if early_period_months and standard_period_months and expiry_period:
                total_specified_periods = early_period_months + standard_period_months
                if expiry_period <= total_specified_periods:
                    self.add_error('expiry_period', 
                        f"Total loan duration must be greater than early period ({early_period_months} months) + "
                        f"standard period ({standard_period_months} months) = {total_specified_periods} months")
            
            # Build interest rate structure
            if early_period_months and early_period_interest_rate and standard_period_months and \
               gold_interest_rate and late_period_interest_rate and expiry_period:
                interest_rate_structure = {}
                
                # Early period: 0 to early_period_months
                interest_rate_structure[f"0-{early_period_months}"] = float(early_period_interest_rate)
                
                # Standard period: early_period_months to early + standard
                interest_rate_structure[f"{early_period_months}-{early_period_months + standard_period_months}"] = float(gold_interest_rate)
                
                # Late period: early + standard to expiry_period
                interest_rate_structure[f"{early_period_months + standard_period_months}-{expiry_period}"] = float(late_period_interest_rate)
                
                cleaned_data['interest_rate_structure'] = interest_rate_structure
            
            # Store period information in additional_conditions
            processing_fee = cleaned_data.get('processing_fee_percentage', 1.0)
            conditions = {
                'processing_fee_percentage': float(processing_fee) if processing_fee else 1.0,
                'early_period_months': early_period_months or 0,
                'standard_period_months': standard_period_months or 0,
                'late_period_months': (expiry_period - (early_period_months + standard_period_months)) if expiry_period and early_period_months and standard_period_months else 0
            }
            cleaned_data['additional_conditions'] = conditions
        elif enable_tiered:
            self.add_error('early_period_months', 'This field is required when tiered rates are enabled.')
            self.add_error('early_period_interest_rate', 'This field is required when tiered rates are enabled.')
            self.add_error('standard_period_months', 'This field is required when tiered rates are enabled.')
            self.add_error('late_period_interest_rate', 'This field is required when tiered rates are enabled.')
        else:
            # Standard scheme without tiered rates
            # Clear tiered rate fields
            cleaned_data['interest_rate_structure'] = None
            cleaned_data['early_period_months'] = None
            cleaned_data['early_period_interest_rate'] = None
            cleaned_data['standard_period_months'] = None
            cleaned_data['late_period_interest_rate'] = None
            
            # Store only processing fee in additional_conditions
            processing_fee = cleaned_data.get('processing_fee_percentage', 1.0)
            conditions = {
                'processing_fee_percentage': float(processing_fee) if processing_fee else 1.0
            }
            cleaned_data['additional_conditions'] = conditions
        
        # Calculate interest_rate from gold_interest_rate (monthly to annual)
        gold_interest_rate = cleaned_data.get('gold_interest_rate')
        if not enable_tiered:
            if gold_interest_rate:
                cleaned_data['interest_rate'] = gold_interest_rate * 12
            else:
                cleaned_data['interest_rate'] = Decimal('12.00')
            
            # Calculate loan_duration from expiry_period (months to days)
            expiry_period = cleaned_data.get('expiry_period')
            if expiry_period:
                cleaned_data['loan_duration'] = expiry_period * 30
            else:
                cleaned_data['loan_duration'] = 180
        
        return cleaned_data