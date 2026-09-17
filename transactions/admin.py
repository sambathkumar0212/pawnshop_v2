from django.contrib import admin
from .models import Loan, Payment, LoanExtension, Sale


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('received_by', 'created_at')


class LoanExtensionInline(admin.TabularInline):
    model = LoanExtension
    extra = 0
    readonly_fields = ('approved_by', 'created_at')


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('loan_number', 'customer', 'get_items', 'principal_amount', 'status', 'due_date', 'is_overdue', 'branch')
    list_filter = ('status', 'branch', 'issue_date')
    search_fields = ('loan_number', 'customer__first_name', 'customer__last_name')
    readonly_fields = ('created_by', 'created_at')
    inlines = [PaymentInline, LoanExtensionInline]
    
    def get_items(self, obj):
        return ", ".join([item.name for item in obj.items.all()])
    get_items.short_description = 'Items'
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(branch__staff=request.user)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('loan', 'amount', 'payment_date', 'payment_method', 'reference_number', 'received_by')
    list_filter = ('payment_date', 'payment_method')
    search_fields = ('loan__loan_number', 'reference_number', 'notes')
    readonly_fields = ('received_by', 'created_at')
    
    def save_model(self, request, obj, form, change):
        if not obj.received_by:
            obj.received_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LoanExtension)
class LoanExtensionAdmin(admin.ModelAdmin):
    list_display = ('loan', 'extension_date', 'previous_due_date', 'new_due_date', 'fee', 'approved_by')
    list_filter = ('extension_date',)
    search_fields = ('loan__loan_number', 'notes')
    readonly_fields = ('approved_by', 'created_at')
    
    def save_model(self, request, obj, form, change):
        if not obj.approved_by:
            obj.approved_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('transaction_number', 'item', 'customer', 'selling_price', 'total_amount', 'status', 'sale_date', 'branch')
    list_filter = ('status', 'sale_date', 'branch', 'payment_method')
    search_fields = ('transaction_number', 'item__name', 'customer__first_name', 'customer__last_name')
    readonly_fields = ('sold_by', 'created_at')
    
    def save_model(self, request, obj, form, change):
        if not obj.sold_by:
            obj.sold_by = request.user
        super().save_model(request, obj, form, change)


from .models import LoanWhatsAppLog, AutopilotConfig, AutopilotLog

@admin.register(LoanWhatsAppLog)
class LoanWhatsAppLogAdmin(admin.ModelAdmin):
    list_display = ('loan', 'customer', 'recipient_phone', 'notification_type', 'status', 'channel', 'sent_by', 'created_at')
    list_filter = ('status', 'notification_type', 'channel', 'created_at')
    search_fields = ('loan__loan_number', 'customer__first_name', 'customer__last_name', 'recipient_phone', 'message_content', 'error_message')
    readonly_fields = ('created_at',)


@admin.register(AutopilotConfig)
class AutopilotConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'is_enabled', 'enable_due_date_reminders', 'enable_ltv_surveillance', 'enable_repledge_retention', 'enable_owner_digest', 'last_status', 'last_run_at')
    readonly_fields = ('last_run_at', 'last_status', 'last_log_summary', 'consecutive_failures', 'updated_at')


@admin.register(AutopilotLog)
class AutopilotLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'pillar', 'action_name', 'target_count', 'success_count', 'failed_count', 'status')
    list_filter = ('pillar', 'status', 'created_at')
    search_fields = ('action_name', 'summary', 'error_details')
    readonly_fields = ('created_at',)

