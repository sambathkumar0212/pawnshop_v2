from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from .models import Loan, Payment, LoanExtension, Sale, LoanItem, DisbursementTransaction
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


# ---------------------------------------------------------------------------
# Category bootstrap cache — avoids 17 get_or_create DB calls on every
# LoanForm init (GET and POST).  Categories almost never change, so we
# populate them once at process startup and cache the results in memory.
# ---------------------------------------------------------------------------
_CATEGORY_NAMES = [
    # Top-priority ornament types
    'Mixed Items',
    'Chain',
    'Chain with Dollar',
    'Chain without Dollar',
    'Ring',
    # Traditional Tamil Nadu ornaments
    'Thali (Mangalsutra)', 'Jimikki (Earrings)', 'Mothiram (Rings)',
    'Valai (Bangles)', 'Malai (Necklaces)', 'Koppu (Studs)',
    'Odiyanam (Waist Belt)', 'Thodu (Ear Hoops)', 'Vanki (Armlet)',
    'Kolusu (Anklet)', 'Metti (Toe Ring)', 'Jadai Nagam (Hair Ornament)',
]

# Maps category name -> description used when auto-creating missing rows
_CATEGORY_DESCRIPTIONS = {
    'Mixed Items': 'Multiple types of gold ornaments',
    'Chain': 'Gold ornament: Chain',
    'Chain with Dollar': 'Gold ornament: Chain with Dollar',
    'Chain without Dollar': 'Gold ornament: Chain without Dollar',
    'Ring': 'Gold ornament: Ring',
    'Thali (Mangalsutra)': 'Traditional Tamil Nadu gold ornament: Thali (Mangalsutra)',
    'Jimikki (Earrings)': 'Traditional Tamil Nadu gold ornament: Jimikki (Earrings)',
    'Mothiram (Rings)': 'Traditional Tamil Nadu gold ornament: Mothiram (Rings)',
    'Valai (Bangles)': 'Traditional Tamil Nadu gold ornament: Valai (Bangles)',
    'Malai (Necklaces)': 'Traditional Tamil Nadu gold ornament: Malai (Necklaces)',
    'Koppu (Studs)': 'Traditional Tamil Nadu gold ornament: Koppu (Studs)',
    'Odiyanam (Waist Belt)': 'Traditional Tamil Nadu gold ornament: Odiyanam (Waist Belt)',
    'Thodu (Ear Hoops)': 'Traditional Tamil Nadu gold ornament: Thodu (Ear Hoops)',
    'Vanki (Armlet)': 'Traditional Tamil Nadu gold ornament: Vanki (Armlet)',
    'Kolusu (Anklet)': 'Traditional Tamil Nadu gold ornament: Kolusu (Anklet)',
    'Metti (Toe Ring)': 'Traditional Tamil Nadu gold ornament: Metti (Toe Ring)',
    'Jadai Nagam (Hair Ornament)': 'Traditional Tamil Nadu gold ornament: Jadai Nagam (Hair Ornament)',
}

# Process-level cache: {name: Category instance}.  None means not yet populated.
_category_cache: dict | None = None


def _get_form_categories():
    """Return a dict of {name: Category} for all loan-form categories.

    The first call does at most 2 DB queries (SELECT + optional INSERT for any
    missing rows). Subsequent calls within the same server process return the
    cached dict with zero DB queries.
    """
    global _category_cache
    if _category_cache is not None and len(_category_cache) > 0:
        # Verify cached category objects exist in active DB (handles test runner DB resets)
        first_cat = next(iter(_category_cache.values()), None)
        if first_cat and Category.objects.filter(pk=first_cat.pk).exists():
            return _category_cache

    try:
        # Single SELECT to fetch all existing categories at once
        existing = {c.name: c for c in Category.objects.filter(name__in=_CATEGORY_NAMES)}

        missing_names = [n for n in _CATEGORY_NAMES if n not in existing]
        if missing_names:
            # Bulk-create any categories that don't exist yet (one INSERT)
            Category.objects.bulk_create(
                [
                    Category(name=n, description=_CATEGORY_DESCRIPTIONS.get(n, n))
                    for n in missing_names
                ],
                ignore_conflicts=True,  # safe if another worker beat us to it
            )
            # Re-fetch to get IDs for newly created rows
            for c in Category.objects.filter(name__in=missing_names):
                existing[c.name] = c

        _category_cache = existing
    except Exception:
        # If DB is not ready yet, fall back gracefully
        _category_cache = {}

    return _category_cache


def _extract_item_quantity_from_name(item_name):
    """Parse total quantity from item text like 'stud-2, chain-1' or 'ring (2), chain (1)'."""
    if not item_name:
        return 1
    text = str(item_name).strip().lower()
    tokens = [token.strip() for token in re.split(r'[,;\n|]+', text) if token.strip()]
    if not tokens:
        return 1

    total = 0
    patterns = [r'[-:]\s*(\d+)\b', r'\bx\s*(\d+)\b', r'\bqty\s*[:\-]?\s*(\d+)\b', r'\(\s*(\d+)\s*\)']

    for token in tokens:
        token_qty = None
        for pattern in patterns:
            match = re.search(pattern, token)
            if match:
                try:
                    value = int(match.group(1))
                    if value > 0:
                        token_qty = value
                        break
                except (TypeError, ValueError):
                    pass

        if token_qty is not None:
            total += token_qty
        elif token.strip():
            total += 1

    return total if total > 0 else 1

