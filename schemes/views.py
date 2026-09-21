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

from .models import Scheme, SchemeAuditLog, DailyGoldRate
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
                
            # Add interest rate structure if available
            if scheme.interest_rate_structure:
                scheme_data['interest_rate_structure'] = scheme.interest_rate_structure
                
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
        # A scheme is considered tiered if it has interest_rate_structure with multiple entries
        # OR if it has any of the tiered period fields set
        has_tiered_structure = False
        
        if scheme.interest_rate_structure:
            # If interest_rate_structure exists and has content, it's tiered
            has_tiered_structure = len(scheme.interest_rate_structure) > 0
        
        if not has_tiered_structure:
            # Also check the period/rate fields
            has_tiered_structure = (
                (scheme.early_period_months and scheme.early_period_months > 0) or
                (scheme.standard_period_months and scheme.standard_period_months > 0) or
                (scheme.early_period_interest_rate and scheme.early_period_interest_rate > 0) or
                (scheme.late_period_interest_rate and scheme.late_period_interest_rate > 0)
            )
        
        if has_tiered_structure:
            # Use the tiered interest rate form
            form = SchemeForm(instance=scheme, user=request.user)
            return render(request, self.template_name, {'form': form, 'scheme': scheme})
        else:
            # Redirect to the new scheme update for standard schemes
            return redirect('new_scheme_update', pk=pk)
    
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


class DailyGoldRateManageView(LoginRequiredMixin, View):
    """
    Head Office Central Gold Rate & RBI Statutory LTV Cap Broadcast Dashboard.
    Enables Super Admin & Executives to broadcast daily market rates across all 100+ branches.
    """
    template_name = 'schemes/daily_gold_rate_manage.html'

    def get(self, request):
        user = request.user
        org = getattr(user, 'organization', None)
        
        # Get active rate
        current_rate = DailyGoldRate.get_current_rate(organization=org)
        
        # Historical rate log
        rate_history = DailyGoldRate.objects.all()
        if org and not user.is_superuser:
            rate_history = rate_history.filter(Q(organization=org) | Q(organization__isnull=True))
        rate_history = rate_history.order_by('-date', '-created_at')[:30]

        context = {
            'current_rate': current_rate,
            'rate_history': rate_history,
            'today': timezone.now().date(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        user = request.user
        org = getattr(user, 'organization', None)

        try:
            rate_24k = Decimal(str(request.POST.get('rate_24k_per_gram', '7200.00')).strip())
            rate_22k = Decimal(str(request.POST.get('rate_22k_per_gram', '6600.00')).strip())
            rate_20k = Decimal(str(request.POST.get('rate_20k_per_gram', '6000.00')).strip())
            rate_18k = Decimal(str(request.POST.get('rate_18k_per_gram', '5400.00')).strip())
            max_ltv = Decimal(str(request.POST.get('maximum_ltv_percentage', '75.00')).strip())
            notes = request.POST.get('notes', '').strip()

            # Hard RBI Cap Validation
            if max_ltv > Decimal('90.00'):
                messages.error(request, "RBI Statutory limit restricts LTV to a maximum of 90.00%. Default is 75.00%.")
                return redirect('daily_gold_rates')
            if max_ltv < Decimal('10.00'):
                messages.error(request, "Please enter a valid LTV percentage (minimum 10%).")
                return redirect('daily_gold_rates')

            # Create or update broadcast
            today = timezone.now().date()
            new_rate = DailyGoldRate.objects.create(
                organization=org,
                date=today,
                rate_24k_per_gram=rate_24k,
                rate_22k_per_gram=rate_22k,
                rate_20k_per_gram=rate_20k,
                rate_18k_per_gram=rate_18k,
                maximum_ltv_percentage=max_ltv,
                updated_by=user,
                is_active=True,
                notes=notes or f"Head Office Rate Broadcast on {today}"
            )

            # Deactivate older rates for today if any
            DailyGoldRate.objects.filter(
                organization=org,
                is_active=True
            ).exclude(pk=new_rate.pk).update(is_active=False)

            messages.success(
                request,
                f"🎉 Central Daily Gold Rate broadcasted successfully! 22K Rate: ₹{rate_22k:,.2f}/g | RBI LTV Cap: {max_ltv}%"
            )
        except Exception as e:
            messages.error(request, f"Failed to broadcast gold rate: {str(e)}")

        return redirect('daily_gold_rates')


def api_get_today_gold_rate(request):
    """
    JSON endpoint for loan creation UI and branches to fetch live active rates & LTV caps.
    """
    user = request.user if request.user.is_authenticated else None
    org = getattr(user, 'organization', None) if user else None
    rate = DailyGoldRate.get_current_rate(organization=org)

    data = {
        'status': 'success',
        'date': rate.date.strftime('%Y-%m-%d'),
        'rate_24k_per_gram': float(rate.rate_24k_per_gram),
        'rate_22k_per_gram': float(rate.rate_22k_per_gram),
        'rate_20k_per_gram': float(rate.rate_20k_per_gram),
        'rate_18k_per_gram': float(rate.rate_18k_per_gram),
        'maximum_ltv_percentage': float(rate.maximum_ltv_percentage),
        'notes': rate.notes or '',
    }
    return JsonResponse(data)


def api_fetch_live_gold_rates(request):
    """
    JSON endpoint to fetch real-time market gold price from live API feeds.
    """
    from .services_gold_api import fetch_live_gold_rate
    res = fetch_live_gold_rate()
    if res.get('success'):
        return JsonResponse({
            'status': 'success',
            'data': res
        })
    else:
        return JsonResponse({
            'status': 'error',
            'message': res.get('error', 'Unable to fetch live rates')
        }, status=502)


