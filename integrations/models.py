from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import uuid


class Integration(models.Model):
    """Base model for external system integrations"""
    INTEGRATION_TYPES = [
        ('pos', 'Point of Sale'),
        ('accounting', 'Accounting Software'),
        ('crm', 'Customer Relationship Management'),
        ('sms', 'SMS Service'),
        ('email', 'Email Service'),
        ('payment', 'Payment Gateway'),
        ('ecommerce', 'E-Commerce Platform'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
        ('pending', 'Pending Setup'),
    ]
    
    name = models.CharField(max_length=100)
    integration_type = models.CharField(max_length=20, choices=INTEGRATION_TYPES)
    description = models.TextField(blank=True, null=True)
    api_key = models.CharField(max_length=255, blank=True, null=True)
    api_secret = models.CharField(max_length=255, blank=True, null=True)
    api_endpoint = models.URLField(blank=True, null=True)
    other_credentials = models.JSONField(default=dict)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    is_global = models.BooleanField(default=False, help_text=_('If true, available to all branches'))
    branches = models.ManyToManyField('branches.Branch', blank=True, related_name='integrations')
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = _('integration')
        verbose_name_plural = _('integrations')
        
    def __str__(self):
        return f"{self.name} ({self.get_integration_type_display()})"


class POSIntegration(models.Model):
    """Point of Sale system integration"""
    integration = models.OneToOneField(Integration, on_delete=models.CASCADE, related_name='pos_details')
    pos_provider = models.CharField(max_length=100)
    inventory_sync_enabled = models.BooleanField(default=True)
    transaction_sync_enabled = models.BooleanField(default=True)
    customer_sync_enabled = models.BooleanField(default=True)
    mapping_config = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = _('POS integration')
        verbose_name_plural = _('POS integrations')
        
    def __str__(self):
        return f"POS Integration: {self.pos_provider}"


class AccountingIntegration(models.Model):
    """Accounting software integration"""
    integration = models.OneToOneField(Integration, on_delete=models.CASCADE, related_name='accounting_details')
    accounting_provider = models.CharField(max_length=100)
    sync_sales = models.BooleanField(default=True)
    sync_purchases = models.BooleanField(default=True)
    sync_inventory = models.BooleanField(default=True)
    sync_customers = models.BooleanField(default=True)
    chart_of_accounts_mapping = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = _('accounting integration')
        verbose_name_plural = _('accounting integrations')
        
    def __str__(self):
        return f"Accounting Integration: {self.accounting_provider}"


class CRMIntegration(models.Model):
    """CRM system integration"""
    integration = models.OneToOneField(Integration, on_delete=models.CASCADE, related_name='crm_details')
    crm_provider = models.CharField(max_length=100)
    sync_customers = models.BooleanField(default=True)
    sync_transactions = models.BooleanField(default=True)
    sync_communications = models.BooleanField(default=True)
    field_mapping = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = _('CRM integration')
        verbose_name_plural = _('CRM integrations')
        
    def __str__(self):
        return f"CRM Integration: {self.crm_provider}"


class WebhookEndpoint(models.Model):
    """Webhook endpoints for integration callbacks"""
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='webhooks')
    name = models.CharField(max_length=100)
    endpoint_url = models.CharField(max_length=255, unique=True)
    secret_key = models.CharField(max_length=64, default=uuid.uuid4, editable=False)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('webhook endpoint')
        verbose_name_plural = _('webhook endpoints')
        
    def __str__(self):
        return f"Webhook: {self.name}"


class IntegrationLog(models.Model):
    """Log for integration events and errors"""
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Information'),
    ]
    
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True, null=True)
    
    class Meta:
        verbose_name = _('integration log')
        verbose_name_plural = _('integration logs')
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.integration.name} - {self.event_type} - {self.timestamp}"
