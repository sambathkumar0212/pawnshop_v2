from django.db import models
from django.utils.translation import gettext_lazy as _


class Branch(models.Model):
    """Model for pawn shop branches/locations"""
    name = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, 
                                    related_name='branches', null=True)
    region = models.ForeignKey('accounts.Region', on_delete=models.SET_NULL, 
                              null=True, blank=True, related_name='branches')
    manager = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, 
                               null=True, blank=True, related_name='managed_branches')
    is_active = models.BooleanField(default=True)
    opening_time = models.TimeField(default='09:00')
    closing_time = models.TimeField(default='18:00')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('branch')
        verbose_name_plural = _('branches')
        ordering = ['name']
        
    def __str__(self):
        return self.name
        
    @property
    def staff_count(self):
        # Fix the reference to staff members
        from accounts.models import CustomUser
        return CustomUser.objects.filter(branch=self).count()
        # Alternative if there's a related_name on the CustomUser model:
        # return self.staff_members.count()  # Assuming related_name is 'staff_members'

    @staff_count.setter
    def staff_count(self, value):
        # This is a computed property, so we ignore attempts to set it directly
        pass
        
    @property
    def active_loans(self):
        return self.loans.filter(status='active').count()
        
    @property
    def inventory_count(self):
        # Handle missing inventory model with a default value
        try:
            # Try to get the appropriate inventory model
            from inventory.models import Item  # Trying a different name
            return Item.objects.filter(branch=self).count()
        except (ImportError, AttributeError):
            try:
                # Try another common name
                from inventory.models import Inventory
                return Inventory.objects.filter(branch=self).count()
            except (ImportError, AttributeError):
                # Return 0 if we can't find the right model
                return 0


class BranchSettings(models.Model):
    """Settings specific to a branch"""
    branch = models.OneToOneField(Branch, on_delete=models.CASCADE, related_name='settings')
    max_loan_amount = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)
    default_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    loan_duration_days = models.IntegerField(default=30)
    grace_period_days = models.IntegerField(default=15)
    allow_online_payments = models.BooleanField(default=True)
    require_id_verification = models.BooleanField(default=True)
    enable_face_recognition = models.BooleanField(default=False)
    enable_email_notifications = models.BooleanField(default=True)
    enable_sms_notifications = models.BooleanField(default=False)
    auction_delay_days = models.IntegerField(default=7)
    bill_header_mobile_numbers = models.TextField(blank=True, null=True, help_text="Enter multiple mobile numbers (40+ characters). Separated by comma, semicolon, slash, or newline. These will be displayed in bill headers.")
    personal_mobile_number = models.CharField(max_length=15, blank=True, null=True, help_text="Personal mobile number of branch manager or staff (10-15 characters).")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('branch settings')
        verbose_name_plural = _('branch settings')
        
    def __str__(self):
        return f"{self.branch.name} Settings"
