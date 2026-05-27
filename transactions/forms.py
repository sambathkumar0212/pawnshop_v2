from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from .models import Loan, Payment, LoanExtension, Sale, LoanItem
from inventory.models import Item, Category
from inventory.forms import ItemForm
from accounts.models import Customer
from branches.models import Branch  # Add this import for Branch model
from schemes.models import Scheme  # Changed from content_manager.models to schemes.models
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Div, HTML
from decimal import Decimal, InvalidOperation
from django.utils import timezone
import re


def _extract_item_quantity_from_name(item_name):
    """Parse total quantity from item text like 'stud-2, chain-1'."""
    if not item_name:
        return 1
    text = str(item_name).strip().lower()
    tokens = [token.strip() for token in re.split(r'[,;\n|]+', text) if token.strip()]
    if not tokens:
        tokens = [text]

    total = 0
    any_explicit_quantity = False
    patterns = [r'-(\d+)\b', r'\bx\s*(\d+)\b', r'\bqty\s*[:\-]?\s*(\d+)\b']

    for token in tokens:
        token_qty = None
        for pattern in patterns:
            match = re.search(pattern, token)
            if match:
                try:
                    value = int(match.group(1))
                    if value > 0:
                        token_qty = value
                        any_explicit_quantity = True
                        break
                except (TypeError, ValueError):
                    pass

        if token_qty is not None:
            total += token_qty
        elif token.strip():
            total += 1

    if any_explicit_quantity:
        return total if total > 0 else 1
    return 1

