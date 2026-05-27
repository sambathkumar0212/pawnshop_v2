from django.contrib import admin
from .models import GSTRate, GSTTransaction, CompanyGSTDetails


@admin.register(GSTRate)
class GSTRateAdmin(admin.ModelAdmin):
    list_display = ('name', 'hsn_code', 'cgst_rate', 'sgst_rate', 'igst_rate', 'get_total_rate', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'hsn_code', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'hsn_code', 'description', 'is_active')
        }),
        ('Tax Rates', {
            'fields': ('cgst_rate', 'sgst_rate', 'igst_rate'),
            'description': 'For intrastate transactions, CGST and SGST are applied. For interstate, IGST is applied.'
        }),
    )
    
    def get_total_rate(self, obj):
        return f"{obj.get_total_rate()}%"
    get_total_rate.short_description = 'Total Rate'


@admin.register(GSTTransaction)
class GSTTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_date', 'transaction_type', 'invoice_number', 'party_name', 
                   'taxable_value', 'total_tax', 'total_amount')
    list_filter = ('transaction_type', 'transaction_date', 'is_interstate')
    search_fields = ('invoice_number', 'party_name', 'party_gstin')
    date_hierarchy = 'transaction_date'
    fieldsets = (
        ('Transaction Details', {
            'fields': ('transaction_date', 'transaction_type', 'invoice_number', 'gst_rate')
        }),
        ('Party Information', {
            'fields': ('party_name', 'party_gstin', 'is_registered_dealer', 'place_of_supply', 'is_interstate')
        }),
        ('Financial Details', {
            'fields': ('taxable_value', 'cgst_amount', 'sgst_amount', 'igst_amount', 'total_tax', 'total_amount')
        }),
        ('Reference', {
            'fields': ('content_type', 'object_id', 'notes')
        }),
    )


@admin.register(CompanyGSTDetails)
class CompanyGSTDetailsAdmin(admin.ModelAdmin):
    list_display = ('legal_name', 'gstin', 'state_code')
    search_fields = ('legal_name', 'trade_name', 'gstin')
    fieldsets = (
        ('GST Registration Details', {
            'fields': ('gstin', 'legal_name', 'trade_name', 'address', 'state_code')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone')
        }),
    )