class LoanForm(forms.ModelForm):
    distribution_amount = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=0,
        label="Distribution Amount",
        widget=forms.TextInput(attrs={
            'data-show-words': 'true',
            'class': 'form-control no-spin',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'placeholder': 'e.g. 50000',
            'autocomplete': 'off'
        })
    )
    distribution_amount_with_deduction = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=0,
        label="Distribution Amount with Deduction",
        widget=forms.TextInput(attrs={
            'data-show-words': 'true',
            'readonly': 'readonly',
            'class': 'form-control bg-light no-spin',
            'inputmode': 'numeric'
        })
    )

    # Scheme field definition (will be properly configured in __init__)
    scheme = forms.ModelChoiceField(
        queryset=Scheme.objects.none(),  # Empty queryset as placeholder, will set in __init__
        empty_label="Select a Loan Scheme",
        required=True,
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
        required=False,
        label='Item Description',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    item_description_tamil = forms.CharField(
        required=False,
        label='Item Description (Tamil)',
        widget=forms.HiddenInput()
    )
    item_category = forms.ModelChoiceField(
        required=True,
        queryset=Category.objects.all(),  # Will filter in __init__
        label='Ornament Type'
    )
    gold_karat = forms.ChoiceField(
        required=False,
        choices=KARAT_CHOICES,
        initial='22',
        label='Purity'
    )
    market_price_22k = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        label="Today's 22K Gold Price (per gram)",
        widget=forms.HiddenInput()
    )
    gross_weight = forms.DecimalField(
        required=False,
        max_digits=7,
        decimal_places=3,
        label='Gross Wt (g)',
        widget=forms.NumberInput(attrs={'step': '0.001', 'placeholder': '0.000'})
    )
    stone_weight = forms.DecimalField(
        required=False,
        max_digits=7,
        decimal_places=3,
        label='Stone Wt (g)',
        widget=forms.NumberInput(attrs={'step': '0.001', 'placeholder': '0.000'})
    )
    items_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    net_weight = forms.DecimalField(
        required=False,
        max_digits=7,
        decimal_places=3,
        label='Net Gold Wt (g)',
        widget=forms.NumberInput(attrs={
            'style': 'width: 100%;',
            'step': '0.001',
            'placeholder': '0.000'
        })
    )
    interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        disabled=True,
        required=False
    )
    processing_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=0,
        initial=0,
        widget=forms.NumberInput(attrs={
            'step': '1',
            'min': '0',
            'pattern': '[0-9]*'
        })
    )
    
    # Loan document field
    loan_document = forms.FileField(
        required=False,
        label='Loan Document',
        widget=forms.FileInput(attrs={
            'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png',
            'class': 'form-control form-control-sm'
        })
    )
    is_first_month_interest_paid = forms.BooleanField(
        required=False,
        label='1st Month Interest Paid upfront',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    is_processing_fee_paid = forms.BooleanField(
        required=False,
        label='Processing Fee Paid upfront',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    pouch_number = forms.CharField(
        required=False,
        label='Vault Pouch No / Barcode',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. PCH-00123'})
    )
    safe_locker_number = forms.CharField(
        required=False,
        initial='Safe-01 / Locker-A1',
        label='Safe & Locker Number',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'})
    )
    shelf_rack_number = forms.CharField(
        required=False,
        initial='Rack-01 / Tray-A1',
        label='Shelf / Rack / Tray',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'})
    )
    seal_barcode = forms.CharField(
        required=False,
        label='Security Seal Barcode',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. SEAL-889922'})
    )
    gold_location = forms.CharField(
        required=False,
        label='Gold Location',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'})
    )
    repledge_date = forms.DateField(
        required=False,
        label='Repledge Date',
        help_text='Date of the repledge',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    repledge_amount = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        label='Repledge Amount',
        help_text='Amount if repledged',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    gold_status_others = forms.CharField(
        required=False,
        label='Gold Status Others (Notes)',
        help_text='Any other notes or details about the gold status',
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'})
    )

    # Section 269SS/269T Compliance: Disbursal Payout Mode & Customer Bank Information
    disbursement_mode = forms.ChoiceField(
        choices=DisbursementTransaction.DISBURSEMENT_MODE_CHOICES,
        initial='CASH',
        required=True,
        label="Disbursal Payout Mode",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_disbursement_mode'})
    )
    bank_account_number = forms.CharField(
        max_length=50,
        required=False,
        label="Beneficiary Account Number",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. 50100234567890'})
    )
    bank_ifsc_code = forms.CharField(
        max_length=20,
        required=False,
        label="Bank IFSC Code",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm text-uppercase', 'placeholder': 'e.g. HDFC0001234'})
    )
    bank_name = forms.CharField(
        max_length=100,
        required=False,
        label="Bank & Branch Name",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. HDFC Bank, Salem Main'})
    )
    bank_beneficiary_name = forms.CharField(
        max_length=150,
        required=False,
        label="Beneficiary / Account Holder Name",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'As per Bank Passbook'})
    )
    disbursement_utr = forms.CharField(
        max_length=100,
        required=False,
        label="Bank UTR / Transaction Reference",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'UTR / IMPS Ref (Optional)'})
    )

    class Meta:
        model = Loan
        fields = [
            'customer', 'branch', 'scheme', 'principal_amount', 'processing_fee',
            'distribution_amount', 'interest_rate', 'issue_date', 'due_date', 'loan_document',
            'is_first_month_interest_paid', 'is_processing_fee_paid',
            'gold_location', 'repledge_date', 'repledge_amount', 'gold_status_others'
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

        # Order schemes by most recently modified first
        self.fields['scheme'].queryset = scheme_queryset.order_by('-updated_at')

        # Set "Standard Gold Loan" as the default selection if it exists
        standard_gold_loan = scheme_queryset.filter(name='Standard Gold Loan').first()
        if standard_gold_loan:
            self.fields['scheme'].initial = standard_gold_loan

        # Update principal_amount field to use integer values
        self.fields['principal_amount'] = forms.DecimalField(
            max_digits=10,
            decimal_places=0,
            help_text="",
            widget=forms.TextInput(attrs={
                'data-show-words': 'true',
                'class': 'form-control no-spin',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
                'placeholder': 'e.g. 50000',
                'autocomplete': 'off'
            })
        )

        # Update processing_fee field to use integer values
        self.fields['processing_fee'] = forms.DecimalField(
            max_digits=10,
            decimal_places=0,
            initial=0,
            help_text="",
            widget=forms.TextInput(attrs={
                'class': 'form-control no-spin',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
                'autocomplete': 'off'
            })
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

        if 'processing_fee' in self.fields:
            self.fields['processing_fee'].required = False
        
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

        # Populate item_category choices using the process-level cache.
        # _get_form_categories() does at most 1 DB SELECT (first call) and
        # zero DB queries on every subsequent call — replacing 17 get_or_create
        # calls that previously ran on every single form init.
        cat_map = _get_form_categories()
        category_ids = [c.id for name, c in cat_map.items() if c.id]
        mixed_items_category = cat_map.get('Mixed Items')

        # Order the categories to ensure Mixed Items appears first
        self.fields['item_category'].queryset = Category.objects.filter(
            id__in=category_ids
        ).order_by(
            models.Case(
                *[models.When(name=name, then=pos) for pos, name in enumerate(_CATEGORY_NAMES)]
            )
        )

        # Always set Mixed Items as default
        if mixed_items_category:
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
            loan_items = list(self.instance.loanitem_set.select_related('item').all())
            if not loan_items:
                loan_items = list(getattr(self.instance, 'loan_items', self.instance.loanitem_set).select_related('item').all())

            if loan_items:
                import json
                items_data = []
                en_names = []
                ta_names = []
                total_gross = Decimal('0.000')
                total_stone = Decimal('0.000')
                total_net = Decimal('0.000')
                first_item = loan_items[0].item

                for li in loan_items:
                    item = li.item
                    it_name = item.name if item else 'Gold Ornament'
                    it_ta = (getattr(item, 'tamil_name', '') or getattr(item, 'name_tamil', '') or '').strip()
                    it_qty = getattr(li, 'quantity', 1) or 1
                    it_karat_raw = li.gold_karat if li.gold_karat is not None else 22
                    try:
                        it_karat = int(it_karat_raw) if float(it_karat_raw).is_integer() else float(it_karat_raw)
                    except Exception:
                        it_karat = 22
                    it_gross = float(li.gross_weight or 0.0)
                    it_stone = float(li.stone_weight or 0.0)
                    it_net = float(li.net_weight or max(0, it_gross - it_stone))

                    total_gross += Decimal(str(it_gross))
                    total_stone += Decimal(str(it_stone))
                    total_net += Decimal(str(it_net))

                    en_formatted = f"{it_name}-{it_qty}" if it_qty > 1 else it_name
                    ta_formatted = f"{it_ta}-{it_qty}" if (it_ta and it_qty > 1) else (it_ta or en_formatted)
                    en_names.append(en_formatted)
                    if it_ta:
                        ta_names.append(ta_formatted)

                    items_data.append({
                        'name': it_name,
                        'name_tamil': it_ta,
                        'quantity': it_qty,
                        'karat': it_karat,
                        'gross_weight': it_gross,
                        'stone_weight': it_stone,
                        'net_weight': it_net
                    })

                items_json_str = json.dumps(items_data)
                self.initial['items_json'] = items_json_str
                if 'items_json' in self.fields:
                    self.fields['items_json'].initial = items_json_str

                aggregated_en = ', '.join(en_names)
                aggregated_ta = ', '.join(ta_names) if ta_names else ''
                self.initial['item_name'] = aggregated_en
                self.fields['item_name'].initial = aggregated_en
                self.initial['item_name_tamil'] = aggregated_ta
                self.fields['item_name_tamil'].initial = aggregated_ta

                if first_item:
                    self.initial['item_description'] = first_item.description or ''
                    self.fields['item_description'].initial = first_item.description or ''
                    first_item_ta_desc = getattr(first_item, 'tamil_description', '') or ''
                    self.initial['item_description_tamil'] = first_item_ta_desc
                    self.fields['item_description_tamil'].initial = first_item_ta_desc
                    if first_item.category:
                        self.initial['item_category'] = first_item.category
                        self.fields['item_category'].initial = first_item.category

                # Karat of first item or dominant
                last_karat = str(loan_items[0].gold_karat) if loan_items[0].gold_karat else '22'
                if last_karat.endswith('.00') or last_karat.endswith('.0'):
                    last_karat = last_karat.split('.')[0]
                self.initial['gold_karat'] = last_karat
                self.fields['gold_karat'].initial = last_karat

                self.initial['gross_weight'] = total_gross
                self.fields['gross_weight'].initial = total_gross
                self.initial['stone_weight'] = total_stone
                self.fields['stone_weight'].initial = total_stone
                self.initial['net_weight'] = total_net
                self.fields['net_weight'].initial = total_net
                if loan_items[0].market_price_22k is not None:
                    self.initial['market_price_22k'] = loan_items[0].market_price_22k
                    self.fields['market_price_22k'].initial = loan_items[0].market_price_22k
            elif hasattr(self.instance, 'items') and self.instance.items.exists():
                import json
                items_data = []
                en_names = []
                ta_names = []
                total_gross = Decimal('0.000')
                total_stone = Decimal('0.000')
                total_net = Decimal('0.000')
                legacy_items = list(self.instance.items.all())
                first_item = legacy_items[0] if legacy_items else None

                for it in legacy_items:
                    it_name = it.name or 'Gold Ornament'
                    it_ta = (getattr(it, 'tamil_name', '') or getattr(it, 'name_tamil', '') or '').strip()
                    it_gross = float(getattr(it, 'gross_weight', 0.0) or getattr(it, 'weight', 0.0) or 0.0)
                    it_stone = float(getattr(it, 'stone_weight', 0.0) or 0.0)
                    it_net = float(getattr(it, 'net_weight', 0.0) or max(0, it_gross - it_stone))

                    total_gross += Decimal(str(it_gross))
                    total_stone += Decimal(str(it_stone))
                    total_net += Decimal(str(it_net))

                    en_names.append(it_name)
                    if it_ta:
                        ta_names.append(it_ta)

                    items_data.append({
                        'name': it_name,
                        'name_tamil': it_ta,
                        'quantity': 1,
                        'karat': 22,
                        'gross_weight': it_gross,
                        'stone_weight': it_stone,
                        'net_weight': it_net
                    })

                items_json_str = json.dumps(items_data)
                self.initial['items_json'] = items_json_str
                if 'items_json' in self.fields:
                    self.fields['items_json'].initial = items_json_str

                aggregated_en = ', '.join(en_names)
                aggregated_ta = ', '.join(ta_names) if ta_names else ''
                self.initial['item_name'] = aggregated_en
                self.fields['item_name'].initial = aggregated_en
                self.initial['item_name_tamil'] = aggregated_ta
                self.fields['item_name_tamil'].initial = aggregated_ta

                if first_item:
                    self.initial['item_description'] = first_item.description or ''
                    self.fields['item_description'].initial = first_item.description or ''
                    first_item_ta_desc = getattr(first_item, 'tamil_description', '') or ''
                    self.initial['item_description_tamil'] = first_item_ta_desc
                    self.fields['item_description_tamil'].initial = first_item_ta_desc
                    if first_item.category:
                        self.initial['item_category'] = first_item.category
                        self.fields['item_category'].initial = first_item.category

                self.initial['gold_karat'] = '22'
                self.fields['gold_karat'].initial = '22'
                self.initial['gross_weight'] = total_gross
                self.fields['gross_weight'].initial = total_gross
                self.initial['stone_weight'] = total_stone
                self.fields['stone_weight'].initial = total_stone
                self.initial['net_weight'] = total_net
                self.fields['net_weight'].initial = total_net


            if 'processing_fee' in self.fields and self.instance.processing_fee is not None:
                self.initial['processing_fee'] = self.instance.processing_fee
                self.fields['processing_fee'].initial = self.instance.processing_fee

            if 'distribution_amount' in self.fields:
                dist_val = self.instance.distribution_amount
                if dist_val is None and self.instance.principal_amount is not None:
                    dist_val = self.instance.principal_amount - (self.instance.processing_fee or 0)
                self.initial['distribution_amount'] = dist_val
                self.fields['distribution_amount'].initial = dist_val

            if 'distribution_amount_with_deduction' in self.fields:
                deduct_val = self.instance.distribution_amount_with_deduction
                if deduct_val is not None:
                    try:
                        deduct_val = int(round(float(deduct_val)))
                    except (ValueError, TypeError):
                        pass
                self.initial['distribution_amount_with_deduction'] = deduct_val
                self.fields['distribution_amount_with_deduction'].initial = deduct_val

            # Populate vault pouch fields if exists
            try:
                if hasattr(self.instance, 'vault_pouch') and self.instance.vault_pouch:
                    vp = self.instance.vault_pouch
                    self.fields['pouch_number'].initial = vp.pouch_number
                    self.fields['safe_locker_number'].initial = vp.safe_locker_number
                    self.fields['shelf_rack_number'].initial = vp.shelf_rack_number
                    self.fields['seal_barcode'].initial = vp.seal_barcode
            except Exception:
                pass

            # Populate disbursement details if exists
            try:
                if hasattr(self.instance, 'disbursement_detail') and self.instance.disbursement_detail:
                    dd = self.instance.disbursement_detail
                    self.fields['disbursement_mode'].initial = dd.payment_mode
                    self.fields['bank_account_number'].initial = dd.account_number
                    self.fields['bank_ifsc_code'].initial = dd.ifsc_code
                    self.fields['bank_name'].initial = dd.bank_name
                    self.fields['bank_beneficiary_name'].initial = dd.beneficiary_name
                    self.fields['disbursement_utr'].initial = dd.utr_number
            except Exception:
                pass
        else:
            # New loan creation: initialize market_price_22k from Central Daily Gold Rate
            try:
                from schemes.models import DailyGoldRate
                org = getattr(self.user, 'organization', None) if self.user else None
                rate_obj = DailyGoldRate.get_current_rate(organization=org)
                if rate_obj and 'market_price_22k' in self.fields:
                    self.fields['market_price_22k'].initial = rate_obj.rate_22k_per_gram
            except Exception:
                pass

        # If customer already selected, pre-populate customer's saved bank account details
        initial_customer = self.initial.get('customer') or getattr(self.instance, 'customer', None)
        if initial_customer:
            try:
                cust_obj = initial_customer if isinstance(initial_customer, Customer) else Customer.objects.filter(pk=initial_customer).first()
                if cust_obj:
                    if 'bank_account_number' in self.fields and not self.fields['bank_account_number'].initial:
                        self.fields['bank_account_number'].initial = cust_obj.bank_account_number
                    if 'bank_ifsc_code' in self.fields and not self.fields['bank_ifsc_code'].initial:
                        self.fields['bank_ifsc_code'].initial = cust_obj.bank_ifsc_code
                    if 'bank_name' in self.fields and not self.fields['bank_name'].initial:
                        self.fields['bank_name'].initial = cust_obj.bank_name
                    if 'bank_beneficiary_name' in self.fields and not self.fields['bank_beneficiary_name'].initial:
                        self.fields['bank_beneficiary_name'].initial = cust_obj.bank_beneficiary_name or cust_obj.full_name
            except Exception:
                pass

        # Set Today's 22K Gold Price as HiddenInput (displayed as top-header badge label)
        if 'market_price_22k' in self.fields:
            self.fields['market_price_22k'].widget = forms.HiddenInput()

        for field_name in ['customer', 'scheme', 'branch']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['class'] = 'form-select form-select-sm'
        if 'issue_date' in self.fields:
            self.fields['issue_date'].widget.attrs['class'] = 'form-control form-control-sm'

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
                Column('interest_rate', css_class='col-md-4'),
                Column('is_first_month_interest_paid', css_class='col-md-4', style="padding-top: 30px;"),
                Column('is_processing_fee_paid', css_class='col-md-4', style="padding-top: 30px;"),
            ),
            Row(
                Column('issue_date', css_class='col-md-4'),
                Column('due_date', css_class='col-md-4'),
            ),
            HTML('<h5 class="mt-4 mb-3 border-bottom pb-2 text-secondary"><i class="fas fa-shield-alt me-2"></i>Vault Custody & Security Pouch Tracking</h5>'),
            Row(
                Column('pouch_number', css_class='col-md-6'),
                Column('seal_barcode', css_class='col-md-6'),
            ),
            Row(
                Column('safe_locker_number', css_class='col-md-6'),
                Column('shelf_rack_number', css_class='col-md-6'),
            ),
            HTML('<h5 class="mt-4 mb-3 border-bottom pb-2 text-secondary"><i class="fas fa-gem me-2"></i>Gold Repledge & Status Information</h5>'),
            Row(
                Column('gold_location', css_class='col-md-6'),
                Column('repledge_date', css_class='col-md-6'),
            ),
            Row(
                Column('repledge_amount', css_class='col-md-6'),
                Column('gold_status_others', css_class='col-md-6'),
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

        # Determine whether this is a new loan creation or an edit
        is_edit = self.instance and self.instance.pk is not None

        issue_date = self.cleaned_data.get('issue_date')
        due_date = None

        if not is_edit:
            # ── NEW LOAN: auto-calculate due_date from scheme duration ──
            if issue_date and scheme.loan_duration:
                due_date = issue_date + timezone.timedelta(days=scheme.loan_duration)
                self.cleaned_data['due_date'] = due_date
                self.cleaned_data['grace_period_end'] = due_date + timezone.timedelta(days=5)
        else:
            # ── EDIT LOAN: honour whatever due_date the user submitted ──
            due_date = self.cleaned_data.get('due_date')
            if due_date:
                self.cleaned_data['grace_period_end'] = due_date + timezone.timedelta(days=5)

        # Calculate interest_rate from the scheme's tiered structure
        if not is_edit:
            # For new loans always derive interest_rate from scheme
            if issue_date and due_date:
                months = ((due_date.year - issue_date.year) * 12 + due_date.month - issue_date.month)
                if due_date.day > issue_date.day:
                    months += 1
                if scheme.interest_rate_structure:
                    self.cleaned_data['interest_rate'] = scheme.get_interest_rate_for_tenure(months)
                else:
                    self.cleaned_data['interest_rate'] = scheme.interest_rate
            else:
                self.cleaned_data['interest_rate'] = scheme.interest_rate
        else:
            # For edits: keep the submitted interest_rate; fall back to scheme only if blank
            submitted_rate = self.cleaned_data.get('interest_rate')
            if not submitted_rate:
                if issue_date and due_date and scheme.interest_rate_structure:
                    months = ((due_date.year - issue_date.year) * 12 + due_date.month - issue_date.month)
                    if due_date.day > issue_date.day:
                        months += 1
                    self.cleaned_data['interest_rate'] = scheme.get_interest_rate_for_tenure(months)
                else:
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
            if cleaned_data.get('principal_amount') is not None and cleaned_data.get('principal_amount') != '':
                cleaned_data['principal_amount'] = int(float(cleaned_data['principal_amount']))
            if cleaned_data.get('processing_fee') is not None and cleaned_data.get('processing_fee') != '':
                cleaned_data['processing_fee'] = int(float(cleaned_data['processing_fee']))
        except (ValueError, TypeError):
            raise ValidationError("Please enter valid whole numbers for principal amount and processing fee")

        # Calculate processing fee and distribution amount based on scheme's processing fee percentage
        principal_amount = cleaned_data.get('principal_amount')
        distribution_amount = cleaned_data.get('distribution_amount')
        is_edit = self.instance and self.instance.pk is not None
        if (principal_amount or distribution_amount) and scheme:
            if not is_edit:
                # NEW LOAN: auto-calculate processing fee from scheme percentage on distribution amount if not provided
                processing_fee_percentage = 1.0  # Default to 1%
                if scheme.additional_conditions and 'processing_fee_percentage' in scheme.additional_conditions:
                    processing_fee_percentage = float(scheme.additional_conditions['processing_fee_percentage'])
                
                if 'processing_fee' not in cleaned_data or cleaned_data.get('processing_fee') is None:
                    if distribution_amount:
                        cleaned_data['processing_fee'] = round(float(distribution_amount) * (processing_fee_percentage / 100))
                    elif principal_amount:
                        fee_rate = processing_fee_percentage / 100
                        calc_dist = round(float(principal_amount) / (1.0 + fee_rate))
                        cleaned_data['processing_fee'] = principal_amount - calc_dist
                        cleaned_data['distribution_amount'] = calc_dist

            processing_fee = cleaned_data.get('processing_fee', 0) or 0
            # Ensure both principal_amount and distribution_amount are properly populated
            if not cleaned_data.get('distribution_amount') and principal_amount is not None:
                cleaned_data['distribution_amount'] = principal_amount - processing_fee
            elif not cleaned_data.get('principal_amount') and distribution_amount is not None:
                cleaned_data['principal_amount'] = distribution_amount + processing_fee

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

        # Calculate allowed principal amount range using Central Daily Rate & Strict RBI LTV Cap
        if all(cleaned_data.get(f) for f in ['market_price_22k', 'gold_karat', 'net_weight']):
            market_price = Decimal(str(cleaned_data['market_price_22k']))
            selected_karat = cleaned_data['gold_karat']
            net_weight = Decimal(str(cleaned_data['net_weight']))

            from schemes.models import DailyGoldRate
            org = getattr(self.user, 'organization', None) if self.user else None
            rate_obj = DailyGoldRate.get_current_rate(organization=org)
            if rate_obj and rate_obj.rate_22k_per_gram:
                market_price = Decimal(str(rate_obj.rate_22k_per_gram))
                cleaned_data['market_price_22k'] = market_price

            # Calculate gold value based on market price for 22K and purity ratio
            karat_purities = {
                '24K': Decimal('0.999'),
                '24': Decimal('0.999'),
                '22K': Decimal('0.916'),
                '22': Decimal('0.916'),
                '21K': Decimal('0.875'),
                '21': Decimal('0.875'),
                '20K': Decimal('0.833'),
                '20': Decimal('0.833'),
                '18K': Decimal('0.750'),
                '18': Decimal('0.750'),
                '16K': Decimal('0.666'),
                '16': Decimal('0.666'),
                '14K': Decimal('0.583'),
                '14': Decimal('0.583'),
                '12K': Decimal('0.500'),
                '12': Decimal('0.500'),
                '10K': Decimal('0.417'),
                '10': Decimal('0.417'),
                '9K': Decimal('0.375'),
                '9': Decimal('0.375'),
                '8K': Decimal('0.333'),
                '8': Decimal('0.333'),
            }

            base_22k_purity = Decimal('0.916')

            items_json_str = cleaned_data.get('items_json') or self.data.get('items_json') or ''
            gold_value = Decimal('0.00')

            if items_json_str:
                try:
                    import json
                    parsed_items = json.loads(items_json_str)
                    if isinstance(parsed_items, list) and len(parsed_items) > 0:
                        for it in parsed_items:
                            it_net = Decimal(str(it.get('net_weight') or 0))
                            if it_net <= 0:
                                it_gross = Decimal(str(it.get('gross_weight') or 0))
                                it_stone = Decimal(str(it.get('stone_weight') or 0))
                                it_net = max(Decimal('0'), it_gross - it_stone)
                            it_karat = str(it.get('karat') or '22').replace('.0', '').replace('.00', '').strip()
                            it_purity = karat_purities.get(it_karat, base_22k_purity)
                            it_ratio = it_purity / base_22k_purity
                            gold_value += it_net * it_ratio * market_price
                except Exception:
                    gold_value = Decimal('0.00')

            if gold_value <= 0:
                karat_purity = karat_purities.get(str(selected_karat), base_22k_purity)
                purity_ratio = karat_purity / base_22k_purity
                gold_value = market_price * net_weight * purity_ratio

            # Determine statutory RBI Cap (Default 75.00%, Hard ceiling 90.00% under RBI norms)
            rbi_ltv_cap = rate_obj.maximum_ltv_percentage if rate_obj else Decimal('75.00')
            if rbi_ltv_cap > Decimal('90.00'):
                rbi_ltv_cap = Decimal('90.00')

            effective_ltv = rbi_ltv_cap
            max_principal = round(gold_value * (effective_ltv / Decimal('100.0')))
            min_principal = round(gold_value * Decimal('0.10'))

            if principal_amount:
                if principal_amount > max_principal:
                    self.add_error(
                        'principal_amount',
                        f'Principal amount of ₹{principal_amount:,} exceeds the maximum eligible loan of ₹{max_principal:,} (RBI LTV Cap: {effective_ltv}%, Gold Value: ₹{gold_value:,.2f})'
                    )
                elif principal_amount < min_principal:
                    self.add_error(
                        'principal_amount',
                        f'Principal amount must be at least ₹{min_principal:,} (10% of gold value)'
                    )

        # -------------------------------------------------------------------
        # Section 269SS Statutory Compliance: Loan Disbursal Rules
        # -------------------------------------------------------------------
        payout_amount = cleaned_data.get('distribution_amount')
        if payout_amount is None and principal_amount is not None:
            payout_amount = principal_amount - (cleaned_data.get('processing_fee') or 0)

        disb_mode = cleaned_data.get('disbursement_mode') or 'CASH'
        bank_acc = (cleaned_data.get('bank_account_number') or '').strip()
        bank_ifsc = (cleaned_data.get('bank_ifsc_code') or '').strip().upper()

        if payout_amount is not None:
            try:
                payout_decimal = Decimal(str(payout_amount))
            except (InvalidOperation, TypeError, ValueError):
                payout_decimal = Decimal('0')

            if payout_decimal >= Decimal('20000.00'):
                if disb_mode == 'CASH':
                    self.add_error(
                        'disbursement_mode',
                        f"Section 269SS Statutory Violation: Loan disbursal of ₹{payout_decimal:,.2f} is ₹20,000 or more and CANNOT be disbursed in Cash. "
                        f"Under Section 269SS of the Income Tax Act, you must select Bank Transfer (NEFT/RTGS/IMPS), UPI, or Cheque."
                    )
                elif disb_mode in ['BANK_TRANSFER', 'NEFT', 'IMPS', 'RTGS']:
                    if not bank_acc:
                        self.add_error('bank_account_number', 'Beneficiary bank account number is required for bank transfer disbursals.')
                    if not bank_ifsc:
                        self.add_error('bank_ifsc_code', 'Bank IFSC code is required for bank transfer disbursals.')
                    elif not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', bank_ifsc):
                        self.add_error('bank_ifsc_code', 'Invalid IFSC code format (expected 11 chars: 4 uppercase letters, 0, 6 letters/digits e.g. HDFC0001234).')
            else:
                # Disbursals < ₹20,000: Validate IFSC if entered
                if disb_mode in ['BANK_TRANSFER', 'NEFT', 'IMPS', 'RTGS']:
                    if bank_ifsc and not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', bank_ifsc):
                        self.add_error('bank_ifsc_code', 'Invalid IFSC code format (e.g. HDFC0001234).')

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

        # Set distribution_amount (base distribution amount: principal - processing_fee)
        if instance.principal_amount is not None:
            if self.cleaned_data.get('distribution_amount'):
                instance.distribution_amount = self.cleaned_data['distribution_amount']
            elif instance.distribution_amount is None:
                proc_fee = instance.processing_fee or 0
                instance.distribution_amount = instance.principal_amount - proc_fee

        # Set grace_period_end if due_date is set
        if instance.due_date:
            instance.grace_period_end = instance.due_date + timedelta(days=5)

        if commit:
            from django.db import transaction
            with transaction.atomic():
                instance.save()
                
                # Check if multi-item JSON is provided
                items_json_str = self.cleaned_data.get('items_json') or self.data.get('items_json') or ''
                parsed_items = []
                if items_json_str:
                    try:
                        import json
                        raw_parsed = json.loads(items_json_str)
                        if isinstance(raw_parsed, list):
                            parsed_items = [x for x in raw_parsed if isinstance(x, dict) and (x.get('name') or x.get('name_tamil'))]
                    except Exception:
                        parsed_items = []

                if parsed_items and len(parsed_items) > 0:
                    # Multi-item structure: clear prior loan items for this loan
                    instance.loanitem_set.all().delete()
                    for it_data in parsed_items:
                        it_name = (it_data.get('name') or it_data.get('name_tamil') or 'Gold Ornament').strip()
                        it_ta = (it_data.get('name_tamil') or '').strip()
                        it_qty = int(it_data.get('quantity', 1) or 1)
                        it_karat = Decimal(str(it_data.get('karat') or self.cleaned_data.get('gold_karat') or 22.0))
                        it_gross = Decimal(str(it_data.get('gross_weight') or 0.0))
                        it_stone = Decimal(str(it_data.get('stone_weight') or 0.0))
                        it_net = Decimal(str(it_data.get('net_weight') or max(0, it_gross - it_stone)))

                        new_item = Item(
                            name=it_name,
                            description=self.cleaned_data.get('item_description', ''),
                            tamil_name=it_ta,
                            tamil_description=self.cleaned_data.get('item_description_tamil', ''),
                            tamil_brand='',
                            tamil_model='',
                            tamil_tags='',
                            tamil_notes='',
                            category=self.cleaned_data['item_category'],
                            status='pawned',
                            branch=instance.branch if instance.branch else (self.user.branch if self.user else None),
                            created_by=self.user
                        )
                        new_item.save()

                        loan_item = LoanItem(
                            loan=instance,
                            item=new_item,
                            quantity=it_qty,
                            gold_karat=it_karat,
                            gross_weight=it_gross,
                            net_weight=it_net,
                            stone_weight=it_stone,
                            market_price_22k=self.cleaned_data['market_price_22k']
                        )
                        loan_item.save()
                elif instance.pk and instance.loanitem_set.exists():
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

                # Synchronize physical VaultPouch record (Enterprise Gold Custody)
                try:
                    from inventory.models import VaultPouch, VaultAuditLog
                    
                    target_branch = instance.branch or (self.user.branch if self.user and hasattr(self.user, 'branch') else None)
                    if not target_branch:
                        from branches.models import Branch
                        target_branch = Branch.objects.first()

                    pouch_no = self.cleaned_data.get('pouch_number') or f"PCH-{target_branch.id if target_branch else '0'}-{instance.loan_number}"
                    safe_loc = self.cleaned_data.get('safe_locker_number') or (instance.gold_location or 'Safe-01 / Locker-A1')
                    rack_loc = self.cleaned_data.get('shelf_rack_number') or 'Rack-01 / Tray-A1'
                    seal_bc = self.cleaned_data.get('seal_barcode') or ''
                    
                    # Compute weights
                    gross_wt = self.cleaned_data.get('gross_weight') or Decimal('0.000')
                    net_wt = self.cleaned_data.get('net_weight') or Decimal('0.000')
                    item_qty = _extract_item_quantity_from_name(self.cleaned_data.get('item_name', ''))

                    pouch = getattr(instance, 'vault_pouch', None)
                    if not pouch:
                        pouch = VaultPouch.objects.filter(loan=instance).first()

                    if not pouch:
                        pouch = VaultPouch.objects.create(
                            pouch_number=pouch_no,
                            loan=instance,
                            branch=target_branch,
                            safe_locker_number=safe_loc,
                            shelf_rack_number=rack_loc,
                            seal_barcode=seal_bc,
                            gross_weight=gross_wt,
                            net_weight=net_wt,
                            item_count=item_qty,
                            custodian_maker=self.user,
                            status='pending_inward'
                        )
                        VaultAuditLog.objects.create(
                            pouch=pouch,
                            action='sealed',
                            performed_by=self.user,
                            new_location=f"{safe_loc} [{rack_loc}]",
                            remarks=f"Gold sealed in security pouch #{pouch_no} for Loan #{instance.loan_number}"
                        )
                    else:
                        old_loc = f"{pouch.safe_locker_number} [{pouch.shelf_rack_number}]"
                        new_loc = f"{safe_loc} [{rack_loc}]"
                        if pouch_no:
                            pouch.pouch_number = pouch_no
                        pouch.safe_locker_number = safe_loc
                        pouch.shelf_rack_number = rack_loc
                        pouch.seal_barcode = seal_bc
                        pouch.gross_weight = gross_wt
                        pouch.net_weight = net_wt
                        pouch.item_count = item_qty
                        pouch.save()

                        if old_loc != new_loc:
                            VaultAuditLog.objects.create(
                                pouch=pouch,
                                action='location_moved',
                                performed_by=self.user,
                                old_location=old_loc,
                                new_location=new_loc,
                                remarks="Locker/Rack location updated via loan form edit"
                            )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Error syncing VaultPouch on loan save: {e}")

                # Synchronize DisbursementTransaction record (Section 269SS/269T Compliance)
                try:
                    disb_mode = self.cleaned_data.get('disbursement_mode', 'CASH')
                    bank_acc = self.cleaned_data.get('bank_account_number') or ''
                    bank_ifsc = (self.cleaned_data.get('bank_ifsc_code') or '').upper()
                    bank_name = self.cleaned_data.get('bank_name') or ''
                    beneficiary = self.cleaned_data.get('bank_beneficiary_name') or (instance.customer.full_name if instance.customer else '')
                    utr = self.cleaned_data.get('disbursement_utr') or ''
                    
                    disbursal_amt = instance.distribution_amount
                    if disbursal_amt is None:
                        disbursal_amt = (instance.principal_amount or Decimal('0')) - (instance.processing_fee or Decimal('0'))

                    DisbursementTransaction.objects.update_or_create(
                        loan=instance,
                        defaults={
                            'payment_mode': disb_mode,
                            'amount': disbursal_amt,
                            'account_number': bank_acc,
                            'ifsc_code': bank_ifsc,
                            'bank_name': bank_name,
                            'beneficiary_name': beneficiary,
                            'utr_number': utr,
                            'disbursed_by': self.user if hasattr(self, 'user') and self.user and self.user.is_authenticated else None,
                            'bank_status': 'PROCESSED'
                        }
                    )

                    # Synchronize customer profile bank details if provided
                    if instance.customer and bank_acc and bank_ifsc:
                        cust = instance.customer
                        cust_updated = False
                        if not cust.bank_account_number or cust.bank_account_number != bank_acc:
                            cust.bank_account_number = bank_acc
                            cust_updated = True
                        if not cust.bank_ifsc_code or cust.bank_ifsc_code != bank_ifsc:
                            cust.bank_ifsc_code = bank_ifsc
                            cust_updated = True
                        if bank_name and (not cust.bank_name or cust.bank_name != bank_name):
                            cust.bank_name = bank_name
                            cust_updated = True
                        if beneficiary and (not cust.bank_beneficiary_name or cust.bank_beneficiary_name != beneficiary):
                            cust.bank_beneficiary_name = beneficiary
                            cust_updated = True
                        if cust_updated:
                            cust.save(update_fields=['bank_account_number', 'bank_ifsc_code', 'bank_name', 'bank_beneficiary_name'])
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Error syncing DisbursementTransaction on loan save: {e}")
        
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
            self.add_error('extension_fee', f"Extension fee must be at least 0.5% of the principal amount (Rs: {min_fee}).")
        
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


class PaymentRecordForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_date', 'payment_method', 'reference_number', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg font-monospace fw-bold',
                'step': '0.01',
                'id': 'id_amount',
                'placeholder': '0.00'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'id_payment_date'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_payment_method'
            }),
            'reference_number': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_reference_number',
                'placeholder': 'e.g. UTR / Cheque / Txn ID'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'id': 'id_notes',
                'placeholder': 'Optional remarks or payment notes...'
            }),
        }

