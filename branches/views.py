from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.http import HttpResponse
import csv

from .models import Branch, BranchSettings
from .forms import BranchForm, BranchSettingsForm


class BranchListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Branch
    template_name = 'branches/branch_list.html'
    context_object_name = 'branches'
    permission_required = 'branches.view_branch'
    paginate_by = 15
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by organization if user belongs to one
        user = self.request.user
        if user.organization:
            queryset = queryset.filter(organization=user.organization)
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(address__icontains=search) |
                Q(city__icontains=search) |
                Q(state__icontains=search)
            )
        
        # Status filter
        status = self.request.GET.get('status')
        if status:
            is_active = status == 'active'
            queryset = queryset.filter(is_active=is_active)
        
        # Annotate with statistics - use different names to avoid property conflicts
        queryset = queryset.annotate(
            staff_count_annotated=Count('staff', distinct=True),
            inventory_count_annotated=Count('items', distinct=True),
            active_loans_annotated=Count('loans', filter=Q(loans__status='active'), distinct=True)
        )
        
        # Sorting
        sort_by = self.request.GET.get('sort', 'name')  # Default sort by name
        valid_sort_fields = {
            'name': 'name',
            '-name': '-name',
            'city': 'city',
            '-city': '-city',
            'state': 'state',
            '-state': '-state',
            'staff_count': 'staff_count_annotated',
            '-staff_count': '-staff_count_annotated',
            'inventory_count': 'inventory_count_annotated',
            '-inventory_count': '-inventory_count_annotated',
            'active_loans': 'active_loans_annotated',
            '-active_loans': '-active_loans_annotated',
            'created_at': 'created_at',
            '-created_at': '-created_at',
        }
        
        if sort_by in valid_sort_fields:
            queryset = queryset.order_by(valid_sort_fields[sort_by])
        else:
            queryset = queryset.order_by('name')  # Default fallback
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['current_sort'] = self.request.GET.get('sort', 'name')
        return context
    
    def get(self, request, *args, **kwargs):
        if request.GET.get('download') == 'csv':
            return self.download_csv()
        return super().get(request, *args, **kwargs)
    
    def download_csv(self):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="branches.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Address', 'City', 'State', 'ZIP Code', 'Phone', 'Email',
            'Manager', 'Staff Count', 'Inventory Count', 'Active Loans', 'Status',
            'Created Date'
        ])
        
        queryset = self.get_queryset()
        for branch in queryset:
            writer.writerow([
                branch.name,
                branch.address,
                branch.city,
                branch.state,
                branch.zip_code,
                branch.phone or '',
                branch.email or '',
                branch.manager.get_full_name() if branch.manager else '',
                getattr(branch, 'staff_count_annotated', 0),
                getattr(branch, 'inventory_count_annotated', 0),
                getattr(branch, 'active_loans_annotated', 0),
                'Active' if branch.is_active else 'Inactive',
                branch.created_at.strftime('%Y-%m-%d %H:%M:%S') if branch.created_at else ''
            ])
        
        return response


class BranchDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Branch
    template_name = 'branches/branch_detail.html'
    context_object_name = 'branch'
    permission_required = 'branches.view_branch'
    
    def get_object(self, queryset=None):
        """Override to check organization-based access permissions"""
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        
        # Users can only access branches from their organization
        if user.organization and obj.organization != user.organization:
            from django.http import Http404
            raise Http404("You don't have permission to view this branch.")
        
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        branch = self.object
        today = timezone.now().date()
        current_month = timezone.now().month
        
        # Get staff counts
        context['staff_count'] = branch.staff.count()
        
        # Get inventory statistics
        context['inventory_count'] = branch.items.count()
        context['available_items'] = branch.items.filter(status='available').count()
        context['pawned_items'] = branch.items.filter(status='pawned').count()
        
        # Get loan statistics
        context['active_loans'] = branch.loans.filter(status='active').count()
        context['overdue_loans'] = branch.loans.filter(status='active', due_date__lt=today).count()
        
        # Get sales statistics
        context['sales_this_month'] = branch.sales.filter(
            sale_date__month=current_month
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Get settings
        try:
            context['settings'] = branch.settings
        except BranchSettings.DoesNotExist:
            context['settings'] = None
        
        return context


class BranchCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Branch
    template_name = 'branches/branch_form.html'
    form_class = BranchForm
    permission_required = 'branches.add_branch'
    success_url = reverse_lazy('branch_list')
    
    def form_valid(self, form):
        # Assign the branch to the user's organization
        if self.request.user.organization:
            form.instance.organization = self.request.user.organization
            
        response = super().form_valid(form)
        messages.success(self.request, f'Branch {form.instance.name} has been created successfully.')
        
        # Create default branch settings
        BranchSettings.objects.create(
            branch=form.instance,
            max_loan_amount=5000.00,
            default_interest_rate=0.10,
            loan_duration_days=30
        )
        
        return response


class BranchUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Branch
    template_name = 'branches/branch_form.html'
    form_class = BranchForm
    permission_required = 'branches.change_branch'
    success_url = reverse_lazy('branch_list')
    
    def get_object(self, queryset=None):
        """Override to check organization-based access permissions"""
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        
        # Users can only access branches from their organization
        if user.organization and obj.organization != user.organization:
            from django.http import Http404
            raise Http404("You don't have permission to edit this branch.")
        
        return obj
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Branch {form.instance.name} has been updated successfully.')
        return response


class BranchDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Branch
    template_name = 'branches/branch_confirm_delete.html'
    context_object_name = 'branch'
    permission_required = 'branches.delete_branch'
    success_url = reverse_lazy('branch_list')
    
    def get_object(self, queryset=None):
        """Override to check organization-based access permissions"""
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        
        # Users can only access branches from their organization
        if user.organization and obj.organization != user.organization:
            from django.http import Http404
            raise Http404("You don't have permission to delete this branch.")
        
        return obj
    
    def delete(self, request, *args, **kwargs):
        branch = self.get_object()
        messages.success(request, f'Branch {branch.name} has been deleted successfully.')
        return super().delete(request, *args, **kwargs)


class BranchSettingsUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = BranchSettings
    template_name = 'branches/branch_settings_form.html'
    form_class = BranchSettingsForm
    permission_required = 'branches.change_branchsettings'
    
    def get_object(self, queryset=None):
        branch_id = self.kwargs.get('branch_id')
        # Get the branch and verify organization access
        user = self.request.user
        branch = get_object_or_404(Branch, id=branch_id)
        
        # Check if user has access to this branch's organization
        if user.organization and branch.organization != user.organization:
            from django.http import Http404
            raise Http404("You don't have permission to edit settings for this branch.")
            
        obj, created = BranchSettings.objects.get_or_create(branch=branch)
        return obj
    
    def get_success_url(self):
        return reverse_lazy('branch_detail', kwargs={'pk': self.kwargs.get('branch_id')})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Branch settings have been updated successfully.')
        return response
