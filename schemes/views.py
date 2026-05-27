from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, Http404, HttpResponse
from django.db.models import Q
from django.utils import timezone
import decimal
import json
from decimal import Decimal

from .models import Scheme, SchemeAuditLog
from .forms import NewSchemeForm, SchemeForm
from accounts.models import UserActivity

# New implementation with simplified approach
class NewSchemeListView(LoginRequiredMixin, ListView):
    """A simplified view for listing loan schemes"""
    model = Scheme
    template_name = 'schemes/new_scheme_list.html'
    context_object_name = 'schemes'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Scheme.objects.all()
        user = self.request.user
        
        # Filter by user's organization or branch access
        if not user.is_superuser:
            if hasattr(user, 'organization') and user.organization:
                queryset = queryset.filter(
                    Q(branch__organization=user.organization) | 
                    Q(is_default=True)
                )
            elif user.branch:
                queryset = queryset.filter(
                    Q(branch=user.branch) | 
                    Q(branch__isnull=True) |
                    Q(is_default=True)
                )
        
        # Handle search
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Handle status filter
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        # Sorting
        sort_by = self.request.GET.get('sort', 'name')  # Default sort by name
        valid_sort_fields = {
            'name': 'name',
            '-name': '-name',
            'interest_rate': 'interest_rate',
            '-interest_rate': '-interest_rate',
            'loan_duration': 'loan_duration',
            '-loan_duration': '-loan_duration',
            'minimum_amount': 'minimum_amount',
            '-minimum_amount': '-minimum_amount',
            'maximum_amount': 'maximum_amount',
            '-maximum_amount': '-maximum_amount',
            'status': 'status',
            '-status': '-status',
            'created_at': 'created_at',
            '-created_at': '-created_at',
            'branch': 'branch__name',
            '-branch': '-branch__name',
        }
        
        if sort_by in valid_sort_fields:
            queryset = queryset.order_by(valid_sort_fields[sort_by])
        else:
            queryset = queryset.order_by('name')  # Default fallback
            
        return queryset.select_related('branch')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['current_sort'] = self.request.GET.get('sort', 'name')
        context['status_choices'] = Scheme.STATUS_CHOICES
        
        # Log user activity
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='scheme_list_viewed',
            description='Viewed schemes list',
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        
        return context

class NewSchemeCreateView(LoginRequiredMixin, View):
    """A simplified view for creating loan schemes"""
    template_name = 'schemes/new_scheme_form.html'
    
    def get(self, request):
        form = NewSchemeForm(user=request.user)
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = NewSchemeForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                scheme = form.save(commit=False)
                scheme.created_by = request.user
                scheme.updated_by = request.user
                scheme.is_gold_scheme = True
                
                # Auto-set branch for branch managers
                if not scheme.branch and not request.user.is_superuser:
                    if hasattr(request.user, 'role') and request.user.role and request.user.role.name.lower() == 'branch manager' and request.user.branch:
                        scheme.branch = request.user.branch
                
                scheme.save()
                
                # Create audit log
                SchemeAuditLog.objects.create(
                    scheme=scheme,
                    user=request.user,
                    action='created',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                # Log user activity
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='scheme_created',
                    description=f'Created new scheme: {scheme.name}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Scheme "{scheme.name}" was created successfully.')
                return redirect('new_scheme_detail', pk=scheme.pk)
            except Exception as e:
                messages.error(request, f"Error creating scheme: {str(e)}")
                # Log the error for debugging purposes
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Scheme creation error: {str(e)}", exc_info=True)
        else:
            # Add more detailed error messages for field validation issues
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error in {field}: {error}")
        
        return render(request, self.template_name, {'form': form})

