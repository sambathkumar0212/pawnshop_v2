"""
Permission classes and mixins for role-based access control.
"""
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions

from .models import Role


class BranchManagerRequiredMixin(UserPassesTestMixin):
    """
    Mixin that restricts access to branch managers, regional managers, and admins.
    Used primarily for views managing schemes and branch-specific content.
    """
    def test_func(self):
        user = self.request.user
        
        # Superusers always have access
        if user.is_superuser:
            return True
            
        # Check if user is a branch manager
        if hasattr(user, 'role') and user.role:
            if user.role.role_type == Role.BRANCH_MANAGER:
                return True
            
        # Check if user is a regional manager
        if hasattr(user, 'role') and user.role:
            if user.role.role_type == Role.REGIONAL_MANAGER:
                return True
                
        return False


class RoleRequiredMixin(UserPassesTestMixin):
    """
    Mixin that restricts access based on user role.
    """
    required_role = None  # Role type required to access the view
    allow_management = True  # Allow management roles (branch manager, regional manager, superuser)
    
    def test_func(self):
        user = self.request.user
        
        # Superusers always have access
        if user.is_superuser:
            return True
            
        # Check role-based permissions
        if self.required_role:
            # User must have the required role
            if user.role and user.role.role_type == self.required_role:
                return True
                
            # Check if management can access and user is a manager
            if self.allow_management:
                if (user.role and (
                    user.role.role_type == Role.BRANCH_MANAGER or
                    user.role.role_type == Role.REGIONAL_MANAGER
                )):
                    return True
        
        return False


class BranchRestrictedMixin(UserPassesTestMixin):
    """
    Mixin that restricts access to a user's branch only.
    Requires object to have a branch attribute.
    """
    def test_func(self):
        user = self.request.user
        obj = self.get_object()
        
        # Superusers always have access
        if user.is_superuser:
            return True
            
        # Regional managers have access to branches in their regions
        if user.is_regional_manager:
            # Check if the object's branch is in the user's managed regions
            if hasattr(obj, 'branch') and obj.branch:
                return obj.branch.region in user.regions.all()
                
        # Branch managers only have access to their own branch
        if user.is_branch_manager:
            if hasattr(obj, 'branch'):
                return obj.branch == user.branch
                
        # Regular staff only have access to their own branch
        if hasattr(obj, 'branch'):
            return obj.branch == user.branch
            
        return False


# DRF Permission Classes
class IsBranchManagerOrAdmin(permissions.BasePermission):
    """
    Permission class for DRF that restricts access to branch managers
    and administrators only.
    """
    def has_permission(self, request, view):
        user = request.user
        
        # Superusers always have permission
        if user.is_superuser:
            return True
            
        # Branch managers have permission
        if user.is_branch_manager:
            return True
            
        # Regional managers have permission
        if user.is_regional_manager:
            return True
            
        return False
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Superusers always have permission
        if user.is_superuser:
            return True
            
        # Check if object has a branch attribute
        if hasattr(obj, 'branch'):
            # Branch managers can only modify objects in their branch
            if user.is_branch_manager:
                return obj.branch == user.branch
                
            # Regional managers can modify objects in their regions
            if user.is_regional_manager:
                return obj.branch.region in user.regions.all()
        
        return False


class IsRegionalManagerOrAdmin(permissions.BasePermission):
    """
    Permission class for DRF that restricts access to regional managers
    and administrators only.
    """
    def has_permission(self, request, view):
        user = request.user
        return user.is_superuser or user.is_regional_manager
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Superusers always have permission
        if user.is_superuser:
            return True
            
        # Regional managers have permission for their regions
        if user.is_regional_manager:
            if hasattr(obj, 'region'):
                return obj.region in user.regions.all()
            elif hasattr(obj, 'branch') and obj.branch and obj.branch.region:
                return obj.branch.region in user.regions.all()
                
        return False


class IsFrontlineStaff(permissions.BasePermission):
    """
    Permission class for DRF that grants read-only access to frontline staff,
    but allows create access for loans and payments.
    """
    def has_permission(self, request, view):
        user = request.user
        
        # Check if user has a frontline role
        is_frontline = user.role and user.role.category == Role.FRONTLINE
        
        # Read permissions are allowed for all staff
        if request.method in permissions.SAFE_METHODS:
            return user.is_authenticated
            
        # Write permissions for frontline staff depend on the view
        if is_frontline:
            # Allow creating transactions
            if 'loan' in view.__class__.__name__.lower() and request.method == 'POST':
                return True
            if 'payment' in view.__class__.__name__.lower() and request.method == 'POST':
                return True
                
        # Deny other write operations
        return False
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Read permissions are allowed for all staff
        if request.method in permissions.SAFE_METHODS:
            # Restrict to user's branch
            if hasattr(obj, 'branch'):
                return obj.branch == user.branch
                
        # Deny write operations on existing objects
        return False


