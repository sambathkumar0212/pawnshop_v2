from django import forms
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from .models import CashTill, CashScrollEntry


class CashTillOpenForm(forms.ModelForm):
    """BOD Opening form for Cash Till"""
    class Meta:
        model = CashTill
        fields = ['opening_balance']
        widgets = {
            'opening_balance': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg font-monospace fw-bold',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            })
        }
        labels = {
            'opening_balance': _('Opening Cash in Till (₹)')
        }


class CashTillReconciliationForm(forms.ModelForm):
    """EOD Reconciliation & Denomination breakdown form"""
    # Denomination counts
    count_500 = forms.IntegerField(min_value=0, required=False, initial=0, widget=forms.NumberInput(attrs={'class': 'form-control denom-input', 'data-value': '500'}))
    count_200 = forms.IntegerField(min_value=0, required=False, initial=0, widget=forms.NumberInput(attrs={'class': 'form-control denom-input', 'data-value': '200'}))
    count_100 = forms.IntegerField(min_value=0, required=False, initial=0, widget=forms.NumberInput(attrs={'class': 'form-control denom-input', 'data-value': '100'}))
    count_50 = forms.IntegerField(min_value=0, required=False, initial=0, widget=forms.NumberInput(attrs={'class': 'form-control denom-input', 'data-value': '50'}))
    count_20 = forms.IntegerField(min_value=0, required=False, initial=0, widget=forms.NumberInput(attrs={'class': 'form-control denom-input', 'data-value': '20'}))
    count_10 = forms.IntegerField(min_value=0, required=False, initial=0, widget=forms.NumberInput(attrs={'class': 'form-control denom-input', 'data-value': '10'}))
    count_5 = forms.IntegerField(min_value=0, required=False, initial=0, widget=forms.NumberInput(attrs={'class': 'form-control denom-input', 'data-value': '5'}))
    count_coins = forms.IntegerField(min_value=0, required=False, initial=0, widget=forms.NumberInput(attrs={'class': 'form-control denom-input', 'data-value': '1'}))

    class Meta:
        model = CashTill
        fields = ['closing_balance_physical', 'discrepancy_reason']
        widgets = {
            'closing_balance_physical': forms.NumberInput(attrs={
                'class': 'form-control font-monospace fw-bold fs-5',
                'readonly': 'readonly',
                'id': 'id_closing_balance_physical'
            }),
            'discrepancy_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Explain any cash shortage or excess variance...')
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.denomination_breakdown:
            db = self.instance.denomination_breakdown
            self.fields['count_500'].initial = db.get('500', 0)
            self.fields['count_200'].initial = db.get('200', 0)
            self.fields['count_100'].initial = db.get('100', 0)
            self.fields['count_50'].initial = db.get('50', 0)
            self.fields['count_20'].initial = db.get('20', 0)
            self.fields['count_10'].initial = db.get('10', 0)
            self.fields['count_5'].initial = db.get('5', 0)
            self.fields['count_coins'].initial = db.get('coins', 0)

    def clean(self):
        cleaned_data = super().clean()
        counts = {
            '500': cleaned_data.get('count_500') or 0,
            '200': cleaned_data.get('count_200') or 0,
            '100': cleaned_data.get('count_100') or 0,
            '50': cleaned_data.get('count_50') or 0,
            '20': cleaned_data.get('count_20') or 0,
            '10': cleaned_data.get('count_10') or 0,
            '5': cleaned_data.get('count_5') or 0,
            'coins': cleaned_data.get('count_coins') or 0,
        }
        total_physical = (
            counts['500'] * 500 +
            counts['200'] * 200 +
            counts['100'] * 100 +
            counts['50'] * 50 +
            counts['20'] * 20 +
            counts['10'] * 10 +
            counts['5'] * 5 +
            counts['coins'] * 1
        )
        cleaned_data['closing_balance_physical'] = Decimal(str(total_physical))
        cleaned_data['denomination_breakdown'] = counts

        # If variance exists, require discrepancy reason
        if self.instance:
            self.instance.sync_live_transactions()
            variance = Decimal(str(total_physical)) - self.instance.closing_balance_system
            if variance != 0 and not cleaned_data.get('discrepancy_reason'):
                self.add_error('discrepancy_reason', _("Discrepancy explanation is required when physical cash does not match system balance."))

        return cleaned_data


class CashBankDepositForm(forms.ModelForm):
    """Form for transferring cash from till to Bank / CIT"""
    class Meta:
        model = CashScrollEntry
        fields = ['amount', 'reference_id', 'description']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '1', 'placeholder': '0.00'}),
            'reference_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Bank Acknowledgment / Challan / CIT Receipt No.')}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': _('e.g. Cash remitted to HDFC Branch Current A/C via CIT courier')}),
        }
        labels = {
            'amount': _('Deposit Amount (₹)'),
            'reference_id': _('Deposit Reference / Challan No.'),
            'description': _('Narration / Bank Name')
        }