class NewSchemeDetailView(LoginRequiredMixin, DetailView):
    """A simplified view for viewing loan scheme details"""
    model = Scheme
    template_name = 'schemes/new_scheme_detail.html'
    context_object_name = 'scheme'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scheme = self.get_object()
        user = self.request.user
        
        # Add audit logs
        context['audit_logs'] = scheme.audit_logs.all().order_by('-timestamp')[:5]
        
        # Check if user can edit or delete
        can_edit = False
        can_delete = False
        
        if user.is_superuser:
            can_edit = True
            can_delete = True
        elif hasattr(user, 'organization') and user.organization and user.organization.owner == user:
            if scheme.branch and scheme.branch.organization == user.organization:
                can_edit = True
                can_delete = True
        elif hasattr(user, 'role') and user.role:
            role_name = user.role.name.lower()
            if role_name == 'branch manager' and user.branch and scheme.branch == user.branch:
                can_edit = True
                can_delete = True
            elif role_name == 'regional manager':
                if hasattr(user, 'managed_branches') and scheme.branch in user.managed_branches.all():
                    can_edit = True
                    can_delete = True
        
        context['can_edit'] = can_edit
        context['can_delete'] = can_delete
        
        # Log user activity
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='scheme_viewed',
            description=f'Viewed scheme: {scheme.name}',
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        
        return context

class NewSchemeUpdateView(LoginRequiredMixin, View):
    """A simplified view for updating loan schemes"""
    template_name = 'schemes/new_scheme_form.html'
    
    def get(self, request, pk):
        scheme = get_object_or_404(Scheme, pk=pk)
        form = NewSchemeForm(instance=scheme, user=request.user)
        return render(request, self.template_name, {'form': form, 'scheme': scheme})
    
    def post(self, request, pk):
        scheme = get_object_or_404(Scheme, pk=pk)
        form = NewSchemeForm(request.POST, instance=scheme, user=request.user)
        
        if form.is_valid():
            try:
                scheme = form.save(commit=False)
                scheme.updated_by = request.user
                scheme.save()
                
                # Create audit log
                SchemeAuditLog.objects.create(
                    scheme=scheme,
                    user=request.user,
                    action='updated',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                # Log user activity
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='scheme_updated',
                    description=f'Updated scheme: {scheme.name}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Scheme "{scheme.name}" was updated successfully.')
                return redirect('new_scheme_detail', pk=scheme.pk)
            except Exception as e:
                messages.error(request, f"Error updating scheme: {str(e)}")
                # Log the error for debugging purposes
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Scheme update error: {str(e)}", exc_info=True)
        else:
            # Add more detailed error messages for field validation issues
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error in {field}: {error}")
        
        return render(request, self.template_name, {'form': form, 'scheme': scheme})

