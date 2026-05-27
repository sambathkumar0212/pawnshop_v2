from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count

from .models import CustomUser, Role, Region, UserActivity, Customer, Organization


class CustomUserAdmin(UserAdmin):
    """Custom admin for the CustomUser model"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'branch', 'is_staff', 'delete_button')
    list_filter = ('role', 'branch', 'is_staff', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    readonly_fields = ('date_joined', 'last_login', 'face_encoding')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        (_('Role & Branch'), {'fields': ('role', 'branch', 'regions')}),
        (_('Face ID'), {'fields': ('face_id',)}),
        (_('Admin Access'), {'fields': ('is_pawnshop_admin',)}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('date_joined', 'last_login')}),
        (_('Face Encoding Data'), {'fields': ('face_encoding',)}),
    )
    
    filter_horizontal = ('groups', 'user_permissions', 'regions')
    
    class Media:
        js = ('js/admin_password_toggle.js',)
    
    def delete_button(self, obj):
        """Add delete button in list view"""
        if obj.is_superuser:
            return format_html('<span style="color: red;">Cannot delete superuser</span>')
        return format_html(
            '<a class="button button-danger" href="{}" style="background-color: #dc3545;">🗑️ Delete</a>',
            reverse('admin:accounts_customuser_delete', args=[obj.pk])
        )
    delete_button.short_description = 'Action'


class RoleAdmin(admin.ModelAdmin):
    """Admin for Role model"""
    list_display = ('name', 'role_type', 'category')
    list_filter = ('category', 'role_type')
    search_fields = ('name', 'description')
    filter_horizontal = ('permissions',)
    
    def save_model(self, request, obj, form, change):
        """Apply default permissions when new roles are created"""
        from .permissions import get_role_permissions
        
        # Save the model first
        super().save_model(request, obj, form, change)
        
        # Apply default permissions if this is a new role
        if not change:  # If this is a new role
            # Get default permissions for this role type
            default_permissions = get_role_permissions().get(obj.role_type, [])
            
            # If default permissions exist, apply them
            if default_permissions:
                from django.contrib.auth.models import Permission
                from django.contrib.contenttypes.models import ContentType
                
                # Get all permissions with matching codenames
                permissions_to_add = Permission.objects.filter(codename__in=default_permissions)
                
                # Apply these permissions to the role
                obj.permissions.add(*permissions_to_add)


class RegionAdmin(admin.ModelAdmin):
    """Admin for Region model"""
    list_display = ('name', 'branch_count')
    search_fields = ('name', 'description')


class UserActivityAdmin(admin.ModelAdmin):
    """Admin for UserActivity model"""
    list_display = ('user', 'activity_type', 'timestamp', 'ip_address')
    list_filter = ('activity_type', 'timestamp')
    search_fields = ('user__username', 'description')
    readonly_fields = ('user', 'activity_type', 'timestamp', 'description', 'ip_address')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'email', 'branch', 'created_at']
    list_filter = ['branch', 'created_at', 'id_type']
    search_fields = ['first_name', 'last_name', 'phone', 'email', 'id_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('first_name', 'last_name', 'phone', 'email')
        }),
        ('Branch Assignment', {
            'fields': ('branch',),
            'description': 'Each customer must be assigned to a branch.'
        }),
        ('Address Information', {
            'fields': ('address', 'city', 'state', 'zip_code'),
            'classes': ('collapse',)
        }),
        ('Identification', {
            'fields': ('id_type', 'id_number', 'id_image'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'profile_photo', 'face_encoding'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Filter customers based on user's organization and branch"""
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
            
        if hasattr(request.user, 'organization') and request.user.organization:
            # Filter by organization
            qs = qs.filter(branch__organization=request.user.organization)
            
            # Further filter by branch if user is not a regional manager
            if request.user.branch and not (hasattr(request.user, 'role') and 
                request.user.role and request.user.role.name.lower() == 'regional manager'):
                qs = qs.filter(branch=request.user.branch)
                
        return qs
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form to filter branch choices"""
        form = super().get_form(request, obj, **kwargs)
        
        if 'branch' in form.base_fields:
            if request.user.is_superuser:
                # Superusers can see all branches
                form.base_fields['branch'].queryset = Branch.objects.filter(is_active=True)
            elif hasattr(request.user, 'organization') and request.user.organization:
                # Filter branches by organization
                branches_query = Branch.objects.filter(
                    organization=request.user.organization,
                    is_active=True
                )
                
                # Further filter by branch if user is not a regional manager
                if request.user.branch and not (hasattr(request.user, 'role') and 
                    request.user.role and request.user.role.name.lower() == 'regional manager'):
                    branches_query = branches_query.filter(id=request.user.branch.id)
                    
                form.base_fields['branch'].queryset = branches_query
            else:
                # No organization, show active branches
                form.base_fields['branch'].queryset = Branch.objects.filter(is_active=True)
                
        return form
    
    def save_model(self, request, obj, form, change):
        """Set created_by for new customers"""
        if not change:  # New customer
            obj.created_by = request.user
            # If user can only manage one branch, set it automatically
            if (not request.user.is_superuser and request.user.branch and 
                not (hasattr(request.user, 'role') and request.user.role and 
                     request.user.role.name.lower() == 'regional manager')):
                if not obj.branch:
                    obj.branch = request.user.branch
        super().save_model(request, obj, form, change)


class OrganizationAdmin(admin.ModelAdmin):
    """Admin for Organization model with super admin controls"""
    list_display = ('name', 'owner', 'plan', 'status_display', 'total_users', 'total_branches', 'subscription_status', 'created_at', 'organization_actions')
    list_filter = ('status', 'plan', 'created_at', 'subscription_start')
    search_fields = ('name', 'slug', 'owner__username', 'owner__email', 'contact_email')
    readonly_fields = ('slug', 'subscription_start', 'created_at', 'updated_at', 'total_users', 'total_branches', 'total_customers')
    ordering = ['-created_at']
    
    fieldsets = (
        (_('Organization Details'), {
            'fields': ('name', 'slug', 'owner', 'status', 'plan')
        }),
        (_('Contact Information'), {
            'fields': ('contact_email', 'contact_phone')
        }),
        (_('Subscription & Limits'), {
            'fields': ('subscription_start', 'subscription_end', 'auto_renew', 'max_branches', 'max_users', 'max_customers', 'max_loans', 'enable_biometrics')
        }),
        (_('Statistics'), {
            'fields': ('total_users', 'total_branches', 'total_customers'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Only superusers can access organization management"""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            user_count=Count('users', distinct=True),
            branch_count=Count('branches', distinct=True)
        )
    
    def has_module_permission(self, request):
        """Only superusers can access this module"""
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def status_display(self, obj):
        """Display status with color coding"""
        status_colors = {
            'active': 'green',
            'pending': 'orange', 
            'suspended': 'red',
            'cancelled': 'gray'
        }
        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def subscription_status(self, obj):
        """Display subscription status"""
        if obj.is_subscription_active():
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">✗ Inactive</span>')
    subscription_status.short_description = 'Subscription'
    
    def total_users(self, obj):
        """Display total users count"""
        return getattr(obj, 'user_count', obj.total_users)
    total_users.short_description = 'Users'
    
    def total_branches(self, obj):
        """Display total branches count"""
        return getattr(obj, 'branch_count', obj.total_branches)
    total_branches.short_description = 'Branches'
    
    def organization_actions(self, obj):
        """Custom action buttons - renamed from 'actions' to avoid conflict"""
        buttons = []
        
        if obj.status == 'active':
            buttons.append(
                format_html(
                    '<a class="button" href="{}">Suspend</a>',
                    reverse('admin:organization_suspend', args=[obj.pk])
                )
            )
        elif obj.status == 'suspended':
            buttons.append(
                format_html(
                    '<a class="button" href="{}">Reactivate</a>',
                    reverse('admin:organization_reactivate', args=[obj.pk])
                )
            )
        
        buttons.append(
            format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Are you sure you want to delete this organization? This action cannot be undone.\')">Delete</a>',
                reverse('admin:organization_delete', args=[obj.pk])
            )
        )
        
        return format_html(' '.join(buttons))
    organization_actions.short_description = 'Actions'
    
    def get_urls(self):
        """Add custom URLs for organization management"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:organization_id>/suspend/', self.admin_site.admin_view(self.suspend_organization), name='organization_suspend'),
            path('<int:organization_id>/reactivate/', self.admin_site.admin_view(self.reactivate_organization), name='organization_reactivate'),
            path('<int:organization_id>/delete/', self.admin_site.admin_view(self.delete_organization), name='organization_delete'),
        ]
        return custom_urls + urls
    
    def suspend_organization(self, request, organization_id):
        """Suspend an organization"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        organization = get_object_or_404(Organization, id=organization_id)
        organization.status = 'suspended'
        organization.save()
        
        # Deactivate all users in the organization
        organization.users.update(is_active=False)
        
        messages.success(request, f'Organization "{organization.name}" has been suspended.')
        return redirect('admin:accounts_organization_changelist')
    
    def reactivate_organization(self, request, organization_id):
        """Reactivate a suspended organization"""
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        organization = get_object_or_404(Organization, id=organization_id)
        organization.status = 'active'
        organization.save()
        
        # Reactivate all users in the organization
        organization.users.update(is_active=True)
        
        messages.success(request, f'Organization "{organization.name}" has been reactivated.')
        return redirect('admin:accounts_organization_changelist')
    
    def delete_organization(self, request, organization_id):
        """Delete an organization and all related data"""
        from django.shortcuts import get_object_or_404, redirect, render
        from django.contrib import messages
        from django.db import transaction
        
        organization = get_object_or_404(Organization, id=organization_id)
        
        if request.method == 'POST':
            org_name = organization.name
            
            try:
                with transaction.atomic():
                    # Delete all related data in proper order
                    # This will cascade delete users, branches, customers, loans, etc.
                    organization.delete()
                
                messages.success(request, f'Organization "{org_name}" and all related data has been permanently deleted.')
                return redirect('admin:accounts_organization_changelist')
            
            except Exception as e:
                messages.error(request, f'Error deleting organization: {str(e)}')
                return redirect('admin:accounts_organization_changelist')
        
        # Show confirmation page
        context = {
            'organization': organization,
            'title': f'Delete Organization: {organization.name}',
            'opts': self.model._meta,
        }
        return render(request, 'admin/accounts/organization_delete_confirmation.html', context)


