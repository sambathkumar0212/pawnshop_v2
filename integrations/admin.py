from django.contrib import admin
from .models import (Integration, POSIntegration, AccountingIntegration, 
                    CRMIntegration, WebhookEndpoint, IntegrationLog)


class POSIntegrationInline(admin.StackedInline):
    model = POSIntegration
    can_delete = False


class AccountingIntegrationInline(admin.StackedInline):
    model = AccountingIntegration
    can_delete = False


class CRMIntegrationInline(admin.StackedInline):
    model = CRMIntegration
    can_delete = False


class WebhookEndpointInline(admin.TabularInline):
    model = WebhookEndpoint
    extra = 1


@admin.register(Integration)
class IntegrationAdmin(admin.ModelAdmin):
    list_display = ('name', 'integration_type', 'status', 'is_global', 'created_at', 'last_sync')
    list_filter = ('integration_type', 'status', 'is_global')
    search_fields = ('name', 'description')
    readonly_fields = ('created_by', 'created_at', 'updated_at', 'last_sync')
    
    def get_inlines(self, request, obj=None):
        if not obj:
            return []
        
        inlines = [WebhookEndpointInline]
        if obj.integration_type == 'pos':
            inlines.append(POSIntegrationInline)
        elif obj.integration_type == 'accounting':
            inlines.append(AccountingIntegrationInline)
        elif obj.integration_type == 'crm':
            inlines.append(CRMIntegrationInline)
            
        return inlines
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ('name', 'integration', 'endpoint_url', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'endpoint_url', 'integration__name')
    readonly_fields = ('secret_key', 'created_at')


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ('integration', 'event_type', 'status', 'timestamp')
    list_filter = ('status', 'event_type', 'timestamp')
    search_fields = ('integration__name', 'message')
    readonly_fields = ('integration', 'timestamp', 'event_type', 'status', 'message', 'data')
