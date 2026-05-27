from django import forms
from .models import Integration, POSIntegration, AccountingIntegration, CRMIntegration

class IntegrationForm(forms.ModelForm):
    class Meta:
        model = Integration
        fields = ['name', 'integration_type', 'description', 'api_key', 
                  'api_secret', 'api_endpoint', 'is_global', 'branches']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class POSIntegrationForm(forms.ModelForm):
    class Meta:
        model = POSIntegration
        fields = ['pos_provider', 'inventory_sync_enabled', 'transaction_sync_enabled',
                 'customer_sync_enabled', 'mapping_config']
        widgets = {
            'mapping_config': forms.Textarea(attrs={'rows': 3}),
        }

class AccountingIntegrationForm(forms.ModelForm):
    class Meta:
        model = AccountingIntegration
        fields = ['accounting_provider', 'sync_sales', 'sync_purchases',
                 'sync_inventory', 'sync_customers', 'chart_of_accounts_mapping']
        widgets = {
            'chart_of_accounts_mapping': forms.Textarea(attrs={'rows': 3}),
        }

class CRMIntegrationForm(forms.ModelForm):
    class Meta:
        model = CRMIntegration
        fields = ['crm_provider', 'sync_customers', 'sync_transactions',
                 'sync_communications', 'field_mapping']
        widgets = {
            'field_mapping': forms.Textarea(attrs={'rows': 3}),
        }