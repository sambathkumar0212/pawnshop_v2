from django.contrib import admin
from .models import Category, Item, ItemImage, Appraisal, InventoryAudit, ItemAttribute

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
