from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify
import uuid
import os
from utils.default_photos import get_default_item_photo

from branches.models import Branch


def item_image_path(instance, filename):
    """Generate a unique file path for inventory item images"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('inventory_images', str(instance.item.id), filename)


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, max_length=100)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('category_detail', args=[str(self.slug)])


class Item(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('pawned', 'Pawned'),
        ('sold', 'Sold'),
        ('expired', 'Expired'),
        ('damaged', 'Damaged'),
        ('maintenance', 'In Maintenance'),
    )
    
    CONDITION_CHOICES = (
        ('new', 'New'),
        ('like_new', 'Like New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    )
    
    item_id = models.CharField(max_length=20, unique=True, help_text="Unique identifier for this item")
    name = models.CharField(max_length=255)
    description = models.TextField()
    tamil_name = models.CharField(max_length=255, blank=True, default='')
    tamil_description = models.TextField(blank=True, default='')
    tamil_brand = models.CharField(max_length=100, blank=True, default='')
    tamil_model = models.CharField(max_length=100, blank=True, default='')
    tamil_tags = models.CharField(max_length=255, blank=True, default='')
    tamil_notes = models.TextField(blank=True, default='')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='items')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='items')
    
    # Item details
    serial_number = models.CharField(max_length=100, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    year = models.PositiveIntegerField(null=True, blank=True)
    
    # Financial details
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    appraised_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    estimated_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    # User relationships
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='created_items',
        on_delete=models.SET_NULL, 
        null=True
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='modified_items',
        on_delete=models.SET_NULL, 
        null=True,
        blank=True
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='added_items',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Customer relationship (who pawned or sold this item to shop)
    customer = models.ForeignKey(
        'accounts.Customer',
        related_name='items',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Loan relationship through LoanItem
    loans = models.ManyToManyField(
        'transactions.Loan',
        through='transactions.LoanItem',
        through_fields=('item', 'loan'),
        related_name='loan_items'  # Changed from 'items' to 'loan_items'
    )
    
    # Additional metadata
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags")
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Dashboard: item counts by status
            models.Index(fields=['status'], name='item_status_idx'),
            # Branch + status filtering used in item list and dashboard
            models.Index(fields=['branch', 'status'], name='item_branch_status_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.item_id})"
        
    def save(self, *args, **kwargs):
        # Generate a unique item ID if not provided
        if not self.item_id:
            # Use branch code + category code + sequential number
            branch_code = self.branch.code if hasattr(self.branch, 'code') else 'XX'
            category_code = self.category.slug[:2].upper() if self.category else 'GN'
            
            # Get the highest existing sequence number for this branch and category prefix
            prefix = f"{branch_code}-{category_code}-"
            highest_item = Item.objects.filter(item_id__startswith=prefix).order_by('-item_id').first()
            
            if highest_item:
                # Extract sequence number from the highest item_id
                try:
                    seq_str = highest_item.item_id.split('-')[-1]
                    seq_num = int(seq_str) + 1
                except (IndexError, ValueError):
                    # Fallback if parsing fails
                    seq_num = 1
            else:
                seq_num = 1
                
            self.item_id = f"{branch_code}-{category_code}-{seq_num:04d}"
            
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('item_detail', args=[str(self.id)])
    
    @property
    def primary_photo(self):
        primary_image = self.images.filter(is_primary=True).first()
        if primary_image and primary_image.image:
            return primary_image.image.url
        from utils.default_photos import get_default_item_photo
        return get_default_item_photo(self.category)

    def get_primary_image(self):
        primary_image = self.images.filter(is_primary=True).first()
        if primary_image and primary_image.image:
            return primary_image.image.url
        from utils.default_photos import get_default_item_photo
        return get_default_item_photo(self.category)
    
    def is_available(self):
        return self.status == 'available'
    
    def is_pawned(self):
        return self.status == 'pawned'


class ItemImage(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=item_image_path)
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    class Meta:
        ordering = ['-is_primary', '-uploaded_at']
    
    def __str__(self):
        return f"Image for {self.item.name}"
    
    def save(self, *args, **kwargs):
        # If this is marked as primary, unmark all others
        if self.is_primary:
            ItemImage.objects.filter(item=self.item, is_primary=True).update(is_primary=False)
        
        # If this is the first image, make it primary
        elif not ItemImage.objects.filter(item=self.item).exists():
            self.is_primary = True
            
        super().save(*args, **kwargs)

class ItemAttribute(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='attributes')
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)
    
    class Meta:
        verbose_name = 'Item Attribute'
        verbose_name_plural = 'Item Attributes'
        unique_together = ('item', 'name')
    
    def __str__(self):
        return f"{self.item.name} - {self.name}: {self.value}"

from django.utils import timezone

class Appraisal(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='appraisals')
    value = models.DecimalField(max_digits=10, decimal_places=2)
    appraiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='appraisals'
    )
    appraisal_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-appraisal_date']
    
    def __str__(self):
        return f"Appraisal for {self.item.name} - Rs: {self.value}"

class InventoryAudit(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='audits')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='inventory_audits'
    )
    action = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Audit for {self.item.name} - {self.action}"


class VaultPouch(models.Model):
    """Physical tamper-proof security pouch for pledged gold custody (Muthoot / Manappuram standard)"""
    STATUS_CHOICES = (
        ('pending_inward', 'Pending Dual Inward'),
        ('vaulted', 'Vaulted (Secured in Safe)'),
        ('in_transit', 'In Transit'),
        ('released', 'Released to Customer'),
        ('auctioned', 'Sent for Auction'),
    )

    pouch_number = models.CharField(
        max_length=60,
        unique=True,
        db_index=True,
        help_text="Unique pouch barcode/identifier"
    )
    loan = models.OneToOneField(
        'transactions.Loan',
        on_delete=models.CASCADE,
        related_name='vault_pouch',
        null=True,
        blank=True,
        help_text="Associated loan for this gold pouch"
    )
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.PROTECT,
        related_name='vault_pouches'
    )
    safe_locker_number = models.CharField(
        max_length=100,
        default='Safe-01 / Locker-A1',
        db_index=True,
        help_text="Designated safe and locker compartment"
    )
    shelf_rack_number = models.CharField(
        max_length=100,
        blank=True,
        default='Rack-01 / Tray-A1',
        help_text="Specific rack, tray, or shelf within locker"
    )
    seal_barcode = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Tamper-evident security seal strip barcode number"
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending_inward',
        db_index=True
    )
    gross_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0.000,
        help_text="Total gross weight in grams"
    )
    net_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0.000,
        help_text="Total pure/net gold weight in grams"
    )
    item_count = models.PositiveIntegerField(
        default=1,
        help_text="Total number of ornaments sealed inside"
    )
    custodian_maker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vault_pouches_packed',
        help_text="Staff/Appraiser who packed and sealed the pouch"
    )
    custodian_checker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vault_pouches_verified',
        help_text="Branch Manager / Joint Keyholder who verified & locked into vault"
    )
    sealed_at = models.DateTimeField(default=timezone.now)
    inward_verified_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vault_pouches_released'
    )
    notes = models.TextField(blank=True, help_text="Audit and location notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Vault Pouch'
        verbose_name_plural = 'Vault Pouches'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['branch', 'status']),
            models.Index(fields=['safe_locker_number', 'shelf_rack_number']),
        ]

    def __str__(self):
        return f"Pouch #{self.pouch_number} ({self.get_status_display()}) - {self.branch.name}"

    @property
    def location_display(self):
        loc = self.safe_locker_number
        if self.shelf_rack_number:
            loc += f" [{self.shelf_rack_number}]"
        return loc


class VaultAuditLog(models.Model):
    """Audit trail for pouch verification, safe movements, and periodic physical audits"""
    ACTION_CHOICES = (
        ('sealed', 'Pouch Sealed & Registered'),
        ('inward_verified', 'Dual-Custody Inward Verified'),
        ('location_moved', 'Relocated to New Safe/Rack'),
        ('audit_verified', 'Physical Audit Verified (Count & Weight Match)'),
        ('discrepancy', 'Audit Discrepancy Flagged'),
        ('released', 'Gold Released to Customer'),
        ('auctioned', 'Transferred to Auction Lot'),
    )

    pouch = models.ForeignKey(
        VaultPouch,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='vault_audits_performed'
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vault_audits_verified',
        help_text="Joint keyholder or supervisor witness"
    )
    old_location = models.CharField(max_length=200, blank=True)
    new_location = models.CharField(max_length=200, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Vault Audit Log'
        verbose_name_plural = 'Vault Audit Logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.pouch.pouch_number} - {self.get_action_display()} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

