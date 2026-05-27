from django.contrib import admin
from .models import FaceEnrollment, CustomerFaceEnrollment, FaceAuthLog, BiometricSetting


@admin.register(FaceEnrollment)
class FaceEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_active', 'enrolled_at', 'last_updated')
    list_filter = ('is_active', 'enrolled_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('enrolled_at', 'last_updated')


@admin.register(CustomerFaceEnrollment)
class CustomerFaceEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('customer', 'is_active', 'enrolled_at', 'last_updated')
    list_filter = ('is_active', 'enrolled_at')
    search_fields = ('customer__first_name', 'customer__last_name')
    readonly_fields = ('enrolled_at', 'last_updated')


@admin.register(FaceAuthLog)
class FaceAuthLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'get_status', 'user', 'customer', 'get_confidence', 'ip_address')
    list_filter = ('success', 'timestamp')
    search_fields = ('user__username', 'customer__first_name', 'customer__last_name', 'ip_address')
    readonly_fields = ('user', 'customer', 'timestamp', 'success', 'confidence', 'ip_address', 'device_info')

    def get_status(self, obj):
        return 'Success' if obj.success else 'Failed'
    get_status.short_description = 'Status'

    def get_confidence(self, obj):
        return f'{obj.confidence:.2f}%' if obj.confidence is not None else 'N/A'
    get_confidence.short_description = 'Confidence Score'


@admin.register(BiometricSetting)
class BiometricSettingAdmin(admin.ModelAdmin):
    list_display = ('branch', 'face_recognition_enabled', 'fingerprint_enabled',
                   'face_recognition_required_for_staff', 'face_recognition_required_for_customers')
    list_filter = ('face_recognition_enabled', 'fingerprint_enabled', 'face_recognition_required_for_staff', 'face_recognition_required_for_customers')
    search_fields = ('branch__name',)
    readonly_fields = ('updated_by', 'last_updated')
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
