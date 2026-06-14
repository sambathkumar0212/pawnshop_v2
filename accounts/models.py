from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
from utils.default_photos import get_default_person_photo
from django.utils import timezone
import uuid
from datetime import timedelta


class Organization(models.Model):
    """Model for managing multi-tenant organizations in SaaS model"""
    PLAN_CHOICES = (
        ('free', 'Free Plan'),
        ('basic', 'Basic Plan'),
        ('professional', 'Professional Plan'),
        ('enterprise', 'Enterprise Plan'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('pending', 'Pending Verification'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
    )
    
    name = models.CharField(max_length=100, help_text="Organization name")
    slug = models.SlugField(unique=True, help_text="URL-friendly identifier")
    owner = models.ForeignKey('accounts.CustomUser', on_delete=models.PROTECT, related_name='owned_organizations')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Contact info
    contact_email = models.EmailField(help_text="Primary contact email")
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Subscription details
    subscription_start = models.DateTimeField(auto_now_add=True)
    subscription_end = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True, help_text="Whether subscription should automatically renew")
    
    # Limits based on plan
    max_branches = models.PositiveIntegerField(default=1)
    max_users = models.PositiveIntegerField(default=3)
    max_customers = models.PositiveIntegerField(default=100)
    max_loans = models.PositiveIntegerField(default=100)
    enable_biometrics = models.BooleanField(default=False)
    
    # Utility fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def is_subscription_active(self):
        """Check if subscription is active"""
        if self.plan == 'free':
            return True
        if not self.subscription_end:
            return False
        return timezone.now() < self.subscription_end
    
    def extend_subscription(self, months=1):
        """Extend subscription by specified months"""
        if not self.subscription_end or self.subscription_end < timezone.now():
            self.subscription_end = timezone.now() + timedelta(days=30*months)
        else:
            self.subscription_end = self.subscription_end + timedelta(days=30*months)
        self.save()
    
    @property
    def total_branches(self):
        """Count total branches in organization"""
        return self.branches.count()
    
    @property
    def total_users(self):
        """Count total users in organization"""
        return self.users.count()
    
    @property
    def total_customers(self):
        """Count total customers in organization"""
        return Customer.objects.filter(branch__organization=self).count()


class Role(models.Model):
    """Custom role model for user permissions"""
    # Role Categories
    MANAGEMENT = 'management'
    FRONTLINE = 'frontline'
    SUPPORT = 'support'
    HEADOFFICE = 'headoffice'
    
    ROLE_CATEGORY_CHOICES = [
        (MANAGEMENT, _('Management')),
        (FRONTLINE, _('Front-Line Staff')),
        (SUPPORT, _('Support')),
        (HEADOFFICE, _('Head Office')),
    ]
    
    # Specific Role Types
    BRANCH_MANAGER = 'branch_manager'
    REGIONAL_MANAGER = 'regional_manager'
    LOAN_OFFICER = 'loan_officer'
    APPRAISER = 'appraiser'
    CASHIER = 'cashier'
    SECURITY = 'security'
    INVENTORY_MANAGER = 'inventory_manager'
    CUSTOMER_SERVICE = 'customer_service'
    IT_ADMIN = 'it_admin'
    FINANCE_MANAGER = 'finance_manager'
    COMPLIANCE_OFFICER = 'compliance_officer'
    
    ROLE_TYPE_CHOICES = [
        (BRANCH_MANAGER, _('Branch Manager')),
        (REGIONAL_MANAGER, _('Regional Manager')),
        (LOAN_OFFICER, _('Loan Officer/Pawnbroker')),
        (APPRAISER, _('Appraiser/Valuation Expert')),
        (CASHIER, _('Cashier/Teller')),
        (SECURITY, _('Security Personnel')),
        (INVENTORY_MANAGER, _('Inventory Manager')),
        (CUSTOMER_SERVICE, _('Customer Service Representative')),
        (IT_ADMIN, _('IT Administrator')),
        (FINANCE_MANAGER, _('Finance/Accounting Manager')),
        (COMPLIANCE_OFFICER, _('Compliance Officer')),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    role_type = models.CharField(max_length=30, choices=ROLE_TYPE_CHOICES, default=CASHIER)
    category = models.CharField(max_length=20, choices=ROLE_CATEGORY_CHOICES, default=FRONTLINE)
    description = models.TextField(blank=True, null=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    
    class Meta:
        verbose_name = _('role')
        verbose_name_plural = _('roles')
        
    def __str__(self):
        return self.name
    
    def get_permission_groups(self):
        """Returns permissions grouped by app label"""
        from django.contrib.contenttypes.models import ContentType
        from itertools import groupby
        from operator import attrgetter
        
        permissions = self.permissions.select_related('content_type').order_by('content_type__app_label')
        return {
            app_label: list(perms)
            for app_label, perms in groupby(permissions, key=lambda p: p.content_type.app_label)
        }
    
    def has_permission(self, perm_codename):
        """Check if role has a specific permission"""
        return self.permissions.filter(codename=perm_codename).exists()
    
    def add_permissions(self, *codenames):
        """Add multiple permissions by codename"""
        from django.contrib.auth.models import Permission
        perms = Permission.objects.filter(codename__in=codenames)
        self.permissions.add(*perms)
    
    def remove_permissions(self, *codenames):
        """Remove multiple permissions by codename"""
        from django.contrib.auth.models import Permission
        perms = Permission.objects.filter(codename__in=codenames)
        self.permissions.remove(*perms)
    
    def apply_default_permissions(self):
        """Apply default permissions for this role type"""
        from .permissions import get_role_permissions
        
        # Get the default permissions for this role type
        role_permissions = get_role_permissions()
        if self.role_type in role_permissions:
            # Get permission objects for the codenames
            from django.contrib.auth.models import Permission
            perm_codenames = role_permissions[self.role_type]
            permissions = Permission.objects.filter(codename__in=perm_codenames)
            
            # Assign permissions to the role
            self.permissions.set(permissions)


# Signal handler to automatically apply default permissions when a role is created or updated
@receiver(post_save, sender=Role)
def set_default_permissions(sender, instance, created, **kwargs):
    """Set default permissions when a role is created or updated"""
    # We need to use post_save because ManyToManyField can only be modified after the instance is saved
    instance.apply_default_permissions()

class Region(models.Model):
    """Region model for grouping branches"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    @property
    def branch_count(self):
        return self.branches.count()


class CustomUser(AbstractUser):
    """Custom user model extending Django's AbstractUser"""
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    
    phone = models.CharField(max_length=20, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    branch = models.ForeignKey('branches.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff')
    regions = models.ManyToManyField(Region, blank=True, related_name='managers')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    face_id = models.BooleanField(default=False, help_text=_('Whether face ID is enabled for this user'))
    face_encoding = models.BinaryField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    # For SaaS plans
    is_organization_admin = models.BooleanField(default=False, help_text=_('Whether user is an admin for their organization'))
    # Admin-only access
    is_pawnshop_admin = models.BooleanField(default=False, help_text=_('Whether user is a pawnshop admin (only admin can manage staff)'))
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"
    
    def save(self, *args, **kwargs):
        # Check if this is a new user (being created for the first time)
        is_new = self.pk is None
        
        # Save the user first
        super().save(*args, **kwargs)
        
        # Set proper permissions based on role
        if self.role:
            self.user_permissions.set(self.role.permissions.all())
        
        # For new users or users without the inventory view permission, add it
        if is_new or not self.has_perm('inventory.view_item'):
            from django.contrib.auth.models import Permission
            from django.contrib.contenttypes.models import ContentType
            from inventory.models import Item
            
            # Get the inventory view permission
            content_type = ContentType.objects.get_for_model(Item)
            view_item_permission = Permission.objects.get(
                content_type=content_type,
                codename='view_item'
            )
            
            # Add the permission to the user
            self.user_permissions.add(view_item_permission)
    
    @property
    def is_regional_manager(self):
        return self.role and self.role.role_type == Role.REGIONAL_MANAGER
    
    @property
    def is_branch_manager(self):
        return self.role and self.role.role_type == Role.BRANCH_MANAGER
    
    @property
    def managed_branches(self):
        """Return branches managed by this user"""
        from branches.models import Branch
        
        if self.is_superuser:
            return Branch.objects.all()
        elif self.is_regional_manager:
            return Branch.objects.filter(region__in=self.regions.all())
        elif self.is_branch_manager and self.branch:
            return Branch.objects.filter(id=self.branch.id)
        return Branch.objects.none()

class UserActivity(models.Model):
    """Track user activity in the system"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    class Meta:
        verbose_name = _('user activity')
        verbose_name_plural = _('user activities')
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.user} - {self.activity_type} - {self.timestamp}"


# Add the Customer model that's referenced in the inventory app
class Customer(models.Model):
    """Model for pawnshop customers"""
    
    # Define ID type choices
    ID_TYPE_CHOICES = [
        ('aadhar_card', 'Aadhar Card'),
        ('pan_card', 'PAN Card'),
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
        ('voter_id', 'Voter ID Card'),
        ('ration_card', 'Ration Card'),
        ('bank_passbook', 'Bank Passbook'),
        ('other', 'Other'),
    ]
    
    first_name = models.CharField(max_length=100)
    first_name_tamil = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    last_name_tamil = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20)
    branch = models.ForeignKey(
        'branches.Branch', 
        on_delete=models.PROTECT, 
        related_name='customers', 
        null=True,
        blank=True,
        help_text="Branch where this customer is registered"
    )
    profile_photo = models.TextField(blank=True, null=True, help_text="Base64-encoded profile photo of customer")
    address = models.TextField(blank=True)
    address_tamil = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    city_tamil = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    state_tamil = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    id_type = models.CharField(
        max_length=50, 
        choices=ID_TYPE_CHOICES,
        default='aadhar_card',
        blank=True, 
        help_text="Type of ID provided"
    )
    id_number = models.CharField(max_length=50, blank=True, help_text="ID document number")
    id_image = models.ImageField(upload_to='customer_ids/', blank=True, null=True)
    face_encoding = models.BinaryField(null=True, blank=True, help_text="Binary data for facial recognition")
    notes = models.TextField(blank=True)
    notes_tamil = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.CustomUser',
        related_name='created_customers',
        on_delete=models.SET_NULL,
        null=True
    )
    
    class Meta:
        verbose_name = _('customer')
        verbose_name_plural = _('customers')
        ordering = ['last_name', 'first_name']
        # Add constraint to ensure branch is always set
        constraints = [
            models.CheckConstraint(
                check=models.Q(branch__isnull=False),
                name='customer_must_have_branch'
            )
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def clean(self):
        """Custom validation to ensure branch is set"""
        from django.core.exceptions import ValidationError
        # Only validate branch requirement if the instance is being saved to database
        # (i.e., not during form instantiation or temporary object creation)
        if self.pk is None and not hasattr(self, '_state') or (hasattr(self, '_state') and self._state.adding):
            # This is a new object being created, branch validation will be handled by the form
            return
        if not self.branch_id:  # Use branch_id instead of branch to avoid RelatedObjectDoesNotExist
            raise ValidationError({'branch': 'Each customer must be assigned to a branch.'})
    
    def save(self, *args, **kwargs):
        """Override save to ensure validation"""
        # Only call clean() if we're updating an existing customer or if branch is already set
        if self.pk or self.branch_id:
            self.clean()
        super().save(*args, **kwargs)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def active_loans_count(self):
        """Return number of active loans for this customer"""
        return self.loans.filter(status='active').count() if hasattr(self, 'loans') else 0

    @property
    def photo(self):
        if self.profile_photo and self.profile_photo.strip():
            photo_value = self.profile_photo.strip()
            # Already a usable image source (sanitize accidental whitespace/newlines).
            if photo_value.startswith('data:image/'):
                header, sep, payload = photo_value.partition(',')
                if sep:
                    payload = ''.join(payload.split())
                    # If payload is PNG but header says JPEG, correct mime.
                    if payload.startswith('iVBOR') and 'image/jpeg' in header:
                        header = header.replace('image/jpeg', 'image/png')
                    return f"{header},{payload}"
                return photo_value
            if photo_value.startswith('/media/') or photo_value.startswith('http://') or photo_value.startswith('https://'):
                return photo_value
            # Raw base64 value without data-uri prefix.
            clean_payload = ''.join(photo_value.split())
            mime = 'image/png' if clean_payload.startswith('iVBOR') else 'image/jpeg'
            return f"data:{mime};base64,{clean_payload}"

        # Fallback: try to pick a photo from this customer's latest loans.
        try:
            from transactions.models import Loan
            from transactions.views import process_item_photos_for_display

            loans = Loan.objects.filter(customer=self).order_by('-created_at')
            for loan in loans:
                if getattr(loan, 'customer_face_capture', None):
                    return loan.customer_face_capture
                photos = process_item_photos_for_display(loan.item_photos)
                if photos:
                    return photos[0]
        except Exception:
            pass

        from utils.default_photos import get_default_person_photo
        return get_default_person_photo()


class AuditTrail(models.Model):
    """Model to track all changes made by admin"""
    CHANGE_TYPE_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('password_change', 'Password Change'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('permission_change', 'Permission Change'),
    ]
    
    # Who made the change
    admin_user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='audit_trails_created')
    
    # What was changed
    change_type = models.CharField(max_length=30, choices=CHANGE_TYPE_CHOICES)
    model_name = models.CharField(max_length=100, help_text="Name of the model that was changed")
    object_id = models.PositiveIntegerField(null=True, blank=True, help_text="ID of the changed object")
    object_str = models.CharField(max_length=500, help_text="String representation of the changed object")
    
    # Field-specific changes
    field_name = models.CharField(max_length=100, blank=True, help_text="Name of the field that was changed")
    old_value = models.TextField(blank=True, null=True, help_text="Old value before change")
    new_value = models.TextField(blank=True, null=True, help_text="New value after change")
    
    # When and where
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True, help_text="IP address from where change was made")
    user_agent = models.CharField(max_length=500, blank=True, help_text="Browser/User Agent information")
    
    # Target user (for staff-related changes)
    target_user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, 
                                    related_name='audit_trails_target')
    
    description = models.TextField(blank=True, help_text="Detailed description of the change")
    
    class Meta:
        verbose_name = _('audit trail')
        verbose_name_plural = _('audit trails')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['admin_user', '-timestamp']),
            models.Index(fields=['target_user', '-timestamp']),
            models.Index(fields=['change_type', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.admin_user} - {self.change_type} - {self.object_str} - {self.timestamp}"


class PasswordChangeHistory(models.Model):
    """Track password changes for staff accounts"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='password_changes')
    changed_by_admin = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, 
                                        related_name='staff_password_changes_made')
    timestamp = models.DateTimeField(auto_now_add=True)
    change_type = models.CharField(
        max_length=20,
        choices=[
            ('admin_reset', 'Admin Reset'),
            ('forgot_password', 'Forgot Password'),
            ('user_change', 'User Changed'),  # Should not happen for staff unless admin allows
        ],
        default='admin_reset'
    )
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    description = models.CharField(max_length=255, blank=True)
    
    class Meta:
        verbose_name = _('password change history')
        verbose_name_plural = _('password change histories')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['changed_by_admin', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.change_type} - {self.timestamp}"


class LoanEditLog(models.Model):
    """Track edits made to Loan objects for history and auditing."""
    CHANGE_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('foreclose', 'Foreclose'),
        ('payment', 'Payment'),
        ('other', 'Other'),
    ]

    loan = models.ForeignKey('transactions.Loan', on_delete=models.CASCADE, related_name='edit_logs')
    edited_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='loan_edits_made')
    edited_at = models.DateTimeField(auto_now_add=True)
    change_type = models.CharField(max_length=20, choices=CHANGE_CHOICES, default='update')
    description = models.TextField(blank=True)
    # Field-level changes stored as JSON: {"field_name": {"old": "...", "new": "..."}, ...}
    changes = models.JSONField(null=True, blank=True, help_text='Field-level old/new values')

    class Meta:
        verbose_name = _('loan edit log')
        verbose_name_plural = _('loan edit logs')
        ordering = ['-edited_at']

    def __str__(self):
        return f"{self.loan} - {self.change_type} by {self.edited_by} at {self.edited_at}"


class StaffDeletion(models.Model):
    """Track deleted staff accounts"""
    staff_user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, 
                                   related_name='deletion_records')
    deleted_by_admin = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, 
                                        related_name='staff_deletions_made')
    deletion_timestamp = models.DateTimeField(auto_now_add=True)
    username = models.CharField(max_length=150)  # Store username of deleted user
    email = models.EmailField()
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role_name = models.CharField(max_length=100, blank=True)
    reason_for_deletion = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    class Meta:
        verbose_name = _('staff deletion')
        verbose_name_plural = _('staff deletions')
        ordering = ['-deletion_timestamp']
        indexes = [
            models.Index(fields=['deleted_by_admin', '-deletion_timestamp']),
            models.Index(fields=['-deletion_timestamp']),
        ]
    
    def __str__(self):
        return f"{self.username} - Deleted by {self.deleted_by_admin} - {self.deletion_timestamp}"
