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
        required=True,
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
    
    # Early repayment period and interest rate
    early_period_months = forms.IntegerField(
        required=True,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2'
        }),
        help_text="First period in months for early repayment benefits"
    )
    
    early_period_interest_rate = forms.DecimalField(
        required=True,
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
        required=True,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 4'
        }),
        help_text="Second period in months for standard interest rate"
    )
    
    # Late period automatically calculated but with increased interest rate
    late_period_interest_rate = forms.DecimalField(
        required=True,
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
        required=True,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter number of months'
        }),
        help_text="Total loan duration in months (must be greater than early + standard periods)"
    )
    
    minimum_duration = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter number of months'
        }),
        help_text="Minimum duration for gold loans in months (0 means no minimum)"
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
            'interest_rate', 'loan_duration', 'minimum_amount', 'maximum_amount'
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
            next_year = today.replace(year=today.year + 1)
            
            self.fields['start_date'].initial = today
            self.fields['end_date'].initial = next_year
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
        else:
            # For EXISTING schemes, populate tiered interest rate fields from existing data
            if self.instance.processing_fee_percentage:
                self.fields['processing_fee_percentage'].initial = self.instance.processing_fee_percentage
            elif self.instance.additional_conditions and 'processing_fee_percentage' in self.instance.additional_conditions:
                self.fields['processing_fee_percentage'].initial = self.instance.additional_conditions['processing_fee_percentage']
            
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
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Always set is_gold_scheme to True
        cleaned_data['is_gold_scheme'] = True
        
        # Get period values
        early_period_months = cleaned_data.get('early_period_months', 0)
        standard_period_months = cleaned_data.get('standard_period_months', 0)
        expiry_period = cleaned_data.get('expiry_period', 0)
        
        # Validate that expiry_period is greater than early_period + standard_period
        total_specified_periods = early_period_months + standard_period_months
        if expiry_period <= total_specified_periods:
            self.add_error('expiry_period', 
                f"Total loan duration must be greater than early period ({early_period_months} months) + standard period ({standard_period_months} months) = {total_specified_periods} months")
        
        # Get interest rates
        gold_interest_rate = cleaned_data.get('gold_interest_rate')
        early_period_interest_rate = cleaned_data.get('early_period_interest_rate')
        late_period_interest_rate = cleaned_data.get('late_period_interest_rate')
        
        # Build interest rate structure JSON
        interest_rate_structure = {}
        if early_period_months and early_period_interest_rate:
            key = f"0-{early_period_months}"
            interest_rate_structure[key] = float(early_period_interest_rate)
        
        if standard_period_months and gold_interest_rate:
            key = f"{early_period_months}-{early_period_months + standard_period_months}"
            interest_rate_structure[key] = float(gold_interest_rate)
        
        if late_period_interest_rate:
            key = f"{early_period_months + standard_period_months}-{expiry_period}"
            interest_rate_structure[key] = float(late_period_interest_rate)
        
        # Store the interest rate structure in the model
        cleaned_data['interest_rate_structure'] = interest_rate_structure
        
        # Calculate interest_rate from gold_interest_rate (for backward compatibility)
        if gold_interest_rate:
            # Convert gold_interest_rate (rupees per month) to interest_rate (percentage per year)
            # If gold interest rate is 1 rupee per 100 rupees per month, annual rate is 12%
            cleaned_data['interest_rate'] = gold_interest_rate * 12
        
        if expiry_period:
            # Convert expiry_period (months) to loan_duration (days)
            cleaned_data['loan_duration'] = expiry_period * 30
        
        # Build additional_conditions dictionary
        conditions = {}
        
        # Add processing fee percentage if provided
        processing_fee = cleaned_data.get('processing_fee_percentage')
        if processing_fee:
            conditions['processing_fee_percentage'] = float(processing_fee)
        
        # Add period information to additional_conditions
        conditions['early_period_months'] = early_period_months
        conditions['standard_period_months'] = standard_period_months
        conditions['late_period_months'] = expiry_period - (early_period_months + standard_period_months)
        
        # Add any other conditions as needed
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
        help_text="Monthly interest rate for gold loans per ₹100"
    )
    
    expiry_period = forms.IntegerField(
        required=True,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 6'
        }),
        help_text="Loan term in months"
    )
    
    # Add minimum_duration field
    minimum_duration = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 1'
        }),
        help_text="Minimum term in months (0 = no minimum)"
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
            'name', 'description', 'gold_interest_rate', 'expiry_period',
            'minimum_duration',  # Added minimum_duration field
            'minimum_amount', 'maximum_amount', 'processing_fee_percentage',
            'special_conditions', 'start_date', 'end_date', 'status', 'branch',
            'interest_rate', 'loan_duration'
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
            next_year = today.replace(year=today.year + 1)
            
            self.fields['start_date'].initial = today
            self.fields['end_date'].initial = next_year
        
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
        
        # Calculate interest_rate from gold_interest_rate (monthly to annual)
        gold_interest_rate = cleaned_data.get('gold_interest_rate')
        if gold_interest_rate:
            cleaned_data['interest_rate'] = gold_interest_rate * 12
        else:
            # Provide a default value if gold_interest_rate is not provided
            # This ensures interest_rate is never NULL
            cleaned_data['interest_rate'] = Decimal('12.00')
        
        # Calculate loan_duration from expiry_period (months to days)
        expiry_period = cleaned_data.get('expiry_period')
        if expiry_period:
            cleaned_data['loan_duration'] = expiry_period * 30
        else:
            # Provide a default value if expiry_period is not provided
            # This ensures loan_duration is never NULL
            cleaned_data['loan_duration'] = 180  # Default to 6 months (180 days)
        
        # Store processing_fee in additional_conditions
        processing_fee = cleaned_data.get('processing_fee_percentage')
        conditions = {}
        if processing_fee:
            conditions['processing_fee_percentage'] = float(processing_fee)
        else:
            # Set default processing fee if not provided
            conditions['processing_fee_percentage'] = 1.0
        
        cleaned_data['additional_conditions'] = conditions
        
        return cleaned_data