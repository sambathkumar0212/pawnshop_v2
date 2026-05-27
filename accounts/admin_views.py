"""
Admin-only views for managing staff accounts and viewing audit trails
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
from datetime import timedelta
import string
import random

from .models import CustomUser, AuditTrail, PasswordChangeHistory, StaffDeletion, Role
from .audit import (
    log_staff_creation, log_staff_update, log_staff_deletion, 
    log_permission_change, log_password_change, get_request_info
)
from .forms import UserFaceCreateForm, UserUpdateForm

UserModel = get_user_model()


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure user is a pawnshop admin"""
    
    def test_func(self):
        return self.request.user.is_pawnshop_admin
    
    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to access this page. Admin access required.")
        return redirect('home')


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """Admin dashboard showing overview of staff and recent activities"""
    template_name = 'accounts/admin/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Count statistics
        context['total_staff'] = CustomUser.objects.filter(is_pawnshop_admin=False).count()
        context['admins_count'] = CustomUser.objects.filter(is_pawnshop_admin=True).count()
        context['active_staff'] = CustomUser.objects.filter(is_pawnshop_admin=False, is_active=True).count()
        context['inactive_staff'] = CustomUser.objects.filter(is_pawnshop_admin=False, is_active=False).count()
        
        # Recent activities
        context['recent_audits'] = AuditTrail.objects.select_related(
            'admin_user', 'target_user'
        ).order_by('-timestamp')[:10]
        
        context['recent_deletions'] = StaffDeletion.objects.select_related(
            'deleted_by_admin'
        ).order_by('-deletion_timestamp')[:5]
        
        # Password changes in last 7 days
        seven_days_ago = timezone.now() - timedelta(days=7)
        context['recent_password_changes'] = PasswordChangeHistory.objects.filter(
            timestamp__gte=seven_days_ago
        ).select_related('user', 'changed_by_admin').order_by('-timestamp')[:5]
        
        return context


class StaffListView(AdminRequiredMixin, ListView):
    """List all staff users (non-admin)"""
    model = CustomUser
    template_name = 'accounts/admin/staff_list.html'
    context_object_name = 'staff_list'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = CustomUser.objects.filter(
            is_pawnshop_admin=False
        ).select_related('role', 'branch').order_by('-date_joined')
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )
        
        # Filter by active status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Filter by role
        role_id = self.request.GET.get('role')
        if role_id:
            queryset = queryset.filter(role_id=role_id)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = Role.objects.all()
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['role_filter'] = self.request.GET.get('role', '')
        return context


class StaffDetailView(AdminRequiredMixin, DetailView):
    """Show detailed information about a staff member"""
    model = CustomUser
    template_name = 'accounts/admin/staff_detail.html'
    context_object_name = 'staff_user'
    
    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        user = get_object_or_404(CustomUser, pk=pk, is_pawnshop_admin=False)
        return user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        staff_user = self.object
        
        # Audit trails for this staff
        context['audit_trails'] = AuditTrail.objects.filter(
            Q(target_user=staff_user) | Q(admin_user=staff_user)
        ).select_related('admin_user').order_by('-timestamp')[:20]
        
        # Password change history
        context['password_changes'] = PasswordChangeHistory.objects.filter(
            user=staff_user
        ).select_related('changed_by_admin').order_by('-timestamp')[:10]
        
        return context


