from django.contrib import admin
from .models import Category, Item, ItemImage, Appraisal, InventoryAudit, ItemAttribute, VaultPouch, VaultAuditLog

class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 1


class ItemAttributeInline(admin.TabularInline):
    model = ItemAttribute
    extra = 1


class AppraisalInline(admin.TabularInline):
    model = Appraisal
    extra = 0
    readonly_fields = ('appraiser', 'appraisal_date')


class VaultAuditLogInline(admin.TabularInline):
    model = VaultAuditLog
    extra = 0
    readonly_fields = ('action', 'performed_by', 'verified_by', 'old_location', 'new_location', 'timestamp', 'remarks')
    can_delete = False


@admin.register(VaultPouch)
class VaultPouchAdmin(admin.ModelAdmin):
    list_display = ('pouch_number', 'loan', 'branch', 'safe_locker_number', 'shelf_rack_number', 'seal_barcode', 'status', 'net_weight', 'sealed_at')
    list_filter = ('status', 'branch', 'safe_locker_number')
    search_fields = ('pouch_number', 'seal_barcode', 'loan__loan_number', 'safe_locker_number')
    readonly_fields = ('created_at', 'updated_at', 'sealed_at', 'inward_verified_at', 'released_at')
    inlines = [VaultAuditLogInline]


@admin.register(VaultAuditLog)
class VaultAuditLogAdmin(admin.ModelAdmin):
    list_display = ('pouch', 'action', 'performed_by', 'verified_by', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('pouch__pouch_number', 'performed_by__username', 'remarks')
    readonly_fields = ('pouch', 'action', 'performed_by', 'verified_by', 'old_location', 'new_location', 'timestamp', 'remarks')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'description')
    list_filter = ('parent',)
    search_fields = ('name', 'description')


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'branch', 'status', 'condition', 'estimated_value', 'selling_price')
    list_filter = ('status', 'condition', 'branch', 'category')
    search_fields = ('name', 'description', 'serial_number', 'brand', 'model')
    inlines = [ItemImageInline, ItemAttributeInline, AppraisalInline]
    readonly_fields = ('added_by', 'created_at')
    
    def save_model(self, request, obj, form, change):
        if not obj.added_by:
            obj.added_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(branch__staff=request.user)


@admin.register(Appraisal)
class AppraisalAdmin(admin.ModelAdmin):
    list_display = ('item', 'appraiser', 'value', 'appraisal_date')
    list_filter = ('appraisal_date', 'appraiser')
    search_fields = ('item__name', 'notes')
    readonly_fields = ('appraisal_date',)
    
    def save_model(self, request, obj, form, change):
        if not obj.appraiser:
            obj.appraiser = request.user
        super().save_model(request, obj, form, change)


@admin.register(InventoryAudit)
class InventoryAuditAdmin(admin.ModelAdmin):
    list_display = ('item', 'action', 'user', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('item__name', 'user__username', 'details')
    readonly_fields = ('item', 'user', 'action', 'timestamp', 'details')