class LoanForm(forms.ModelForm):
    distribution_amount = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=0,
        help_text="Amount to be distributed after processing fee",
        widget=forms.NumberInput(attrs={
            'data-show-words': 'true'  # Custom attribute to identify fields that need words display
        })
    )

    # Scheme field definition (will be properly configured in __init__)
    scheme = forms.ModelChoiceField(
        queryset=Scheme.objects.none(),  # Empty queryset as placeholder, will set in __init__
        empty_label="Select a Loan Scheme",
        required=True,
        help_text="Select a loan scheme to apply to this loan"
    )

    KARAT_CHOICES = [
        ('24', '24K (99.9%) - Pure Gold'),
        ('22', '22K (91.6%) - Indian Standard'),
        ('21', '21K (87.5%) - Middle Eastern'),
        ('20', '20K (83.3%) - Indian Standard'),
        ('18', '18K (75.0%) - European Standard'),
        ('14', '14K (58.3%) - US Common'),
    ]

    KARAT_PURITY = {
        '24': Decimal('0.999'),
        '22': Decimal('0.916'),
        '21': Decimal('0.875'),
        '20': Decimal('0.833'),
        '18': Decimal('0.750'),
        '14': Decimal('0.583'),
    }

    # Item fields for new items
    item_name = forms.CharField(
        label='Item Name',
        help_text='Enter the name or description of the gold item',
        max_length=255,
        required=True
    )
    item_name_tamil = forms.CharField(
        label='Item Name (Tamil)',
        help_text='Tamil item name will auto-fill while you type',
        max_length=255,
        required=False
    )
    item_description = forms.CharField(
        required=False,  # Making it optional
        label='Item Description',
        help_text='Optional: Detailed description of the item including any distinguishing marks or damaged parts',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    item_description_tamil = forms.CharField(
        required=False,
        label='Item Description (Tamil)',
        help_text='Tamil item description will auto-fill while you type',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    item_category = forms.ModelChoiceField(
        required=True,
        queryset=Category.objects.all(),  # Will filter in __init__
        label='Ornament Type',
        help_text="Select the type of gold ornament"
    )
    gold_karat = forms.ChoiceField(
        required=False,
        choices=KARAT_CHOICES,
        initial='22',
        help_text="Select the purity of gold"
    )
    market_price_22k = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        label="Today's 22K Gold Price (per gram)",
        help_text="Enter today's market price for 22K gold per gram",
        widget=forms.TextInput()  # Changed to TextInput
    )
    gross_weight = forms.DecimalField(
        required=False,
        max_digits=7,
        decimal_places=3,
        help_text="Total weight of the ornament in grams",
        widget=forms.NumberInput(attrs={'step': '0.001'})  # Added step to ensure 3 decimal places
    )
    net_weight = forms.DecimalField(
        required=False,
        max_digits=7,
        decimal_places=3,
        widget=forms.NumberInput(attrs={
            'style': 'width: 100%;',  # Changed from 50% to 100% to increase size
            'step': '0.001'  # Added step to ensure 3 decimal places
        }),
        help_text="Weight of pure gold content in grams"
    )
    stone_weight = forms.DecimalField(
        required=False,
        max_digits=7,
        decimal_places=3,
        help_text="Weight of stones if any in grams",
        widget=forms.NumberInput(attrs={'step': '0.001'})  # Added step to ensure 3 decimal places
    )
    interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        disabled=True,  # We'll set this programmatically based on scheme
        required=False,  # Add this line to make it not required for form submission
        help_text="Interest rate per year"
    )
    processing_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=0,
        initial=0,
        help_text="Processing fee amount in Rupees",
        widget=forms.NumberInput(attrs={
            'step': '1',  # Only allow whole numbers
            'min': '0',   # Prevent negative values
            'pattern': '[0-9]*'  # Only allow digits
        })
    )
    
    # Loan document field
    loan_document = forms.FileField(
        required=False,
        label='Loan Document',
        help_text='Upload loan agreement or related documents (PDF, DOC, DOCX, JPG, PNG). File will be automatically named using customer and item names.',
        widget=forms.FileInput(attrs={
            'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png',
            'class': 'form-control'
        })
    )

    class Meta:
        model = Loan
        fields = [
            'customer', 'branch', 'scheme', 'principal_amount', 'processing_fee',
            'distribution_amount', 'interest_rate', 'issue_date', 'due_date', 'loan_document'
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'issue_date': 'Loan Date',
        }
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filter schemes to match exactly what's shown in the Loan Schemes page
        scheme_queryset = Scheme.objects.filter(status='active')
        
        if self.user and not self.user.is_superuser:
            # For branch users: Show active schemes that are either global or specific to their branch
            branch_id = self.user.branch.id if hasattr(self.user, 'branch') and self.user.branch else None
            if branch_id:
                scheme_queryset = scheme_queryset.filter(
                    Q(branch__isnull=True) | Q(branch_id=branch_id)
                )
                print(f"Filtered to {scheme_queryset.count()} schemes for branch {branch_id}")

        # Order schemes by most recently modified first
        self.fields['scheme'].queryset = scheme_queryset.order_by('-updated_at')
        
        # Print debug info - how many schemes were found
        print(f"Found {scheme_queryset.count()} active schemes in schemes app")
        for scheme in scheme_queryset.order_by('-updated_at'):  # Keep same ordering in debug output
            print(f"  - {scheme.name} (Branch: {scheme.branch}, Last modified: {scheme.updated_at})")
        
        # Set "Standard Gold Loan" as the default selection if it exists
        standard_gold_loan = scheme_queryset.filter(name='Standard Gold Loan').first()
        if standard_gold_loan:
            self.fields['scheme'].initial = standard_gold_loan
        
        # If no schemes are available, create a default one to prevent form errors
        if not scheme_queryset.exists():
            print("No schemes found in schemes app, consider creating some.")

        # Update principal_amount field to use integer values
        self.fields['principal_amount'] = forms.DecimalField(
            max_digits=10,
            decimal_places=0,
            help_text=""  # Removing help text as we'll display amount in words instead
        )

        # Update processing_fee field to use integer values
        self.fields['processing_fee'] = forms.DecimalField(
            max_digits=10,
            decimal_places=0,
            initial=0,
            help_text="Processing fee amount in Rupees",
            widget=forms.TextInput()  # Changed to TextInput
        )

        # Configure customer field - filter by organization first
        if self.user and hasattr(self.user, 'organization') and self.user.organization:
            # Filter customers by organization
            customers_query = Customer.objects.filter(branch__organization=self.user.organization)
            
            # Then further filter by branch if user has branch assigned and is not a regional manager
            if not self.user.is_superuser and self.user.branch and not (hasattr(self.user, 'role') and 
                self.user.role and self.user.role.name.lower() == 'regional manager'):
                customers_query = customers_query.filter(branch=self.user.branch)
                
            self.fields['customer'].queryset = customers_query.order_by('first_name', 'last_name')
        else:
            # Show all customers for superusers or users without an organization
            self.fields['customer'].queryset = Customer.objects.all().order_by('first_name', 'last_name')
            
        self.fields['customer'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name}"
        
        # Add data attribute to customer field to support setting branch based on customer's branch
        self.fields['customer'].widget.attrs['data-branch-update'] = 'true'
        
        # Configure branch field - filter by organization
        if self.user and hasattr(self.user, 'organization') and self.user.organization:
            # Filter branches by organization
            self.fields['branch'].queryset = Branch.objects.filter(
                organization=self.user.organization
            ).order_by('name')
            
            # Set branch if user belongs to one
            if not self.user.is_superuser and self.user.branch:
                self.fields['branch'].initial = self.user.branch
                
                # If user is not a regional manager or other role that can create loans for other branches,
                # make the branch field hidden
                if not (hasattr(self.user, 'role') and self.user.role and 
                        self.user.role.name.lower() in ['regional manager', 'area manager']):
                    self.fields['branch'].widget = forms.HiddenInput()
        else:
            # Show all branches for superusers or users without an organization
            self.fields['branch'].queryset = Branch.objects.all().order_by('name')

        # Define top priority ornament types and Tamil Nadu relevant gold ornament categories
        top_categories = [
            'Mixed Items',
            'Chain', 
            'Chain with Dollar', 
            'Chain without Dollar', 
            'Ring'
        ]

        # Create Mixed Items category first to ensure it exists
        mixed_items_category, created = Category.objects.get_or_create(
            name='Mixed Items',
            defaults={'description': 'Multiple types of gold ornaments'}
        )
        category_ids = [mixed_items_category.id]

        # Create other top categories
        for category_name in top_categories[1:]:  # Skip Mixed Items as it's already created
            category, created = Category.objects.get_or_create(
                name=category_name,
                defaults={'description': f'Gold ornament: {category_name}'}
            )
            category_ids.append(category.id)

        # Then create or get the Tamil Nadu categories
        tamilnadu_categories = [
            'Thali (Mangalsutra)', 'Jimikki (Earrings)', 'Mothiram (Rings)', 
            'Valai (Bangles)', 'Malai (Necklaces)', 'Koppu (Studs)',
            'Odiyanam (Waist Belt)', 'Thodu (Ear Hoops)', 'Vanki (Armlet)',
            'Kolusu (Anklet)', 'Metti (Toe Ring)', 'Jadai Nagam (Hair Ornament)'
        ]

        for category_name in tamilnadu_categories:
            category, created = Category.objects.get_or_create(
                name=category_name,
                defaults={'description': f'Traditional Tamil Nadu gold ornament: {category_name}'}
            )
            category_ids.append(category.id)
        
        # Create the complete categories list in order
        all_categories = ['Mixed Items'] + top_categories[1:] + tamilnadu_categories
        
        # Order the categories to ensure Mixed Items appears first
        self.fields['item_category'].queryset = Category.objects.filter(id__in=category_ids).order_by(
            models.Case(
                *[models.When(name=name, then=pos) for pos, name in enumerate(all_categories)]
            )
        )
        
        # Always set Mixed Items as default
        self.fields['item_category'].initial = mixed_items_category
        self.fields['item_category'].label = 'Ornament Type'
        self.fields['item_category'].help_text = 'Select the type of gold ornament'

        # Filter available items
        available_items = Item.objects.exclude(
            loans__status='active'
        ).filter(status='available')

        # Add formset for multiple items
        from django.forms import formset_factory
        ItemFormSet = formset_factory(ItemForm, extra=1, can_delete=True)
        self.items_formset = ItemFormSet(prefix='items')

        # Set branch if user belongs to one
        if self.user and not self.user.is_superuser and self.user.branch:
            self.fields['branch'].initial = self.user.branch
            self.fields['branch'].widget = forms.HiddenInput()
            
        # If this is an existing loan, populate the item fields
        if self.instance and self.instance.pk:
            # Get the first loan item associated with this loan
            loan_item = self.instance.loanitem_set.first()
            if loan_item:
                # Populate all item-related fields from the existing data
                self.fields['item_name'].initial = loan_item.item.name
                self.fields['item_name_tamil'].initial = loan_item.item.tamil_name
                self.fields['item_description'].initial = loan_item.item.description
                self.fields['item_description_tamil'].initial = loan_item.item.tamil_description
                self.fields['item_category'].initial = loan_item.item.category
                
                # Convert Decimal to string for gold_karat field
                if loan_item.gold_karat:
                    # Convert to string and remove decimal part if it's .00
                    karat_str = str(loan_item.gold_karat)
                    if karat_str.endswith('.00'):
                        karat_str = karat_str.split('.')[0]
                    self.fields['gold_karat'].initial = karat_str
                
                self.fields['gross_weight'].initial = loan_item.gross_weight
                self.fields['net_weight'].initial = loan_item.net_weight
                self.fields['stone_weight'].initial = loan_item.stone_weight
                self.fields['market_price_22k'].initial = loan_item.market_price_22k

        # Set up crispy form layout
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('customer', css_class='col-md-8'),
                Column('branch', css_class='col-md-4'),
            ),
            Row(
                Column('item_name', css_class='col-md-6'),
                Column('item_category', css_class='col-md-6'),
            ),
            Row(
                Column('market_price_22k', css_class='col-md-6'),
                Column('gold_karat', css_class='col-md-6'),
            ),
            Row(
                Column('gross_weight', css_class='col-md-4'),
                Column('stone_weight', css_class='col-md-4'),
                Column('net_weight', css_class='col-md-4'),
            ),
            Row(
                Column('item_description', css_class='col-md-6'),
                Column('loan_document', css_class='col-md-6'),
            ),
            Row(
                Column('principal_amount', css_class='col-md-4'),
                Column('processing_fee', css_class='col-md-4'),
                Column('distribution_amount', css_class='col-md-4'),
            ),
            Row(
                Column('interest_rate', css_class='col-md-12'),
            ),
            Row(
                Column('issue_date', css_class='col-md-4'),
                Column('due_date', css_class='col-md-4'),
            ),
        )

    def get_initial(self):
        initial = super().get_initial()
        initial['issue_date'] = timezone.now().date()
        
        # Auto-calculate due date and grace period end based on issue date
        today = timezone.now().date()
        
        # Both Standard and Flexible schemes use the same due date calculation: 364 days from issue date
        initial['due_date'] = today + timezone.timedelta(days=364)
            
        # Grace period is 5 days after due date for both schemes
        initial['grace_period_end'] = initial['due_date'] + timezone.timedelta(days=5)
        
        return initial

    def clean_scheme(self):
        scheme = self.cleaned_data.get('scheme')
        if not scheme:
            raise ValidationError("Please select a loan scheme.")
        
        # Calculate loan duration in months
        issue_date = self.cleaned_data.get('issue_date')
        due_date = None
        
        if issue_date and scheme.loan_duration:
            due_date = issue_date + timezone.timedelta(days=scheme.loan_duration)
            self.cleaned_data['due_date'] = due_date
            
            # Set grace period end date (5 days after due date)
            self.cleaned_data['grace_period_end'] = due_date + timezone.timedelta(days=5)
        
        # Calculate loan tenure in months for interest rate determination
        if issue_date and due_date:
            months = ((due_date.year - issue_date.year) * 12 + due_date.month - issue_date.month)
            # Add an extra month if there are remaining days
            if due_date.day > issue_date.day:
                months += 1
                
            # Check if scheme has dynamic interest rates
            if scheme.interest_rate_structure:
                # Get the appropriate interest rate based on tenure
                interest_rate = scheme.get_interest_rate_for_tenure(months)
                self.cleaned_data['interest_rate'] = interest_rate
            else:
                # Use the default interest rate if no dynamic structure exists
                self.cleaned_data['interest_rate'] = scheme.interest_rate
        else:
            # Fallback to default interest rate if dates are not available
            self.cleaned_data['interest_rate'] = scheme.interest_rate
        
        # Set processing fee percentage from the scheme's additional_conditions
        if scheme.additional_conditions and 'processing_fee_percentage' in scheme.additional_conditions:
            processing_fee_percentage = scheme.additional_conditions['processing_fee_percentage']
            self.cleaned_data['processing_fee_percentage'] = processing_fee_percentage
        
        return scheme

    def clean(self):
        cleaned_data = super().clean()

        # Ensure interest_rate is set from scheme before other validations
        scheme = cleaned_data.get('scheme')
        if scheme:
            # Set interest rate from scheme if not already set
            if 'interest_rate' not in cleaned_data or not cleaned_data['interest_rate']:
                cleaned_data['interest_rate'] = scheme.interest_rate

        # Ensure principal_amount and processing_fee are integers
        try:
            if 'principal_amount' in cleaned_data:
                cleaned_data['principal_amount'] = int(float(cleaned_data['principal_amount']))
            if 'processing_fee' in cleaned_data:
                cleaned_data['processing_fee'] = int(float(cleaned_data['processing_fee']))
        except (ValueError, TypeError):
            raise ValidationError("Please enter valid whole numbers for principal amount and processing fee")

        # Calculate processing fee and distribution amount based on scheme's processing fee percentage
        principal_amount = cleaned_data.get('principal_amount')
        
        if principal_amount and scheme:
            # Get processing fee percentage from scheme's additional_conditions, default to 1% if not specified
            processing_fee_percentage = 1.0  # Default to 1%
            
            if scheme.additional_conditions and 'processing_fee_percentage' in scheme.additional_conditions:
                processing_fee_percentage = float(scheme.additional_conditions['processing_fee_percentage'])
            
            # Calculate processing fee using the scheme's percentage
            processing_fee = round(float(principal_amount) * (processing_fee_percentage / 100))
            cleaned_data['processing_fee'] = processing_fee
            cleaned_data['distribution_amount'] = principal_amount - processing_fee

        # Check if at least one item is being added
        # For new item creation, check required fields
        required_fields = [
            'item_name', 'item_category', 'gold_karat',
            'gross_weight', 'net_weight', 'market_price_22k'
        ]
        missing_fields = [field for field in required_fields if not cleaned_data.get(field)]
        if missing_fields:
            for field in missing_fields:
                self.add_error(field, 'This field is required when creating a new item.')

        # Calculate allowed principal amount range if creating new item
        if all(cleaned_data.get(f) for f in ['market_price_22k', 'gold_karat', 'net_weight']):
            market_price = Decimal(str(cleaned_data['market_price_22k']))
            selected_karat = cleaned_data['gold_karat']
            net_weight = Decimal(str(cleaned_data['net_weight']))
            
            # Calculate value based on purity ratio
            purity_ratio = self.KARAT_PURITY[selected_karat] / self.KARAT_PURITY['22']
            gold_value = market_price * net_weight * purity_ratio
            max_principal = gold_value * Decimal('0.90')  # 90% of the gold value
            min_principal = gold_value * Decimal('0.50')  # 50% of the gold value
            principal = cleaned_data.get('principal_amount', 0)

            if principal > max_principal:
                self.add_error('principal_amount', 
                    f'Principal amount cannot exceed 90% of the gold value. Maximum allowed: ₹{max_principal:.2f}')
            elif principal < min_principal:
                self.add_error('principal_amount',
                    f'Principal amount must be at least 50% of the gold value. Minimum required: ₹{min_principal:.2f}')

        # Calculate total payable amount (distribution amount + interest)
        interest_rate = cleaned_data.get('interest_rate')
        distribution_amount = cleaned_data.get('distribution_amount')
        if distribution_amount and interest_rate:
            # Interest rate is annual, convert to decimal and apply to distribution amount
            annual_interest_rate = interest_rate / Decimal('100')
            interest_amount = distribution_amount * annual_interest_rate
            cleaned_data['total_payable'] = distribution_amount + interest_amount

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        from datetime import timedelta
        # Calculate and set total_payable
        if instance.principal_amount and instance.interest_rate:
            # Convert interest_rate to Decimal if it's not already
            from decimal import Decimal
            interest_rate = Decimal(str(instance.interest_rate))
            annual_interest_rate = interest_rate / Decimal('100')
            interest_amount = instance.principal_amount * annual_interest_rate
            instance.total_payable = instance.principal_amount + interest_amount

        # Set distribution_amount
        if instance.principal_amount and instance.processing_fee:
            # The processing_fee is already stored as an amount at this point, not a percentage
            instance.distribution_amount = instance.principal_amount - instance.processing_fee

        # Set grace_period_end if due_date is set
        if instance.due_date:
            instance.grace_period_end = instance.due_date + timedelta(days=5)

        if commit:
            instance.save()
            
            # Check if this is an update or new loan
            if instance.pk and instance.loanitem_set.exists():
                # Update existing loan item information
                loan_item = instance.loanitem_set.first()
                if loan_item:
                    # Update item information
                    loan_item.item.name = self.cleaned_data['item_name']
                    loan_item.item.tamil_name = self.cleaned_data.get('item_name_tamil', '')
                    loan_item.item.description = self.cleaned_data['item_description']
                    loan_item.item.tamil_description = self.cleaned_data.get('item_description_tamil', '')
                    loan_item.item.tamil_brand = loan_item.item.tamil_brand or ''
                    loan_item.item.tamil_model = loan_item.item.tamil_model or ''
                    loan_item.item.tamil_tags = loan_item.item.tamil_tags or ''
                    loan_item.item.tamil_notes = loan_item.item.tamil_notes or ''
                    loan_item.item.category = self.cleaned_data['item_category']
                    loan_item.item.save()
                    
                    # Update loan item details
                    loan_item.gold_karat = self.cleaned_data['gold_karat']
                    loan_item.gross_weight = self.cleaned_data['gross_weight']
                    loan_item.net_weight = self.cleaned_data['net_weight']
                    loan_item.stone_weight = self.cleaned_data.get('stone_weight', 0)
                    loan_item.market_price_22k = self.cleaned_data['market_price_22k']
                    loan_item.quantity = _extract_item_quantity_from_name(self.cleaned_data.get('item_name', ''))
                    loan_item.save()
            else:
                # Create new item with gold details
                new_item = Item(
                    name=self.cleaned_data['item_name'],
                    description=self.cleaned_data.get('item_description', ''),
                    tamil_name=self.cleaned_data.get('item_name_tamil', ''),
                    tamil_description=self.cleaned_data.get('item_description_tamil', ''),
                    tamil_brand='',
                    tamil_model='',
                    tamil_tags='',
                    tamil_notes='',
                    category=self.cleaned_data['item_category'],
                    status='pawned',  # Set status to pawned when used in loan
                    branch=instance.branch if instance.branch else self.user.branch,
                    created_by=self.user
                )
                new_item.save()
                
                # Create LoanItem with gold details
                loan_item = LoanItem(
                    loan=instance,
                    item=new_item,
                    quantity=_extract_item_quantity_from_name(self.cleaned_data.get('item_name', '')),
                    gold_karat=self.cleaned_data['gold_karat'],
                    gross_weight=self.cleaned_data['gross_weight'],
                    net_weight=self.cleaned_data['net_weight'],
                    stone_weight=self.cleaned_data.get('stone_weight', 0),
                    market_price_22k=self.cleaned_data['market_price_22k']
                )
                loan_item.save()
            
            # Handle existing items from formset
            if hasattr(self, 'items_formset') and self.items_formset.is_valid():
                for item_form in self.items_formset:
                    if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                        item = item_form.save(commit=False)
                        item.status = 'pledged'
                        item.save()
                        LoanItem.objects.create(loan=instance, item=item)
        
        return instance

