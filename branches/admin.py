from django.contrib import admin
from .models import Branch, BranchSettings


class BranchSettingsInline(admin.StackedInline):
    model = BranchSettings
    can_delete = False
    verbose_name_plural = 'Branch Settings'


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'manager', 'is_active', 'staff_count', 'inventory_count')
    list_filter = ('is_active', 'city', 'state')
    search_fields = ('name', 'address', 'city', 'state', 'phone', 'email')
    inlines = [BranchSettingsInline]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(staff=request.user)


@admin.register(BranchSettings)
class BranchSettingsAdmin(admin.ModelAdmin):
    list_display = ('branch', 'max_loan_amount', 'default_interest_rate', 'loan_duration_days', 
                   'require_id_verification', 'enable_face_recognition')
    list_filter = ('require_id_verification', 'enable_face_recognition')
    search_fields = ('branch__name',)
