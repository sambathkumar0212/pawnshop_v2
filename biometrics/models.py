from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from accounts.models import Customer  # Import Customer from accounts app


class FaceEnrollment(models.Model):
    """Face enrollment model for facial recognition"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='face_enrollment')
    face_encoding = models.BinaryField()
    face_image = models.ImageField(upload_to='faces/', blank=True, null=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = _('face enrollment')
        verbose_name_plural = _('face enrollments')
        
    def __str__(self):
        return f"Face ID for {self.user}"


class CustomerFaceEnrollment(models.Model):
    """Face enrollment model for customer facial recognition"""
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='face_enrollment')
    face_encoding = models.BinaryField()
    face_image = models.ImageField(upload_to='customer_face_images/', blank=True, null=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = _('customer face enrollment')
        verbose_name_plural = _('customer face enrollments')
        
    def __str__(self):
        return f"Face ID for customer {self.customer}"


class FaceAuthLog(models.Model):
    """Log for face recognition authentication attempts"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='face_auth_logs')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='face_auth_logs', null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    confidence = models.FloatField(null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.TextField(default='', blank=True)  # Added default=''
    
    class Meta:
        verbose_name = _('face authentication log')
        verbose_name_plural = _('face authentication logs')
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"Face auth attempt by {self.user or self.customer} at {self.timestamp}"


class BiometricSetting(models.Model):
    """Settings for biometric authentication"""
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='biometric_settings')
    min_confidence = models.FloatField(default=0.6, help_text=_('Minimum confidence score required for face recognition'))
    max_attempts = models.PositiveIntegerField(default=3, help_text=_('Maximum failed attempts before lockout'))
    lockout_duration = models.DurationField(default='00:30:00', help_text=_('Duration of lockout after max attempts'))
    require_liveness = models.BooleanField(default=True, help_text=_('Whether to require liveness detection'))
    allow_customer_enrollment = models.BooleanField(default=True, help_text=_('Allow customers to enroll in face recognition'))
    
    # New fields
    face_recognition_enabled = models.BooleanField(default=True, help_text=_('Enable face recognition authentication'))
    fingerprint_enabled = models.BooleanField(default=False, help_text=_('Enable fingerprint authentication'))
    face_recognition_required_for_staff = models.BooleanField(default=False, help_text=_('Require staff to use face recognition'))
    face_recognition_required_for_customers = models.BooleanField(default=False, help_text=_('Require customers to use face recognition'))
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='updated_biometric_settings')
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('biometric setting')
        verbose_name_plural = _('biometric settings')
