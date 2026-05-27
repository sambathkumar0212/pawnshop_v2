from django import forms
from .models import GSTRate, GSTTransaction, CompanyGSTDetails
from django.utils import timezone


class CompanyGSTDetailsForm(forms.ModelForm):
    """Form for managing company GST details"""
    
    class Meta:
        model = CompanyGSTDetails
        fields = ['legal_name', 'gstin', 'registration_type', 'state_code', 'address', 'email', 'phone']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
        
    def clean_gstin(self):
        gstin = self.cleaned_data['gstin']
        
        # Validate GSTIN format (15 characters, proper format)
        if len(gstin) != 15:
            raise forms.ValidationError("GSTIN must be exactly 15 characters")
            
        # Additional validation could be added here
            
        return gstin.upper()  # Convert to uppercase


class GSTRateForm(forms.ModelForm):
    """Form for managing GST rates"""
    
    class Meta:
        model = GSTRate
        fields = ['name', 'description', 'hsn_code', 'cgst_rate', 'sgst_rate', 'igst_rate', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate that IGST rate equals CGST + SGST
        cgst_rate = cleaned_data.get('cgst_rate', 0)
        sgst_rate = cleaned_data.get('sgst_rate', 0)
        igst_rate = cleaned_data.get('igst_rate', 0)
        
        if cgst_rate + sgst_rate != igst_rate:
            self.add_error('igst_rate', "IGST rate should equal CGST + SGST rates")
            
        return cleaned_data


class GSTTransactionForm(forms.ModelForm):
    """Form for creating/editing GST transactions"""
    
    class Meta:
        model = GSTTransaction
        fields = [
            'transaction_date', 'transaction_type', 'invoice_number', 'gst_rate',
            'party_name', 'party_gstin', 'is_registered_dealer', 'place_of_supply', 
            'is_interstate', 'taxable_value', 'cgst_amount', 'sgst_amount', 'igst_amount',
            'total_tax', 'total_amount', 'notes'
        ]
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'cgst_amount': forms.NumberInput(attrs={'step': '0.01', 'readonly': True}),
            'sgst_amount': forms.NumberInput(attrs={'step': '0.01', 'readonly': True}),
            'igst_amount': forms.NumberInput(attrs={'step': '0.01', 'readonly': True}),
            'total_tax': forms.NumberInput(attrs={'step': '0.01', 'readonly': True}),
            'total_amount': forms.NumberInput(attrs={'step': '0.01', 'readonly': True}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to show only active GST rates
        self.fields['gst_rate'].queryset = GSTRate.objects.filter(is_active=True).order_by('name')
        
        # Set default date to today
        if not self.instance.pk:
            self.fields['transaction_date'].initial = timezone.now().date()
            
        # Set calculated fields as readonly in the widget
        for field_name in ['cgst_amount', 'sgst_amount', 'igst_amount', 'total_tax', 'total_amount']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['readonly'] = True
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Calculate tax amounts based on rate and taxable value
        gst_rate = cleaned_data.get('gst_rate')
        taxable_value = cleaned_data.get('taxable_value', 0)
        is_interstate = cleaned_data.get('is_interstate', False)
        
        if gst_rate and taxable_value:
            # Set rates from GST rate object
            cgst_rate = gst_rate.cgst_rate
            sgst_rate = gst_rate.sgst_rate
            igst_rate = gst_rate.igst_rate
            
            # Calculate tax amounts based on interstate status
            if is_interstate:
                cgst_amount = 0
                sgst_amount = 0
                igst_amount = (taxable_value * igst_rate) / 100
            else:
                cgst_amount = (taxable_value * cgst_rate) / 100
                sgst_amount = (taxable_value * sgst_rate) / 100
                igst_amount = 0
                
            # Calculate total tax
            total_tax = cgst_amount + sgst_amount + igst_amount
            
            # Calculate total amount
            total_amount = taxable_value + total_tax
            
            # Set on instance
            self.instance.cgst_amount = cgst_amount
            self.instance.sgst_amount = sgst_amount
            self.instance.igst_amount = igst_amount
            self.instance.total_tax = total_tax
            self.instance.total_amount = total_amount
        
        return cleaned_data


class GSTReportForm(forms.Form):
    """Form for GST report generation"""
    
    REPORT_TYPE_CHOICES = [
        ('gstr1', 'GSTR-1 (Outward Supplies)'),
        ('gstr3b', 'GSTR-3B (Summary Return)'),
        ('b2b', 'B2B Invoices (Sales to Registered Dealers)'),
        ('b2c', 'B2C Invoices (Sales to Consumers)'),
        ('hsn_summary', 'HSN Summary'),
    ]
    
    EXPORT_FORMAT_CHOICES = [
        ('csv', 'CSV File'),
        ('excel', 'Excel File'),
        ('pdf', 'PDF Document'),
        ('json', 'JSON File'),
    ]
    
    start_date = forms.DateField(
        label='Start Date',
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text='Report period start date'
    )
    
    end_date = forms.DateField(
        label='End Date',
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text='Report period end date'
    )
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPE_CHOICES,
        initial='gstr1',
        label='Report Type',
        help_text='Select the type of GST report to generate'
    )
    
    export_format = forms.ChoiceField(
        choices=EXPORT_FORMAT_CHOICES,
        initial='excel',
        label='Export Format',
        help_text='Choose the file format for the exported report'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date range to current month
        today = timezone.now().date()
        first_day = today.replace(day=1)
        
        if not self.is_bound:
            self.fields['start_date'].initial = first_day
            self.fields['end_date'].initial = today
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("End date cannot be before start date")
        
        return cleaned_data