from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.contrib.auth.models import Permission


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend that allows users to authenticate
    using either their username or email address, and dynamically evaluates
    permissions assigned via their assigned Custom Role (Role model).
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None

        try:
            users = UserModel.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
            for user in users:
                if user.check_password(password) and self.user_can_authenticate(user):
                    return user
        except Exception:
            return None
        return None

    def get_all_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous:
            return set()
        
        # Superusers have all permissions
        if user_obj.is_superuser:
            return {
                f"{p.content_type.app_label}.{p.codename}"
                for p in Permission.objects.select_related('content_type').all()
            }
        
        # Start with standard user and group permissions
        perms = super().get_all_permissions(user_obj, obj)
        
        # Merge permissions from user's custom Role model
        if hasattr(user_obj, 'role') and user_obj.role:
            try:
                role_permissions = user_obj.role.permissions.select_related('content_type').all()
                for perm in role_permissions:
                    perms.add(f"{perm.content_type.app_label}.{perm.codename}")
            except Exception:
                pass

        # Organization Admins and Pawnshop Admins
        if getattr(user_obj, 'is_organization_admin', False) or getattr(user_obj, 'is_pawnshop_admin', False):
            # Organization admins should have administrative access across business modules
            common_admin_perms = [
                'accounts.view_customer', 'accounts.add_customer', 'accounts.change_customer', 'accounts.delete_customer',
                'accounts.view_customuser', 'accounts.add_customuser', 'accounts.change_customuser',
                'transactions.view_loan', 'transactions.add_loan', 'transactions.change_loan', 'transactions.approve_loan',
                'transactions.view_payment', 'transactions.add_payment', 'transactions.change_payment',
                'inventory.view_item', 'inventory.add_item', 'inventory.change_item',
                'branches.view_branch', 'branches.change_branch',
                'reporting.view_report',
            ]
            perms.update(common_admin_perms)

        return perms

    def has_perm(self, user_obj, perm, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous:
            return False
        if user_obj.is_superuser:
            return True
        return perm in self.get_all_permissions(user_obj, obj)