class LoanExtensionForm(forms.ModelForm):
    EXTENSION_PERIOD_CHOICES = [
        (30, '30 Days (1 Month)'),
        (60, '60 Days (2 Months)'),
        (90, '90 Days (3 Months)'),
    ]
    
    extension_period = forms.ChoiceField(
        choices=EXTENSION_PERIOD_CHOICES,
        initial=30,
        label="Extension Period",
        help_text="Choose the period to extend the loan by"
    )
    
    extension_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=0.00,
        label="Extension Fee",
        help_text="Fee charged for extending the loan"
    )
    
    new_grace_period_end = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="New Grace Period End Date",
        help_text="The new grace period end date after extension"
    )

    class Meta:
        model = LoanExtension
        fields = ['extension_date', 'new_due_date', 'fee', 'notes']
        widgets = {
            'extension_date': forms.DateInput(attrs={'type': 'date'}),
            'new_due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'extension_date': 'Extension Date',
            'new_due_date': 'New Due Date',
            'fee': 'Extension Fee',
            'notes': 'Notes'
        }

    def __init__(self, *args, **kwargs):
        self.loan = kwargs.pop('loan', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Setup form helper for crispy forms
        self.helper = FormHelper()
        self.helper.form_tag = False
        
        # Set default dates if loan is provided
        if self.loan:
            # Map fee to extension_fee for template
            self.fields['extension_fee'] = self.fields.pop('fee')
            
            # Set default values
            self.initial['extension_date'] = timezone.now().date()
            self.initial['new_due_date'] = self.loan.due_date + timezone.timedelta(days=30)
            self.initial['new_grace_period_end'] = self.loan.due_date + timezone.timedelta(days=35)  # 5 days grace period
            
            # Calculate default extension fee (0.5% of principal amount)
            self.initial['extension_fee'] = (self.loan.principal_amount * Decimal('0.005')).quantize(Decimal('0.01'))
            
    def clean(self):
        cleaned_data = super().clean()
        extension_period = int(cleaned_data.get('extension_period', 30))
        extension_date = cleaned_data.get('extension_date')
        
        if not self.loan:
            raise ValidationError("No loan specified for extension")
            
        # Check if loan is active
        if self.loan.status != 'active':
            raise ValidationError(f"Cannot extend a loan with status '{self.loan.status}'. Only active loans can be extended.")
        
        # Check if loan is not overdue by more than 30 days
        today = timezone.now().date()
        if self.loan.due_date < today:
            days_overdue = (today - self.loan.due_date).days
            if days_overdue > 30:
                raise ValidationError(f"Loan is overdue by {days_overdue} days. Extensions are not allowed for loans overdue by more than 30 days.")
        
        # Check if this would exceed the maximum of 3 extensions
        existing_extensions_count = self.loan.extensions.count()
        if existing_extensions_count >= 3:
            raise ValidationError(f"Maximum of 3 extensions allowed per loan. This loan already has {existing_extensions_count} extensions.")
        
        # Calculate new due date based on extension period
        if extension_date and self.loan:
            new_due_date = self.loan.due_date + timezone.timedelta(days=extension_period)
            cleaned_data['new_due_date'] = new_due_date
            
            # Calculate new grace period end (due date + 5 days)
            new_grace_period_end = new_due_date + timezone.timedelta(days=5)
            cleaned_data['new_grace_period_end'] = new_grace_period_end
            
        # Validate extension fee (must be at least 0.5% of principal)
        extension_fee = cleaned_data.get('extension_fee')
        min_fee = (self.loan.principal_amount * Decimal('0.005')).quantize(Decimal('0.01'))
        
        if extension_fee and extension_fee < min_fee:
            self.add_error('extension_fee', f"Extension fee must be at least 0.5% of the principal amount (₹{min_fee}).")
        
        # Map extension_fee back to fee for model
        if 'extension_fee' in cleaned_data:
            cleaned_data['fee'] = cleaned_data.pop('extension_fee')
            
        # Set previous due date
        cleaned_data['previous_due_date'] = self.loan.due_date
        
        return cleaned_data
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set loan and previous due date
        instance.loan = self.loan
        instance.previous_due_date = self.loan.due_date
        
        # Set approved_by to current user
        if self.user:
            instance.approved_by = self.user
            
        if commit:
            instance.save()
            
            # Update the loan with new due date and status
            self.loan.due_date = instance.new_due_date
            self.loan.grace_period_end = instance.new_due_date + timezone.timedelta(days=5)
            self.loan.status = 'extended'
            self.loan.save()
            
        return instance

class SaleForm(forms.ModelForm):
    # Add a text field for item name instead of using the model field
    item_name = forms.CharField(
        max_length=255,
        required=True,
        label='Item*',
        help_text='Enter the name or description of the item'
    )
    
    # GST fields
    is_interstate = forms.BooleanField(
        required=False, 
        initial=False,
        label='Interstate Sale',
        help_text='Check if this is an interstate sale (IGST applicable) instead of intrastate (CGST + SGST)'
    )
    
    place_of_supply = forms.CharField(
        max_length=50, 
        required=False,
        label='Place of Supply',
        help_text='State name or code for GST reporting purposes'
    )
    
    customer_gstin = forms.CharField(
        max_length=15, 
        required=False,
        label='Customer GSTIN',
        help_text='GSTIN of the customer if registered under GST'
    )
    
    hsn_code = forms.CharField(
        max_length=20, 
        required=False,
        label='HSN Code',
        help_text='HSN code for the item'
    )

    class Meta:
        model = Sale
        fields = [
            'customer', 'selling_price', 'gst_rate',
            'is_interstate', 'place_of_supply', 'customer_gstin', 
            'discount', 'payment_method', 'sale_date'
        ]
        widgets = {
            'sale_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default sale date to today
        if not self.instance.pk:
            self.fields['sale_date'].initial = timezone.now().date()
            
        # Configure GST rate field to show only active rates
        from gst.models import GSTRate
        self.fields['gst_rate'].queryset = GSTRate.objects.filter(is_active=True).order_by('name')
        self.fields['gst_rate'].label = 'GST Rate'
        self.fields['gst_rate'].help_text = 'Select the applicable GST rate'
        self.fields['gst_rate'].required = False  # Make it optional
        
        # Configure customer field - filter by organization
        if self.user and hasattr(self.user, 'organization') and self.user.organization:
            # Filter customers by organization
            customers_query = Customer.objects.filter(branch__organization=self.user.organization)
            
            # Then further filter by branch if user has branch assigned and is not a regional manager
            if not self.user.is_superuser and self.user.branch and not (hasattr(self.user, 'role') and 
                self.user.role and self.user.role.name.lower() == 'regional manager'):
                customers_query = customers_query.filter(branch=self.user.branch)
                
            self.fields['customer'].queryset = customers_query.order_by('first_name', 'last_name')
        else:
            # Show all customers for superusers or users without an organization
            self.fields['customer'].queryset = Customer.objects.all().order_by('first_name', 'last_name')
            
        self.fields['customer'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name}"
        
        # Initialize item_name from instance if it exists
        if self.instance and self.instance.pk and self.instance.item:
            self.fields['item_name'].initial = self.instance.item.name
            
            # Pre-fill HSN code if it exists
            if self.instance.hsn_code:
                self.fields['hsn_code'].initial = self.instance.hsn_code
                
            # Pre-fill place of supply if it exists
            if self.instance.place_of_supply:
                self.fields['place_of_supply'].initial = self.instance.place_of_supply
            elif self.instance.branch:
                self.fields['place_of_supply'].initial = self.instance.branch.state
                
        # If user has branch and branch has state, set as default place of supply
        elif self.user and hasattr(self.user, 'branch') and self.user.branch and hasattr(self.user.branch, 'state'):
            self.fields['place_of_supply'].initial = self.user.branch.state

        # Setup form helper for crispy forms
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('customer', css_class='col-md-6'),
                Column('item_name', css_class='col-md-6'),
            ),
            Row(
                Column('selling_price', css_class='col-md-4'),
                Column('discount', css_class='col-md-4'),
                Column('sale_date', css_class='col-md-4'),
            ),
            Div(
                HTML('<h5 class="mt-3 mb-2">GST Details</h5>'),
                css_class='col-12'
            ),
            Row(
                Column('gst_rate', css_class='col-md-6'),
                Column('hsn_code', css_class='col-md-6'),
            ),
            Row(
                Column('is_interstate', css_class='col-md-4'),
                Column('place_of_supply', css_class='col-md-4'),
                Column('customer_gstin', css_class='col-md-4'),
            ),
            Row(
                Column('payment_method', css_class='col-12'),
            ),
            Div(
                HTML('<div id="tax-breakdown" class="alert alert-info mt-3" style="display:none;">'
                     '<h6>Tax Breakdown</h6>'
                     '<div id="tax-details"></div>'
                     '</div>'),
                css_class='col-12'
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        selling_price = cleaned_data.get('selling_price', 0)
        discount = cleaned_data.get('discount', 0)
        gst_rate = cleaned_data.get('gst_rate')
        is_interstate = cleaned_data.get('is_interstate', False)

        # Validate selling price
        if selling_price <= 0:
            self.add_error('selling_price', 'Selling price must be greater than zero')
            
        # Validate discount
        if discount < 0:
            self.add_error('discount', 'Discount cannot be negative')
        
        if discount >= selling_price:
            self.add_error('discount', 'Discount cannot be greater than or equal to selling price')
            
        # Calculate taxes if GST rate is provided
        if gst_rate:
            taxable_value = selling_price - discount
            
            # Set rates from GST rate object
            self.instance.cgst_rate = gst_rate.cgst_rate
            self.instance.sgst_rate = gst_rate.sgst_rate
            self.instance.igst_rate = gst_rate.igst_rate
            
            # Auto-populate HSN code if not provided
            if not cleaned_data.get('hsn_code') and gst_rate.hsn_code:
                cleaned_data['hsn_code'] = gst_rate.hsn_code
                self.instance.hsn_code = gst_rate.hsn_code
            
            # Calculate tax amounts based on interstate status
            if is_interstate:
                self.instance.igst_amount = (taxable_value * gst_rate.igst_rate) / Decimal('100')
                self.instance.cgst_amount = Decimal('0')
                self.instance.sgst_amount = Decimal('0')
            else:
                self.instance.cgst_amount = (taxable_value * gst_rate.cgst_rate) / Decimal('100')
                self.instance.sgst_amount = (taxable_value * gst_rate.sgst_rate) / Decimal('100')
                self.instance.igst_amount = Decimal('0')
                
            # Calculate total tax
            self.instance.tax = self.instance.cgst_amount + self.instance.sgst_amount + self.instance.igst_amount
            
            # Calculate total amount
            self.instance.total_amount = taxable_value + self.instance.tax
        else:
            # No GST applied
            self.instance.tax = Decimal('0')
            self.instance.total_amount = selling_price - discount
            
        # Make sure the total amount is positive
        if self.instance.total_amount <= 0:
            self.add_error('selling_price', 'Total amount (selling price - discount + tax) must be greater than zero')

        return cleaned_data
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # First, ensure branch is set correctly - this is the critical part
        if not instance.branch and self.user and hasattr(self.user, 'branch') and self.user.branch:
            instance.branch = self.user.branch
        
        # Save the instance first to get its branch
        if commit and not instance.pk:
            instance.save()
            commit = False  # We'll save again after setting up the item
        
        # Create a new item based on the provided name
        item_name = self.cleaned_data.get('item_name')
        if item_name:
            # Create a new item with the provided name
            from inventory.models import Item
            
            # Create the item with the branch that's already set on the sale instance
            if instance.branch:
                item = Item.objects.create(
                    name=item_name,
                    description='',
                    tamil_name='',
                    tamil_description='',
                    tamil_brand='',
                    tamil_model='',
                    tamil_tags='',
                    tamil_notes='',
                    status='sold',  # Set status to sold
                    branch=instance.branch,
                    created_by=self.user if self.user else None
                )
                instance.item = item
            else:
                raise ValueError("Cannot create item: No branch available. Make sure your user has a branch assigned.")
        
        # Set other GST-related fields
        instance.is_interstate = self.cleaned_data.get('is_interstate', False)
        instance.place_of_supply = self.cleaned_data.get('place_of_supply', '')
        instance.customer_gstin = self.cleaned_data.get('customer_gstin', '')
        instance.hsn_code = self.cleaned_data.get('hsn_code', '')
            
        if commit:
            instance.save()
            
        return instance
