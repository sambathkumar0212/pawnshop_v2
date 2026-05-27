from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import json


class RiskProfile(models.Model):
    """Model to store customer risk profiles and scoring"""
    
    RISK_LEVEL_CHOICES = [
        ('very_low', 'Very Low Risk'),
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('very_high', 'Very High Risk'),
    ]
    
    customer = models.OneToOneField('accounts.Customer', on_delete=models.CASCADE, related_name='risk_profile')
    risk_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES)
    
    # Risk factors
    payment_history_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    loan_to_value_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    demographic_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    economic_indicator_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    behavioral_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Additional risk factors
    total_loans_count = models.IntegerField(default=0)
    active_loans_count = models.IntegerField(default=0)
    defaulted_loans_count = models.IntegerField(default=0)
    average_loan_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_repaid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Time-based factors
    customer_tenure_days = models.IntegerField(default=0)
    last_loan_date = models.DateField(null=True, blank=True)
    last_payment_date = models.DateField(null=True, blank=True)
    
    # Metadata
    last_calculated = models.DateTimeField(auto_now=True)
    calculation_version = models.CharField(max_length=10, default='1.0')
    
    class Meta:
        verbose_name = _('Risk Profile')
        verbose_name_plural = _('Risk Profiles')
        
    def __str__(self):
        return f"{self.customer.full_name} - {self.risk_level} ({self.risk_score})"


class LoanPrediction(models.Model):
    """Model to store loan performance predictions"""
    
    PREDICTION_TYPE_CHOICES = [
        ('default_risk', 'Default Risk'),
        ('early_repayment', 'Early Repayment'),
        ('extension_likelihood', 'Extension Likelihood'),
        ('renewal_probability', 'Renewal Probability'),
    ]
    
    loan = models.ForeignKey('transactions.Loan', on_delete=models.CASCADE, related_name='predictions')
    prediction_type = models.CharField(max_length=30, choices=PREDICTION_TYPE_CHOICES)
    probability = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Prediction factors
    factors_considered = models.JSONField(default=dict)
    model_version = models.CharField(max_length=10, default='1.0')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Loan Prediction')
        verbose_name_plural = _('Loan Predictions')
        unique_together = ['loan', 'prediction_type']
        
    def __str__(self):
        return f"{self.loan.loan_number} - {self.prediction_type} ({self.probability}%)"


class CashFlowForecast(models.Model):
    """Model to store cash flow predictions for branches"""
    
    FORECAST_TYPE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ]
    
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='cash_flow_forecasts')
    forecast_date = models.DateField()
    forecast_type = models.CharField(max_length=20, choices=FORECAST_TYPE_CHOICES)
    
    # Cash flow components
    predicted_loan_disbursements = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    predicted_loan_repayments = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    predicted_interest_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    predicted_fee_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    predicted_sales_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    predicted_operating_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Net cash flow
    predicted_net_cash_flow = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Seasonal and trend factors
    seasonal_adjustment = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    trend_adjustment = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    model_version = models.CharField(max_length=10, default='1.0')
    
    class Meta:
        verbose_name = _('Cash Flow Forecast')
        verbose_name_plural = _('Cash Flow Forecasts')
        unique_together = ['branch', 'forecast_date', 'forecast_type']
        
    def __str__(self):
        return f"{self.branch.name} - {self.forecast_date} ({self.forecast_type})"


class MarketIndicator(models.Model):
    """Model to store economic and market indicators affecting the business"""
    
    INDICATOR_TYPE_CHOICES = [
        ('gold_price', 'Gold Price'),
        ('interest_rate', 'Interest Rate'),
        ('inflation_rate', 'Inflation Rate'),
        ('unemployment_rate', 'Unemployment Rate'),
        ('gdp_growth', 'GDP Growth'),
        ('seasonal_factor', 'Seasonal Factor'),
    ]
    
    indicator_type = models.CharField(max_length=30, choices=INDICATOR_TYPE_CHOICES)
    date = models.DateField()
    value = models.DecimalField(max_digits=15, decimal_places=6)
    source = models.CharField(max_length=100)
    
    # Additional metadata
    region = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Market Indicator')
        verbose_name_plural = _('Market Indicators')
        unique_together = ['indicator_type', 'date', 'region']
        
    def __str__(self):
        return f"{self.indicator_type} - {self.date}: {self.value}"


