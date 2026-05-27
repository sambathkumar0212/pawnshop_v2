from django import forms
from .models import Item, Category, ItemImage


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'icon']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'icon': forms.TextInput(attrs={'placeholder': 'fa-tag'}),
        }


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            'name', 'tamil_name', 'description', 'tamil_description', 'category', 'branch', 'serial_number', 
            'brand', 'tamil_brand', 'model', 'tamil_model', 'condition', 'year', 'purchase_price',
            'appraised_value', 'sale_price', 'status', 'featured',
            'customer', 'tags', 'tamil_tags', 'notes', 'tamil_notes'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'tamil_description': forms.Textarea(attrs={'rows': 4}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'tamil_notes': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.TextInput(attrs={'placeholder': 'gold, vintage, collectible'}),
            'tamil_tags': forms.TextInput(attrs={'placeholder': 'tamil tags'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter branches if user is not superuser
        if user and not user.is_superuser and user.branch:
            self.fields['branch'].queryset = self.fields['branch'].queryset.filter(id=user.branch.id)
            self.fields['branch'].initial = user.branch
            self.fields['branch'].widget = forms.HiddenInput()
        
        # Make sale price optional if status is not 'sold'
        if self.instance.pk and self.instance.status != 'sold':
            self.fields['sale_price'].required = False

        # Add custom help texts
        self.fields['purchase_price'].help_text = "Amount paid to acquire this item"
        self.fields['appraised_value'].help_text = "Estimated retail value of the item"
        self.fields['sale_price'].help_text = "Price the item sold for (if applicable)"


class ItemImageForm(forms.ModelForm):
    class Meta:
        model = ItemImage
        fields = ['image', 'caption', 'is_primary']


class ItemFilterForm(forms.Form):
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Search items...',
        'class': 'form-control'
    }))
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=(('', 'All Statuses'),) + Item.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    sort = forms.ChoiceField(
        choices=[
            ('-created_at', 'Newest First'),
            ('created_at', 'Oldest First'),
            ('name', 'Name (A-Z)'),
            ('-name', 'Name (Z-A)'),
            ('appraised_value', 'Value (Low to High)'),
            ('-appraised_value', 'Value (High to Low)')
        ],
        required=False,
        initial='-created_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
