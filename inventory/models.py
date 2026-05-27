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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
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

# Add the missing models

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
        return f"Appraisal for {self.item.name} - ₹{self.value}"

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
