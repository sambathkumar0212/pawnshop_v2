from django import forms
from django.utils.translation import gettext_lazy as _
from .models import AccountHead, JournalEntry, JournalItem, AccountCategory


class AccountHeadForm(forms.ModelForm):
    class Meta:
        model = AccountHead
        fields = ['code', 'name', 'category', 'parent', 'branch', 'description', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control font-monospace', 'placeholder': 'e.g. 5060'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Account Title'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Purpose / Description'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BranchExpenseForm(forms.Form):
    """Form to quickly record branch expense voucher"""
    expense_head = forms.ModelChoiceField(
        queryset=AccountHead.objects.filter(category=AccountCategory.EXPENSE, is_active=True),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label=_("Expense Head")
    )
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-lg font-monospace fw-bold', 'placeholder': '0.00'}),
        label=_("Expense Amount (₹)")
    )
    payment_mode = forms.ChoiceField(
        choices=[('CASH', _('Cash in Hand (Counter Drawer)')), ('BANK', _('Bank Current Account / Online'))],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_("Payment Mode")
    )
    narration = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': _('Voucher particulars, invoice # or narration')}),
        label=_("Narration / Description")
    )
