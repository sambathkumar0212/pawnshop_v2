from django.db.models import Q
from django.http import Http404
from branches.models import Branch


class RoleBranchAccessMixin:
    """Mixin to provide branch/region based access control for views.

    Methods:
    - get_allowed_branches(user) -> QuerySet or None (None means unrestricted)
    - filter_queryset_by_branches(queryset) -> filtered queryset
    - check_object_branch_access(obj) -> raises Http404 if not allowed
    """

    def get_allowed_branches(self, user):
        # Superusers and pawnshop admins have full access
        if not user.is_authenticated:
            return Branch.objects.none()
        if user.is_superuser or getattr(user, 'is_pawnshop_admin', False):
            return None

        # Regional managers: access to branches in their regions
        if getattr(user, 'is_regional_manager', False):
            regions = user.regions.all()
            return Branch.objects.filter(region__in=regions, is_active=True)

        # Branch managers or regular users assigned to a branch: only their branch
        # Allow access to the user's assigned branch even if branch.is_active is False
        if getattr(user, 'branch', None):
            return Branch.objects.filter(pk=user.branch.pk)

        # Users without branch or region have no access to branch-scoped data
        return Branch.objects.none()

    def filter_queryset_by_branches(self, queryset, branch_field_name='branch'):
        """Filter queryset by allowed branches.

        If get_allowed_branches returns None, returns queryset unchanged.
        branch_field_name can be 'branch' or a related lookup like 'branch__id'.
        """
        user = getattr(self.request, 'user', None)
        allowed = self.get_allowed_branches(user)
        if allowed is None:
            return queryset
        # If no allowed branches, return empty queryset
        if not allowed.exists():
            return queryset.none()

        # Apply filter depending on model relation
        lookup = {f"{branch_field_name}__in": allowed}
        return queryset.filter(**lookup)

    def check_object_branch_access(self, obj, branch_attr='branch'):
        """Ensure object belongs to an allowed branch. Raise Http404 if not."""
        user = getattr(self.request, 'user', None)
        allowed = self.get_allowed_branches(user)
        if allowed is None:
            return True
        # If object has no branch attribute, deny
        branch = getattr(obj, branch_attr, None)
        if branch is None:
            raise Http404()
        if not allowed.filter(pk=branch.pk).exists():
            raise Http404()
        return True
