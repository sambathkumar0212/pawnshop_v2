from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal


class CompanyGSTDetails(models.Model):
    """Stores the company's GST registration details"""
    
    REGISTRATION_TYPE_CHOICES = [
        ('REGULAR', 'Regular'),
        ('COMPOSITION', 'Composition Dealer'),
        ('ISD', 'Input Service Distributor (ISD)'),
        ('TDS', 'Tax Deductor at Source (TDS)'),
        ('TCS', 'Tax Collector at Source (TCS)'),
        ('CASUAL', 'Casual Taxable Person'),
        ('NON_RESIDENT', 'Non-Resident Taxable Person'),
        ('SEZ_DEVELOPER', 'SEZ Developer'),
        ('SEZ_UNIT', 'SEZ Unit'),
        ('OIDAR', 'Online Information Database Access/Retrieval Services'),
    ]
    
    legal_name = models.CharField(max_length=255, help_text="Registered business name")
    gstin = models.CharField(max_length=15, help_text="GST Identification Number")
    registration_type = models.CharField(
        max_length=20,
        choices=REGISTRATION_TYPE_CHOICES,
        default='REGULAR',
        help_text="Type of GST registration"
    )
    state_code = models.CharField(max_length=2, help_text="State code as per GST rules")
    address = models.TextField(help_text="Registered business address")
    email = models.EmailField(blank=True, null=True, help_text="Business email for GST correspondence")
    phone = models.CharField(max_length=15, blank=True, null=True, help_text="Business contact number")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Company GST Details')
        verbose_name_plural = _('Company GST Details')
    
    def __str__(self):
        return f"{self.legal_name} (GSTIN: {self.gstin})"


class GSTRate(models.Model):
    """Stores different GST rates with HSN codes"""
    name = models.CharField(max_length=100, help_text="Name of the GST rate category")
    description = models.TextField(blank=True, null=True, help_text="Description of items in this category")
    hsn_code = models.CharField(max_length=20, blank=True, null=True, help_text="HSN code for this category")
    cgst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="CGST rate in percentage (e.g., 9.00 for 9%)"
    )
    sgst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="SGST rate in percentage (e.g., 9.00 for 9%)"
    )
    igst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="IGST rate in percentage (e.g., 18.00 for 18%)"
    )
    is_active = models.BooleanField(default=True, help_text="Whether this rate is currently in use")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('GST Rate')
        verbose_name_plural = _('GST Rates')
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.igst_rate}%)"
    
    def save(self, *args, **kwargs):
        # Ensure IGST equals CGST + SGST if not set
        if self.igst_rate == 0 and (self.cgst_rate > 0 or self.sgst_rate > 0):
            self.igst_rate = self.cgst_rate + self.sgst_rate
        
        super().save(*args, **kwargs)


class GSTTransaction(models.Model):
    """Stores GST transactions for reporting"""
    TRANSACTION_TYPE_CHOICES = [
        ('SALE', 'Sale'),
        ('PURCHASE', 'Purchase'),
        ('LOAN', 'Loan'),
        ('EXTENSION', 'Loan Extension'),
        ('RETURN', 'Return'),
        ('OTHER', 'Other'),
    ]
    
    transaction_date = models.DateField(help_text="Date of the transaction")
    transaction_type = models.CharField(
        max_length=20, 
        choices=TRANSACTION_TYPE_CHOICES,
        default='SALE',
        help_text="Type of transaction"
    )
    invoice_number = models.CharField(
        max_length=50, 
        help_text="Invoice or reference number"
    )
    gst_rate = models.ForeignKey(
        GSTRate, 
        on_delete=models.PROTECT,
        related_name='transactions',
        help_text="GST rate applied to this transaction"
    )
    party_name = models.CharField(
        max_length=255, 
        help_text="Name of the customer/vendor"
    )
    party_gstin = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        help_text="GSTIN of the customer/vendor if registered"
    )
    is_registered_dealer = models.BooleanField(
        default=False,
        help_text="Whether the party is a GST registered dealer"
    )
    place_of_supply = models.CharField(
        max_length=50,
        help_text="State code or name for GST reporting"
    )
    is_interstate = models.BooleanField(
        default=False,
        help_text="Whether it's an interstate transaction (IGST applicable) or intrastate (CGST+SGST)"
    )
    taxable_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Taxable value of the transaction (before tax)"
    )
    cgst_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="CGST amount"
    )
    sgst_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="SGST amount"
    )
    igst_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="IGST amount"
    )
    total_tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total tax amount (CGST + SGST + IGST)"
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total amount including tax"
    )
    notes = models.TextField(blank=True, null=True, help_text="Additional notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Generic relation to associate with any model (Sale, Purchase, etc.)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        verbose_name = _('GST Transaction')
        verbose_name_plural = _('GST Transactions')
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['transaction_date']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['is_interstate']),
            models.Index(fields=['is_registered_dealer']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.invoice_number} - ₹{self.total_amount}"
    
    def save(self, *args, **kwargs):
        # Calculate tax amounts if not already set
        if self.gst_rate and self.taxable_value and self.total_tax == 0:
            if self.is_interstate:
                self.igst_amount = (self.taxable_value * self.gst_rate.igst_rate) / Decimal('100')
                self.cgst_amount = Decimal('0')
                self.sgst_amount = Decimal('0')
            else:
                self.cgst_amount = (self.taxable_value * self.gst_rate.cgst_rate) / Decimal('100')
                self.sgst_amount = (self.taxable_value * self.gst_rate.sgst_rate) / Decimal('100')
                self.igst_amount = Decimal('0')
            
            # Calculate total tax
            self.total_tax = self.cgst_amount + self.sgst_amount + self.igst_amount
            
            # Calculate total amount
            if self.total_amount == 0:
                self.total_amount = self.taxable_value + self.total_tax
        
        super().save(*args, **kwargs)


class GSTReportLog(models.Model):
    """Logs of generated GST reports"""
    REPORT_TYPE_CHOICES = [
        ('GSTR1', 'GSTR-1'),
        ('GSTR3B', 'GSTR-3B'),
        ('B2B', 'B2B Invoices'),
        ('B2C', 'B2C Invoices'),
        ('HSN', 'HSN Summary'),
        ('OTHER', 'Other'),
    ]
    
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    file_path = models.CharField(max_length=255, blank=True, null=True)
    file_format = models.CharField(max_length=20)
    generated_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='gst_reports_generated'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('GST Report Log')
        verbose_name_plural = _('GST Report Logs')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.start_date} to {self.end_date}"