class NewSchemeDeleteView(LoginRequiredMixin, View):
    """A simplified view for deleting loan schemes"""
    template_name = 'schemes/new_scheme_confirm_delete.html'
    
    def get(self, request, pk):
        scheme = get_object_or_404(Scheme, pk=pk)
        
        # Check for any loans using this scheme
        related_loans = self.get_related_loans(scheme)
        
        return render(request, self.template_name, {
            'scheme': scheme,
            'related_loans': related_loans,
            'can_delete': len(related_loans) == 0
        })
    
    def post(self, request, pk):
        scheme = get_object_or_404(Scheme, pk=pk)
        scheme_name = scheme.name
        
        # Check if the user wants to deactivate instead of delete
        if 'deactivate' in request.POST:
            # Mark the scheme as inactive instead of deleting
            scheme.status = 'inactive'
            scheme.save()
            
            # Create audit log for deactivation
            SchemeAuditLog.objects.create(
                scheme=scheme,
                user=request.user,
                action='deactivated',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Log user activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='scheme_deactivated',
                description=f'Deactivated scheme: {scheme_name}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f'Scheme "{scheme_name}" was successfully deactivated.')
            return redirect('scheme_list')
        
        # Check for any loans using this scheme
        related_loans = self.get_related_loans(scheme)
        
        if related_loans:
            # If related loans exist, show an error message and redirect back
            loan_names = ", ".join([str(loan) for loan in related_loans[:5]])
            if len(related_loans) > 5:
                loan_names += f" and {len(related_loans) - 5} more"
                
            messages.error(
                request, 
                f'Cannot delete scheme "{scheme_name}" because it is being used by {len(related_loans)} loans: {loan_names}. '
                f'You can deactivate the scheme instead.'
            )
            return render(request, self.template_name, {
                'scheme': scheme,
                'related_loans': related_loans,
                'can_delete': False
            })
        
        try:
            # Log audit before deletion
            SchemeAuditLog.objects.create(
                scheme=scheme,
                user=request.user,
                action='deleted',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Log user activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='scheme_deleted',
                description=f'Deleted scheme: {scheme_name}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Proceed with deletion since no related loans exist
            scheme.delete()
            messages.success(request, f'Scheme "{scheme_name}" was deleted successfully.')
            
        except Exception as e:
            messages.error(request, f'Error deleting scheme: {str(e)}')
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Scheme deletion error: {str(e)}", exc_info=True)
            
        return redirect('scheme_list')
    
    def get_related_loans(self, scheme):
        """Check if there are any loans that use this scheme"""
        # Since we can't directly import loans.models, use a more Django-friendly approach
        from django.apps import apps
        
        # Get the Loan model dynamically
        try:
            Loan = apps.get_model('loans', 'Loan')
            # Find all loans using this scheme
            related_loans = Loan.objects.filter(scheme=scheme)
            return related_loans
        except LookupError:
            # If the Loan model doesn't exist or the app isn't installed,
            # return an empty list instead of trying to instantiate EmptyQuerySet
            return []

class SchemeJsonView(LoginRequiredMixin, View):
    """View to return scheme details in JSON format for AJAX requests"""
    
    def get(self, request, pk):
        try:
            scheme = get_object_or_404(Scheme, pk=pk)
            
            # Check permissions
            user = request.user
            if not user.is_superuser:
                if scheme.branch and user.branch != scheme.branch:
                    if not (hasattr(user, 'role') and user.role and user.role.name.lower() == 'regional manager'):
                        return JsonResponse({'error': 'Permission denied'}, status=403)
            
            # Return scheme data as JSON
            scheme_data = {
                'id': scheme.id,
                'name': scheme.name,
                'description': scheme.description,
                'is_gold_scheme': scheme.is_gold_scheme,
                'status': scheme.status,
                'is_active': scheme.is_active,
            }
            
            # Add standard fields
            if scheme.interest_rate:
                scheme_data['interest_rate'] = float(scheme.interest_rate)
            
            if scheme.loan_duration:
                scheme_data['loan_duration'] = scheme.loan_duration
            
            if scheme.minimum_amount:
                scheme_data['minimum_amount'] = float(scheme.minimum_amount)
            
            if scheme.maximum_amount:
                scheme_data['maximum_amount'] = float(scheme.maximum_amount)
            
            # Add dates
            scheme_data['start_date'] = scheme.start_date.isoformat()
            if scheme.end_date:
                scheme_data['end_date'] = scheme.end_date.isoformat()
            
            # Add gold loan specific fields
            if scheme.is_gold_scheme:
                if scheme.gold_interest_rate:
                    scheme_data['gold_interest_rate'] = float(scheme.gold_interest_rate)
                
                if scheme.expiry_period:
                    scheme_data['expiry_period'] = scheme.expiry_period
                
                if scheme.minimum_duration:
                    scheme_data['minimum_duration'] = scheme.minimum_duration
                
                if scheme.late_payment_interest:
                    scheme_data['late_payment_interest'] = float(scheme.late_payment_interest)
                
                if scheme.payment_due_day:
                    scheme_data['payment_due_day'] = scheme.payment_due_day
                
                if scheme.special_conditions:
                    scheme_data['special_conditions'] = scheme.special_conditions
                
                scheme_data['is_fixed_interest'] = scheme.is_fixed_interest
                scheme_data['auction_on_expiry'] = scheme.auction_on_expiry
            
            # Add branch info
            if scheme.branch:
                scheme_data['branch'] = {
                    'id': scheme.branch.id,
                    'name': scheme.branch.name
                }
            
            # Add additional conditions
            if scheme.additional_conditions:
                scheme_data['additional_conditions'] = scheme.additional_conditions
                
            return JsonResponse(scheme_data)
        except Scheme.DoesNotExist:
            return JsonResponse({'error': 'Scheme not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class SchemeCreateView(LoginRequiredMixin, View):
    """View for creating loan schemes with tiered interest rate structure"""
    template_name = 'schemes/scheme_form.html'
    
    def get(self, request):
        form = SchemeForm(user=request.user)
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = SchemeForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                scheme = form.save(commit=False)
                scheme.created_by = request.user
                scheme.updated_by = request.user
                scheme.is_gold_scheme = True
                
                # Auto-set branch for branch managers
                if not scheme.branch and not request.user.is_superuser:
                    if hasattr(request.user, 'role') and request.user.role and request.user.role.name.lower() == 'branch manager' and request.user.branch:
                        scheme.branch = request.user.branch
                
                scheme.save()
                
                # Create audit log
                SchemeAuditLog.objects.create(
                    scheme=scheme,
                    user=request.user,
                    action='created',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    changes={'interest_rate_structure': scheme.interest_rate_structure}
                )
                
                # Log user activity
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='tiered_scheme_created',
                    description=f'Created new tiered interest scheme: {scheme.name}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Scheme "{scheme.name}" with tiered interest rates was created successfully.')
                return redirect('scheme_detail', pk=scheme.pk)
            except Exception as e:
                messages.error(request, f"Error creating scheme: {str(e)}")
                # Log the error for debugging purposes
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Scheme creation error: {str(e)}", exc_info=True)
        else:
            # Add more detailed error messages for field validation issues
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error in {field}: {error}")
        
        return render(request, self.template_name, {'form': form})

class SchemeUpdateView(LoginRequiredMixin, View):
    """View for updating loan schemes with tiered interest rate structure"""
    template_name = 'schemes/scheme_form.html'
    
    def get(self, request, pk):
        scheme = get_object_or_404(Scheme, pk=pk)
        
        # Check if this is a tiered interest rate scheme
        has_tiered_structure = (
            scheme.early_period_months or 
            scheme.standard_period_months or 
            scheme.early_period_interest_rate or 
            scheme.late_period_interest_rate or
            (scheme.interest_rate_structure and len(scheme.interest_rate_structure) > 0)
        )
        
        if has_tiered_structure:
            # Use the tiered interest rate form
            form = SchemeForm(instance=scheme, user=request.user)
        else:
            # Redirect to the new scheme update for standard schemes
            return redirect('new_scheme_update', pk=pk)
            
        return render(request, self.template_name, {'form': form, 'scheme': scheme})
    
    def post(self, request, pk):
        scheme = get_object_or_404(Scheme, pk=pk)
        form = SchemeForm(request.POST, instance=scheme, user=request.user)
        
        if form.is_valid():
            try:
                scheme = form.save(commit=False)
                scheme.updated_by = request.user
                scheme.save()
                
                # Create audit log
                SchemeAuditLog.objects.create(
                    scheme=scheme,
                    user=request.user,
                    action='updated',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    changes={'interest_rate_structure': scheme.interest_rate_structure}
                )
                
                # Log user activity
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='tiered_scheme_updated',
                    description=f'Updated tiered interest scheme: {scheme.name}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Tiered interest scheme "{scheme.name}" was updated successfully.')
                return redirect('scheme_detail', pk=scheme.pk)
            except Exception as e:
                messages.error(request, f"Error updating scheme: {str(e)}")
                # Log the error for debugging purposes
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Tiered scheme update error: {str(e)}", exc_info=True)
        else:
            # Add more detailed error messages for field validation issues
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error in {field}: {error}")
        
        return render(request, self.template_name, {'form': form, 'scheme': scheme})
