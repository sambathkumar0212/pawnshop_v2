from django.contrib import admin
from .models import Scheme, SchemeAuditLog

class SchemeAuditLogInline(admin.TabularInline):
    model = SchemeAuditLog
    extra = 0
    readonly_fields = ('user', 'action', 'timestamp', 'ip_address', 'changes')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Scheme)
class SchemeAdmin(admin.ModelAdmin):
    list_display = ('name', 'interest_rate', 'loan_duration', 'status', 'start_date', 'end_date', 'branch')
    list_filter = ('status', 'branch', 'created_at')
    search_fields = ('name', 'description')
    date_hierarchy = 'start_date'
    inlines = [SchemeAuditLogInline]
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'status')
        }),
        ('Conditions', {
            'fields': ('interest_rate', 'loan_duration', 'minimum_amount', 'maximum_amount', 'additional_conditions')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Branch', {
            'fields': ('branch',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating a new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        
        # Create audit log entry
        action = 'updated' if change else 'created'
        SchemeAuditLog.objects.create(
            scheme=obj,
            user=request.user,
            action=action,
            ip_address=request.META.get('REMOTE_ADDR'),
            changes={k: str(v) for k, v in form.changed_data.items()} if change else None
        )

@admin.register(SchemeAuditLog)
class SchemeAuditLogAdmin(admin.ModelAdmin):
    list_display = ('scheme', 'action', 'user', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('scheme__name', 'user__username')
    readonly_fields = ('scheme', 'user', 'action', 'timestamp', 'ip_address', 'changes')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
