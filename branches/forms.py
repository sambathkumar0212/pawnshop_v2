from django import forms
from .models import Branch, BranchSettings


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'address', 'city', 'state', 'zip_code', 'phone', 
                  'email', 'manager', 'is_active', 'opening_time', 'closing_time']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'opening_time': forms.TimeInput(attrs={'type': 'time'}),
            'closing_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class BranchSettingsForm(forms.ModelForm):
    class Meta:
        model = BranchSettings
        fields = ['max_loan_amount', 'default_interest_rate', 'loan_duration_days', 
                  'grace_period_days', 'require_id_verification', 'enable_face_recognition',
                  'enable_sms_notifications', 'enable_email_notifications',
                  'auction_delay_days']
        widgets = {
            'default_interest_rate': forms.NumberInput(attrs={'min': 0, 'max': 1, 'step': 0.01}),
        }
        
    def clean_default_interest_rate(self):
        rate = self.cleaned_data.get('default_interest_rate')
        if rate and (rate < 0 or rate > 1):
            raise forms.ValidationError("Interest rate must be between 0 and 1 (0% to 100%).")
        return rate