def get_role_permissions():
    """
    Returns a dictionary mapping role types to lists of permission codenames.
    Use this to set up default permissions for each role.
    """
    permissions = {
        # Management Roles
        Role.BRANCH_MANAGER: [
            # User management
            'view_customuser', 'add_customuser', 'change_customuser',
            # Branch management
            'view_branch', 'change_branch', 
            'view_branchsettings', 'change_branchsettings',
            # Customer management
            'view_customer', 'add_customer', 'change_customer', 'delete_customer',
            # Inventory management
            'view_item', 'add_item', 'change_item', 'delete_item',
            # Loan management
            'view_loan', 'add_loan', 'change_loan', 'approve_loan', 'reject_loan',
            # Payment management
            'view_payment', 'add_payment', 'change_payment',
            # Reporting
            'view_report',
        ],
        
        Role.REGIONAL_MANAGER: [
            # User management
            'view_customuser', 'add_customuser', 'change_customuser', 'delete_customuser',
            # Branch management
            'view_branch', 'add_branch', 'change_branch',
            'view_branchsettings', 'change_branchsettings',
            # Region management
            'view_region', 'add_region', 'change_region',
            # Customer management
            'view_customer', 'add_customer', 'change_customer', 'delete_customer',
            # Inventory management
            'view_item', 'add_item', 'change_item', 'delete_item', 'transfer_item',
            # Loan management
            'view_loan', 'add_loan', 'change_loan', 'approve_loan', 'reject_loan',
            # Payment management
            'view_payment', 'add_payment', 'change_payment',
            # Reporting
            'view_report', 'add_report', 'change_report',
        ],
        
        # Front-Line Staff
        Role.LOAN_OFFICER: [
            # Customer management
            'view_customer', 'add_customer',
            # Loan management
            'view_loan', 'add_loan', 'change_loan',
            # Limited item management
            'view_item', 'add_item',
            # Payment management
            'view_payment', 'add_payment',
        ],
        
        Role.APPRAISER: [
            # Item management
            'view_item', 'add_item', 'change_item',
            # Inventory management
            'view_inventory', 'change_inventory',
            # Limited loan access
            'view_loan',
        ],
        
        Role.CASHIER: [
            # Customer management
            'view_customer',
            # Payment management
            'view_payment', 'add_payment',
            # Limited loan access
            'view_loan',
        ],
        
        # Support Roles
        Role.SECURITY: [
            # Limited access for security
            'view_customer',
            'view_branch',
            'view_inventory',
        ],
        
        Role.INVENTORY_MANAGER: [
            # Inventory management
            'view_item', 'add_item', 'change_item', 'delete_item',
            'view_inventory', 'change_inventory',
            # Limited loan access
            'view_loan',
        ],
        
        Role.CUSTOMER_SERVICE: [
            # Customer management
            'view_customer', 'add_customer', 'change_customer',
            # Limited loan and payment access
            'view_loan',
            'view_payment',
        ],
        
        # Head Office Roles
        Role.IT_ADMIN: [
            # System management
            'view_customuser', 'add_customuser', 'change_customuser', 'delete_customuser',
            'view_branch', 'add_branch', 'change_branch',
            'view_branchsettings', 'add_branchsettings', 'change_branchsettings',
            # Limited data access
            'view_customer',
            'view_loan',
            'view_payment',
            'view_item',
        ],
        
        Role.FINANCE_MANAGER: [
            # Financial management
            'view_payment', 'add_payment', 'change_payment',
            'view_loan', 'change_loan',
            # Reporting
            'view_report', 'add_report', 'change_report', 'delete_report',
            # Data access
            'view_customer',
            'view_branch',
            'view_item',
        ],
        
        Role.COMPLIANCE_OFFICER: [
            # Compliance management
            'view_customuser', 'view_customer', 'view_loan', 'view_payment', 'view_item',
            'view_branch', 'view_report',
            # Auditing
            'view_useractivity',
        ],
    }
    
    return permissions