class RiskAlert(models.Model):
    """Model to store risk alerts and notifications"""
    
    ALERT_TYPE_CHOICES = [
        ('high_risk_customer', 'High Risk Customer'),
        ('default_prediction', 'Default Prediction'),
        ('cash_flow_warning', 'Cash Flow Warning'),
        ('unusual_pattern', 'Unusual Pattern'),
        ('market_volatility', 'Market Volatility'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    recommendation = models.TextField(blank=True)
    
    # Related objects
    customer = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE, null=True, blank=True, related_name='risk_alerts')
    loan = models.ForeignKey('transactions.Loan', on_delete=models.CASCADE, null=True, blank=True, related_name='risk_alerts')
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, null=True, blank=True, related_name='risk_alerts')
    
    # Alert metadata
    threshold_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # User tracking
    created_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_alerts')
    acknowledged_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_alerts')
    
    class Meta:
        verbose_name = _('Risk Alert')
        verbose_name_plural = _('Risk Alerts')
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.alert_type} - {self.severity} - {self.title}"


class ExpenseCategory(models.Model):
    """Model to define expense categories for business operations"""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Categorization
    parent_category = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Expense Category')
        verbose_name_plural = _('Expense Categories')
        ordering = ['name']
        
    def __str__(self):
        return self.name


class BusinessExpense(models.Model):
    """Model to track business expenses"""
    
    EXPENSE_TYPE_CHOICES = [
        ('operating', 'Operating Expense'),
        ('capital', 'Capital Expense'),
        ('administrative', 'Administrative Expense'),
        ('marketing', 'Marketing Expense'),
        ('maintenance', 'Maintenance Expense'),
        ('other', 'Other'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('other', 'Other'),
    ]
    
    # Basic information
    expense_number = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES, default='operating')
    
    # Financial details
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    description = models.TextField()
    expense_date = models.DateField()
    
    # Vendor/Supplier information
    vendor_name = models.CharField(max_length=200, blank=True)
    vendor_gstin = models.CharField(max_length=15, blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True)
    
    # Payment details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference_number = models.CharField(max_length=255, blank=True)
    
    # GST details
    gst_rate = models.ForeignKey('gst.GSTRate', on_delete=models.PROTECT, null=True, blank=True, related_name='expenses')
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Branch allocation
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='expenses')
    
    # Tracking
    recorded_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, related_name='recorded_expenses')
    approved_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    
    # Status and metadata
    is_approved = models.BooleanField(default=False)
    is_recurring = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Business Expense')
        verbose_name_plural = _('Business Expenses')
        ordering = ['-expense_date', '-created_at']
        
    def __str__(self):
        return f"{self.expense_number} - {self.category.name} - ₹{self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.expense_number:
            # Generate expense number
            from django.utils import timezone
            today = timezone.now().date()
            prefix = f"EXP{today.year}{today.month:02d}"
            last_expense = BusinessExpense.objects.filter(
                expense_number__startswith=prefix
            ).order_by('-expense_number').first()
            
            if last_expense:
                last_num = int(last_expense.expense_number[-4:])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.expense_number = f"{prefix}{new_num:04d}"
        
        # Calculate total amount if not set
        if not self.total_amount:
            self.total_amount = self.amount + self.total_tax
            
        super().save(*args, **kwargs)


class RecurringExpense(models.Model):
    """Model to track recurring expenses like rent, salaries, etc."""
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    # Basic information
    name = models.CharField(max_length=200)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='recurring_expenses')
    description = models.TextField()
    
    # Financial details
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    
    # Schedule
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_due_date = models.DateField()
    
    # Branch allocation
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='recurring_expenses')
    
    # Status
    is_active = models.BooleanField(default=True)
    auto_create = models.BooleanField(default=False, help_text="Automatically create expense records")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Recurring Expense')
        verbose_name_plural = _('Recurring Expenses')
        ordering = ['next_due_date']
        
    def __str__(self):
        return f"{self.name} - {self.frequency} - ₹{self.amount}"