class StaffCreateView(AdminRequiredMixin, CreateView):
    """Create a new staff account (admin only)"""
    model = CustomUser
    template_name = 'accounts/admin/staff_form.html'
    fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'role', 'branch', 'is_active']
    success_url = reverse_lazy('admin_staff_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        staff_user = self.object
        
        # Generate a temporary password
        temp_password = self.generate_temp_password()
        staff_user.set_password(temp_password)
        staff_user.save()
        
        # Log staff creation
        request_info = get_request_info(self.request)
        log_staff_creation(
            admin_user=self.request.user,
            staff_user=staff_user,
            request=self.request,
            description=f"Created staff account: {staff_user.get_full_name()} (Username: {staff_user.username})"
        )
        
        # Log password creation
        log_password_change(
            user=staff_user,
            changed_by_admin=self.request.user,
            change_type='admin_reset',
            ip_address=request_info.get('ip_address'),
            description=f"Initial password set during account creation"
        )
        
        messages.success(self.request, f"Staff account created successfully for {staff_user.get_full_name()}.")
        messages.info(self.request, f"Temporary password: {temp_password} (Please share securely)")
        
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Staff Account'
        return context
    
    @staticmethod
    def generate_temp_password(length=12):
        """Generate a secure temporary password"""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(random.choice(characters) for _ in range(length))


class StaffUpdateView(AdminRequiredMixin, UpdateView):
    """Update staff account details (admin only)"""
    model = CustomUser
    template_name = 'accounts/admin/staff_form.html'
    fields = ['email', 'first_name', 'last_name', 'phone', 'role', 'branch', 'is_active']
    success_url = reverse_lazy('admin_staff_list')
    
    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        return get_object_or_404(CustomUser, pk=pk, is_pawnshop_admin=False)
    
    def form_valid(self, form):
        staff_user = self.object
        old_data = CustomUser.objects.get(pk=staff_user.pk)
        
        # Track changes
        changes = {}
        for field in form.changed_data:
            old_value = getattr(old_data, field)
            new_value = getattr(staff_user, field)
            if old_value != new_value:
                changes[field] = (old_value, new_value)
        
        response = super().form_valid(form)
        
        # Log changes if any
        if changes:
            request_info = get_request_info(self.request)
            for field, (old_val, new_val) in changes.items():
                AuditTrail.objects.create(
                    admin_user=self.request.user,
                    change_type='update',
                    model_name='CustomUser',
                    object_id=staff_user.id,
                    object_str=str(staff_user),
                    field_name=field,
                    old_value=str(old_val),
                    new_value=str(new_val),
                    target_user=staff_user,
                    ip_address=request_info.get('ip_address'),
                    user_agent=request_info.get('user_agent'),
                    description=f"Updated {field} for {staff_user.get_full_name()}"
                )
            
            messages.success(self.request, f"Staff account updated successfully.")
        else:
            messages.info(self.request, "No changes were made.")
        
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Update {self.object.get_full_name()}'
        return context


class ResetStaffPasswordView(AdminRequiredMixin, View):
    """Reset a staff member's password (admin only)"""
    
    def post(self, request, pk):
        staff_user = get_object_or_404(CustomUser, pk=pk, is_pawnshop_admin=False)
        
        # Generate new temporary password
        temp_password = StaffCreateView.generate_temp_password()
        staff_user.set_password(temp_password)
        staff_user.save()
        
        # Log password change
        request_info = get_request_info(request)
        log_password_change(
            user=staff_user,
            changed_by_admin=request.user,
            change_type='admin_reset',
            ip_address=request_info.get('ip_address'),
            description=f"Password reset by admin"
        )
        
        messages.success(request, f"Password reset successfully for {staff_user.get_full_name()}.")
        messages.info(request, f"New temporary password: {temp_password} (Please share securely)")
        
        return redirect('admin_staff_detail', pk=pk)


class DeleteStaffView(AdminRequiredMixin, DeleteView):
    """Delete a staff account (admin only)"""
    model = CustomUser
    template_name = 'accounts/admin/staff_confirm_delete.html'
    success_url = reverse_lazy('admin_staff_list')
    
    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        return get_object_or_404(CustomUser, pk=pk, is_pawnshop_admin=False)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_user'] = self.object
        return context
    
    def delete(self, request, *args, **kwargs):
        staff_user = self.get_object()
        reason = request.POST.get('reason_for_deletion', '')
        
        # Log staff deletion
        request_info = get_request_info(request)
        log_staff_deletion(
            admin_user=request.user,
            staff_user=staff_user,
            reason=reason,
            request=request
        )
        
        messages.success(request, f"Staff account {staff_user.get_full_name()} has been deleted successfully.")
        
        return super().delete(request, *args, **kwargs)


class AuditTrailView(AdminRequiredMixin, ListView):
    """View audit trail/activity log"""
    model = AuditTrail
    template_name = 'accounts/admin/audit_trail.html'
    context_object_name = 'audit_trails'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = AuditTrail.objects.select_related(
            'admin_user', 'target_user'
        ).order_by('-timestamp')
        
        # Filter by change type
        change_type = self.request.GET.get('change_type')
        if change_type:
            queryset = queryset.filter(change_type=change_type)
        
        # Filter by admin user
        admin_id = self.request.GET.get('admin_id')
        if admin_id:
            queryset = queryset.filter(admin_user_id=admin_id)
        
        # Filter by target user
        target_id = self.request.GET.get('target_id')
        if target_id:
            queryset = queryset.filter(target_user_id=target_id)
        
        # Filter by date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['change_type_choices'] = AuditTrail.CHANGE_TYPE_CHOICES
        context['admin_users'] = CustomUser.objects.filter(is_pawnshop_admin=True)
        context['staff_users'] = CustomUser.objects.filter(is_pawnshop_admin=False)
        context['selected_change_type'] = self.request.GET.get('change_type', '')
        context['selected_admin'] = self.request.GET.get('admin_id', '')
        context['selected_target'] = self.request.GET.get('target_id', '')
        return context


class PasswordChangeHistoryView(AdminRequiredMixin, ListView):
    """View password change history"""
    model = PasswordChangeHistory
    template_name = 'accounts/admin/password_history.html'
    context_object_name = 'password_changes'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = PasswordChangeHistory.objects.select_related(
            'user', 'changed_by_admin'
        ).order_by('-timestamp')
        
        # Filter by staff user
        staff_id = self.request.GET.get('staff_id')
        if staff_id:
            queryset = queryset.filter(user_id=staff_id)
        
        # Filter by change type
        change_type = self.request.GET.get('change_type')
        if change_type:
            queryset = queryset.filter(change_type=change_type)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_users'] = CustomUser.objects.filter(is_pawnshop_admin=False)
        context['change_type_choices'] = PasswordChangeHistory._meta.get_field('change_type').choices
        return context


class StaffDeletionHistoryView(AdminRequiredMixin, ListView):
    """View history of deleted staff accounts"""
    model = StaffDeletion
    template_name = 'accounts/admin/deletion_history.html'
    context_object_name = 'deletions'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = StaffDeletion.objects.select_related(
            'deleted_by_admin'
        ).order_by('-deletion_timestamp')
        
        # Filter by deleting admin
        admin_id = self.request.GET.get('admin_id')
        if admin_id:
            queryset = queryset.filter(deleted_by_admin_id=admin_id)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['admin_users'] = CustomUser.objects.filter(is_pawnshop_admin=True)
        return context
