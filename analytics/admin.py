from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    RiskProfile, LoanPrediction, CashFlowForecast, MarketIndicator, RiskAlert,
    ExpenseCategory, BusinessExpense, RecurringExpense
)


@admin.register(RiskProfile)
class RiskProfileAdmin(admin.ModelAdmin):
    list_display = ('customer', 'risk_score', 'risk_level', 'total_loans_count', 
                   'active_loans_count', 'defaulted_loans_count', 'last_calculated')
    list_filter = ('risk_level', 'last_calculated', 'customer__branch')
    search_fields = ('customer__first_name', 'customer__last_name', 'customer__phone')
    readonly_fields = ('last_calculated', 'calculation_version')
    ordering = ['-risk_score']
    
    fieldsets = (
        ('Customer Information', {
            'fields': ('customer',)
        }),
        ('Risk Assessment', {
            'fields': ('risk_score', 'risk_level')
        }),
        ('Risk Components', {
            'fields': ('payment_history_score', 'loan_to_value_score', 'demographic_score',
                      'economic_indicator_score', 'behavioral_score'),
            'classes': ('collapse',)
        }),
        ('Loan Statistics', {
            'fields': ('total_loans_count', 'active_loans_count', 'defaulted_loans_count',
                      'average_loan_amount', 'total_repaid_amount'),
            'classes': ('collapse',)
        }),
        ('Timeline', {
            'fields': ('customer_tenure_days', 'last_loan_date', 'last_payment_date'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('last_calculated', 'calculation_version'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(customer__branch__staff=request.user)
    
    def risk_level(self, obj):
        colors = {
            'very_low': '#28a745',  # Green
            'low': '#6c757d',       # Gray
            'medium': '#ffc107',    # Yellow
            'high': '#fd7e14',      # Orange
            'very_high': '#dc3545'  # Red
        }
        color = colors.get(obj.risk_level, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_risk_level_display()
        )
    risk_level.short_description = 'Risk Level'


@admin.register(LoanPrediction)
class LoanPredictionAdmin(admin.ModelAdmin):
    list_display = ('loan', 'prediction_type', 'probability', 'confidence_level', 'created_at')
    list_filter = ('prediction_type', 'created_at', 'loan__branch')
    search_fields = ('loan__loan_number', 'loan__customer__first_name', 'loan__customer__last_name')
    readonly_fields = ('created_at', 'updated_at', 'model_version')
    ordering = ['-created_at']
    
    fieldsets = (
        ('Loan Information', {
            'fields': ('loan',)
        }),
        ('Prediction Details', {
            'fields': ('prediction_type', 'probability', 'confidence_level')
        }),
        ('Model Information', {
            'fields': ('factors_considered', 'model_version'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(loan__branch__staff=request.user)


@admin.register(CashFlowForecast)
class CashFlowForecastAdmin(admin.ModelAdmin):
    list_display = ('branch', 'forecast_date', 'forecast_type', 'predicted_net_cash_flow', 
                   'confidence_level', 'created_at')
    list_filter = ('forecast_type', 'branch', 'forecast_date')
    search_fields = ('branch__name',)
    readonly_fields = ('created_at', 'model_version')
    ordering = ['-forecast_date']
    
    fieldsets = (
        ('Forecast Information', {
            'fields': ('branch', 'forecast_date', 'forecast_type')
        }),
        ('Cash Flow Components', {
            'fields': ('predicted_loan_disbursements', 'predicted_loan_repayments',
                      'predicted_interest_income', 'predicted_fee_income',
                      'predicted_sales_revenue', 'predicted_operating_expenses')
        }),
        ('Net Cash Flow & Confidence', {
            'fields': ('predicted_net_cash_flow', 'confidence_level')
        }),
        ('Adjustments', {
            'fields': ('seasonal_adjustment', 'trend_adjustment'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'model_version'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(branch__staff=request.user)
    
    def predicted_net_cash_flow(self, obj):
        value = obj.predicted_net_cash_flow
        color = '#28a745' if value >= 0 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">₹{:,.2f}</span>',
            color,
            value
        )
    predicted_net_cash_flow.short_description = 'Net Cash Flow'


@admin.register(MarketIndicator)
class MarketIndicatorAdmin(admin.ModelAdmin):
    list_display = ('indicator_type', 'date', 'value', 'source', 'region', 'created_at')
    list_filter = ('indicator_type', 'date', 'source', 'region')
    search_fields = ('source', 'notes')
    ordering = ['-date', 'indicator_type']
    
    fieldsets = (
        ('Indicator Information', {
            'fields': ('indicator_type', 'date', 'value', 'source')
        }),
        ('Location & Notes', {
            'fields': ('region', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def value(self, obj):
        # Format value based on indicator type
        if obj.indicator_type == 'gold_price':
            return f"₹{obj.value:,.2f}/gram"
        elif obj.indicator_type in ['interest_rate', 'inflation_rate', 'unemployment_rate']:
            return f"{obj.value}%"
        elif obj.indicator_type == 'gdp_growth':
            return f"{obj.value}%"
        else:
            return f"{obj.value}"
    value.short_description = 'Value'


@admin.register(RiskAlert)
class RiskAlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'alert_type', 'severity', 'status', 'customer', 'branch', 'created_at')
    list_filter = ('alert_type', 'severity', 'status', 'created_at', 'branch')
    search_fields = ('title', 'description', 'customer__first_name', 'customer__last_name', 'branch__name')
    readonly_fields = ('created_at', 'acknowledged_at', 'resolved_at')
    ordering = ['-created_at']
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('alert_type', 'severity', 'status', 'title', 'description', 'recommendation')
        }),
        ('Related Objects', {
            'fields': ('customer', 'loan', 'branch')
        }),
        ('Alert Data', {
            'fields': ('threshold_value', 'actual_value'),
            'classes': ('collapse',)
        }),
        ('User Tracking', {
            'fields': ('created_by', 'acknowledged_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'acknowledged_at', 'resolved_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_acknowledged', 'mark_resolved', 'mark_dismissed']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(branch__staff=request.user)
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def severity(self, obj):
        colors = {
            'low': '#6c757d',       # Gray
            'medium': '#ffc107',    # Yellow
            'high': '#fd7e14',      # Orange
            'critical': '#dc3545'  # Red
        }
        color = colors.get(obj.severity, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_severity_display()
        )
    severity.short_description = 'Severity'
    
    def status(self, obj):
        colors = {
            'active': '#dc3545',      # Red
            'acknowledged': '#ffc107', # Yellow
            'resolved': '#28a745',    # Green
            'dismissed': '#6c757d'    # Gray
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status.short_description = 'Status'
    
    def mark_acknowledged(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            status='acknowledged',
            acknowledged_by=request.user,
            acknowledged_at=timezone.now()
        )
        self.message_user(request, f'{updated} alerts marked as acknowledged.')
    mark_acknowledged.short_description = "Mark selected alerts as acknowledged"
    
    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            status='resolved',
            resolved_at=timezone.now()
        )
        self.message_user(request, f'{updated} alerts marked as resolved.')
    mark_resolved.short_description = "Mark selected alerts as resolved"
    
    def mark_dismissed(self, request, queryset):
        updated = queryset.update(status='dismissed')
        self.message_user(request, f'{updated} alerts dismissed.')
    mark_dismissed.short_description = "Dismiss selected alerts"


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent_category', 'is_active', 'created_at']
    list_filter = ['is_active', 'parent_category']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(BusinessExpense)
class BusinessExpenseAdmin(admin.ModelAdmin):
    list_display = [
        'expense_number', 'category', 'amount', 'total_amount', 
        'expense_date', 'vendor_name', 'is_approved', 'branch'
    ]
    list_filter = [
        'expense_type', 'category', 'is_approved', 'branch', 
        'expense_date', 'payment_method'
    ]
    search_fields = [
        'expense_number', 'description', 'vendor_name', 
        'invoice_number', 'reference_number'
    ]
    date_hierarchy = 'expense_date'
    readonly_fields = ['expense_number', 'total_amount', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('expense_number', 'category', 'expense_type', 'description', 'expense_date')
        }),
        ('Financial Details', {
            'fields': ('amount', 'total_tax', 'total_amount')
        }),
        ('Vendor Information', {
            'fields': ('vendor_name', 'vendor_gstin', 'invoice_number')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'reference_number')
        }),
        ('GST Details', {
            'fields': ('gst_rate', 'cgst_amount', 'sgst_amount', 'igst_amount'),
            'classes': ('collapse',)
        }),
        ('Branch & Approval', {
            'fields': ('branch', 'is_approved', 'recorded_by', 'approved_by')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.is_approved:
            readonly.extend(['amount', 'category', 'expense_type', 'vendor_name'])
        return readonly


@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category', 'amount', 'frequency', 
        'next_due_date', 'is_active', 'branch'
    ]
    list_filter = ['frequency', 'is_active', 'branch', 'category']
    search_fields = ['name', 'description']
    date_hierarchy = 'next_due_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'description')
        }),
        ('Financial Details', {
            'fields': ('amount', 'frequency')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'next_due_date')
        }),
        ('Settings', {
            'fields': ('branch', 'is_active', 'auto_create')
        })
    )


# Custom admin site modifications
admin.site.site_header = "Pawnshop Risk Analytics Administration"
admin.site.site_title = "Risk Analytics Admin"
admin.site.index_title = "Welcome to Risk Analytics Administration"