class AuditTrailAdmin(admin.ModelAdmin):
    """Admin for AuditTrail model - read-only"""
    list_display = ('admin_user', 'change_type', 'object_str', 'target_user', 'timestamp', 'ip_address')
    list_filter = ('change_type', 'timestamp', 'admin_user')
    search_fields = ('object_str', 'description', 'admin_user__username', 'target_user__username')
    readonly_fields = ('admin_user', 'change_type', 'model_name', 'object_id', 'object_str', 
                      'field_name', 'old_value', 'new_value', 'timestamp', 'ip_address', 
                      'user_agent', 'target_user', 'description')
    
    def has_add_permission(self, request):
        """Disable manual adding of audit entries"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Disable deletion of audit entries"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing of audit entries"""
        return False


class PasswordChangeHistoryAdmin(admin.ModelAdmin):
    """Admin for PasswordChangeHistory model - read-only"""
    list_display = ('user', 'changed_by_admin', 'change_type', 'timestamp', 'ip_address')
    list_filter = ('change_type', 'timestamp', 'changed_by_admin')
    search_fields = ('user__username', 'changed_by_admin__username', 'description')
    readonly_fields = ('user', 'changed_by_admin', 'timestamp', 'change_type', 'ip_address', 'description')
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


class StaffDeletionAdmin(admin.ModelAdmin):
    """Admin for StaffDeletion model - read-only"""
    list_display = ('username', 'email', 'deleted_by_admin', 'deletion_timestamp', 'ip_address')
    list_filter = ('deletion_timestamp', 'deleted_by_admin')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'deleted_by_admin__username')
    readonly_fields = ('staff_user', 'deleted_by_admin', 'username', 'email', 'first_name', 
                      'last_name', 'role_name', 'reason_for_deletion', 'deletion_timestamp', 'ip_address')
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# Register models
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Role, RoleAdmin)
admin.site.register(Region, RegionAdmin)
admin.site.register(UserActivity, UserActivityAdmin)
admin.site.register(Organization, OrganizationAdmin)

# Register audit trail models
from .models import AuditTrail, PasswordChangeHistory, StaffDeletion
admin.site.register(AuditTrail, AuditTrailAdmin)
admin.site.register(PasswordChangeHistory, PasswordChangeHistoryAdmin)
admin.site.register(StaffDeletion, StaffDeletionAdmin)
