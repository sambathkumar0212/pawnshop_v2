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
from transactions.views import get_branch_bill_header_phones


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
        
        # Get branch phone display (supports multiple phone numbers)
        context['branch_phone_display'] = get_branch_bill_header_phones(branch)
        
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


# ==============================================================================
# Task 1.4: Branch Cash Drawer, Cash Till & Daily Cash Scroll (EOD Reconciliation)
# ==============================================================================
from django.views import View
from decimal import Decimal
from .models import CashTill, CashScrollEntry
from .forms_till import CashTillOpenForm, CashTillReconciliationForm, CashBankDepositForm
from transactions.models import Payment, Loan, DisbursementTransaction


class CashTillDashboardView(LoginRequiredMixin, View):
    """
    Live Cash Drawer, Real-Time Cash Scroll & Reconciliation Dashboard for Branch Operations.
    """
    template_name = 'branches/cash_till_dashboard.html'

    def get_user_branch(self, request):
        branch_id = request.GET.get('branch_id')
        if branch_id and (request.user.is_superuser or getattr(request.user, 'role', None) in ['admin', 'manager', 'regional_manager']):
            return get_object_or_404(Branch, pk=branch_id)
        if getattr(request.user, 'branch', None):
            return request.user.branch
        return Branch.objects.filter(is_active=True).first()

    def get(self, request):
        branch = self.get_user_branch(request)
        if not branch:
            messages.warning(request, "No active branch found. Please create or assign a branch first.")
            return redirect('branch_list')

        today = timezone.now().date()
        
        # Get or find today's active till for current cashier and branch
        till = CashTill.objects.filter(branch=branch, date=today, cashier=request.user).first()
        if not till:
            # Fallback: check if another cashier opened a till for this branch today
            till = CashTill.objects.filter(branch=branch, date=today).first()

        previous_till = CashTill.objects.filter(branch=branch, date__lt=today).order_by('-date').first()
        suggested_opening = Decimal('0.00')
        if previous_till:
            suggested_opening = previous_till.closing_balance_physical or previous_till.closing_balance_system or Decimal('0.00')

        feed_items = []
        if till:
            till.sync_live_transactions()

            # Compile live transaction scroll feed
            # 1. Opening entry
            feed_items.append({
                'time': till.created_at,
                'type': 'OPENING',
                'type_display': 'Opening Balance',
                'direction': 'IN',
                'amount': till.opening_balance,
                'ref': 'BOD-REGISTER',
                'narrative': f"Opening drawer cash registered by {till.cashier.get_full_name() or till.cashier.username}",
                'user': till.cashier
            })

            # 2. Manual cash scroll entries (Bank deposits, petty cash, etc.)
            for entry in till.entries.exclude(entry_type='OPENING'):
                feed_items.append({
                    'time': entry.created_at,
                    'type': entry.entry_type,
                    'type_display': entry.get_entry_type_display(),
                    'direction': entry.direction,
                    'amount': entry.amount,
                    'ref': entry.reference_id or 'VOUCHER',
                    'narrative': entry.description,
                    'user': entry.created_by
                })

            # 3. Cash loan repayments today
            repayments = Payment.objects.filter(
                loan__branch=branch,
                payment_date=today,
                payment_method__iexact='cash'
            ).select_related('loan', 'loan__customer', 'received_by')
            for p in repayments:
                feed_items.append({
                    'time': p.created_at if hasattr(p, 'created_at') else timezone.now(),
                    'type': 'LOAN_REPAYMENT',
                    'type_display': 'Loan Repayment (Cash)',
                    'direction': 'IN',
                    'amount': p.amount,
                    'ref': f"LN-{p.loan.loan_number}",
                    'narrative': f"Repayment from {p.loan.customer.full_name} for Loan #{p.loan.loan_number}",
                    'user': p.received_by
                })

            # 4. Cash loan disbursals today
            disbursements = DisbursementTransaction.objects.filter(
                loan__branch=branch,
                disbursed_at__date=today,
                payment_mode='CASH'
            ).select_related('loan', 'loan__customer', 'disbursed_by')
            for d in disbursements:
                feed_items.append({
                    'time': d.disbursed_at,
                    'type': 'LOAN_DISBURSAL',
                    'type_display': 'Loan Disbursal (Cash)',
                    'direction': 'OUT',
                    'amount': d.amount,
                    'ref': f"LN-{d.loan.loan_number}",
                    'narrative': f"Disbursed to {d.loan.customer.full_name} for Loan #{d.loan.loan_number}",
                    'user': d.disbursed_by
                })

            # Sort feed items descending by time
            feed_items.sort(key=lambda x: x['time'] or timezone.now(), reverse=True)

        all_branches = Branch.objects.filter(is_active=True)

        context = {
            'branch': branch,
            'all_branches': all_branches,
            'today': today,
            'till': till,
            'suggested_opening': suggested_opening,
            'feed_items': feed_items,
            'deposit_form': CashBankDepositForm(),
        }
        return render(request, self.template_name, context)


class CashTillOpenView(LoginRequiredMixin, View):
    """BOD Open Register View"""
    template_name = 'branches/cash_till_open.html'

    def get_user_branch(self, request):
        branch_id = request.GET.get('branch_id')
        if branch_id and (request.user.is_superuser or getattr(request.user, 'role', None) in ['admin', 'manager', 'regional_manager']):
            return get_object_or_404(Branch, pk=branch_id)
        if getattr(request.user, 'branch', None):
            return request.user.branch
        return Branch.objects.filter(is_active=True).first()

    def get(self, request):
        branch = self.get_user_branch(request)
        today = timezone.now().date()
        
        # Check if already opened
        existing_till = CashTill.objects.filter(branch=branch, date=today, cashier=request.user).first()
        if existing_till:
            messages.info(request, "Today's cash till is already open.")
            return redirect('cash_till_dashboard')

        previous_till = CashTill.objects.filter(branch=branch, date__lt=today).order_by('-date').first()
        suggested_opening = Decimal('0.00')
        if previous_till:
            suggested_opening = previous_till.closing_balance_physical or previous_till.closing_balance_system or Decimal('0.00')

        form = CashTillOpenForm(initial={'opening_balance': suggested_opening})
        context = {
            'branch': branch,
            'today': today,
            'previous_till': previous_till,
            'suggested_opening': suggested_opening,
            'form': form
        }
        return render(request, self.template_name, context)

    def post(self, request):
        branch = self.get_user_branch(request)
        today = timezone.now().date()
        
        form = CashTillOpenForm(request.POST)
        if form.is_valid():
            till, created = CashTill.objects.get_or_create(
                branch=branch,
                cashier=request.user,
                date=today,
                defaults={
                    'opening_balance': form.cleaned_data['opening_balance'],
                    'status': 'open'
                }
            )
            if not created:
                till.opening_balance = form.cleaned_data['opening_balance']
                till.status = 'open'
                till.save()

            # Create opening balance scroll entry
            CashScrollEntry.objects.create(
                till=till,
                entry_type='OPENING',
                direction='IN',
                amount=till.opening_balance,
                reference_id=f"BOD-{today.strftime('%Y%m%d')}",
                description=f"Beginning of Day cash drawer opened with ₹{till.opening_balance:,.2f}",
                created_by=request.user
            )

            till.sync_live_transactions()
            messages.success(request, f"Cash register successfully opened for {branch.name} with ₹{till.opening_balance:,.2f}.")
            return redirect('cash_till_dashboard')

        context = {
            'branch': branch,
            'today': today,
            'form': form
        }
        return render(request, self.template_name, context)


class CashTillReconcileView(LoginRequiredMixin, View):
    """EOD Denomination Count and Physical Reconciliation View"""
    template_name = 'branches/cash_till_reconcile.html'

    def get(self, request, pk):
        till = get_object_or_404(CashTill, pk=pk)
        till.sync_live_transactions()
        form = CashTillReconciliationForm(instance=till)
        context = {
            'till': till,
            'form': form,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        till = get_object_or_404(CashTill, pk=pk)
        till.sync_live_transactions()
        form = CashTillReconciliationForm(request.POST, instance=till)
        if form.is_valid():
            till = form.save(commit=False)
            till.closing_balance_physical = form.cleaned_data['closing_balance_physical']
            till.denomination_breakdown = form.cleaned_data['denomination_breakdown']
            
            variance = till.closing_balance_physical - till.closing_balance_system
            if variance == 0:
                till.status = 'reconciled'
                messages.success(request, f"EOD Physical Cash matched system balance perfectly (₹{till.closing_balance_physical:,.2f}). Ready for Manager Sign-off.")
            else:
                till.status = 'mismatched'
                direction_str = "Excess" if variance > 0 else "Shortage"
                messages.warning(request, f"EOD Cash Discrepancy noted: {direction_str} of ₹{abs(variance):,.2f}. Discrepancy reason recorded.")

            till.save()
            return redirect('cash_till_dashboard')

        context = {
            'till': till,
            'form': form,
        }
        return render(request, self.template_name, context)


class CashTillManagerSignoffView(LoginRequiredMixin, View):
    """Branch Manager / Admin Sign-off & Day Closure View"""
    def post(self, request, pk):
        till = get_object_or_404(CashTill, pk=pk)
        
        # Verify manager permissions
        is_manager = request.user.is_superuser or getattr(request.user, 'role', None) in ['admin', 'manager', 'regional_manager'] or request.user == till.branch.manager
        if not is_manager:
            messages.error(request, "Permission Denied: Only Branch Manager or Administrator can sign off and close the daily cash register.")
            return redirect('cash_till_dashboard')

        till.sync_live_transactions()
        till.status = 'closed'
        till.verified_by_manager = request.user
        till.reconciled_at = timezone.now()
        till.save()

        messages.success(request, f"Daily Cash Register for {till.branch.name} ({till.date}) has been verified and officially CLOSED by Manager {request.user.get_full_name() or request.user.username}.")
        return redirect('cash_till_dashboard')


class CashTillBankDepositView(LoginRequiredMixin, View):
    """Record Cash transfer from Till to Bank / CIT"""
    def post(self, request, pk):
        till = get_object_or_404(CashTill, pk=pk)
        form = CashBankDepositForm(request.POST)
        if form.is_valid():
            deposit_entry = form.save(commit=False)
            deposit_entry.till = till
            deposit_entry.entry_type = 'BANK_DEPOSIT'
            deposit_entry.direction = 'OUT'
            deposit_entry.created_by = request.user
            deposit_entry.save()

            till.sync_live_transactions()
            messages.success(request, f"Cash deposit of ₹{deposit_entry.amount:,.2f} to Bank/CIT recorded successfully.")
        else:
            messages.error(request, "Failed to record cash deposit. Please check the entered fields.")
        return redirect('cash_till_dashboard')


class CashTillPrintScrollView(LoginRequiredMixin, View):
    """Printable A4 Daily Cash Scroll & EOD Reconciliation Certificate"""
    template_name = 'branches/cash_till_print.html'

    def get(self, request, pk):
        till = get_object_or_404(CashTill, pk=pk)
        till.sync_live_transactions()
        
        # Build chronological stream
        feed_items = []
        feed_items.append({
            'time': till.created_at,
            'type_display': 'Opening Balance (BOD)',
            'direction': 'IN',
            'amount': till.opening_balance,
            'ref': 'BOD-REGISTER',
            'narrative': f"Opening drawer cash registered by {till.cashier.get_full_name() or till.cashier.username}",
            'user': till.cashier
        })

        for entry in till.entries.exclude(entry_type='OPENING'):
            feed_items.append({
                'time': entry.created_at,
                'type_display': entry.get_entry_type_display(),
                'direction': entry.direction,
                'amount': entry.amount,
                'ref': entry.reference_id or 'VOUCHER',
                'narrative': entry.description,
                'user': entry.created_by
            })

        repayments = Payment.objects.filter(
            loan__branch=till.branch,
            payment_date=till.date,
            payment_method__iexact='cash'
        ).select_related('loan', 'loan__customer', 'received_by')
        for p in repayments:
            feed_items.append({
                'time': p.created_at if hasattr(p, 'created_at') else timezone.now(),
                'type_display': 'Loan Repayment (Cash)',
                'direction': 'IN',
                'amount': p.amount,
                'ref': f"LN-{p.loan.loan_number}",
                'narrative': f"Repayment from {p.loan.customer.full_name}",
                'user': p.received_by
            })

        disbursements = DisbursementTransaction.objects.filter(
            loan__branch=till.branch,
            disbursed_at__date=till.date,
            payment_mode='CASH'
        ).select_related('loan', 'loan__customer', 'disbursed_by')
        for d in disbursements:
            feed_items.append({
                'time': d.disbursed_at,
                'type_display': 'Loan Disbursal (Cash)',
                'direction': 'OUT',
                'amount': d.amount,
                'ref': f"LN-{d.loan.loan_number}",
                'narrative': f"Disbursal to {d.loan.customer.full_name}",
                'user': d.disbursed_by
            })

        feed_items.sort(key=lambda x: x['time'] or timezone.now())

        context = {
            'till': till,
            'feed_items': feed_items,
            'now': timezone.now(),
        }
        return render(request, self.template_name, context)


class CashTillHistoryListView(LoginRequiredMixin, ListView):
    """Historical list of branch cash registers with filters"""
    model = CashTill
    template_name = 'branches/cash_till_history.html'
    context_object_name = 'tills'
    paginate_by = 20

    def get_queryset(self):
        queryset = CashTill.objects.select_related('branch', 'cashier', 'verified_by_manager').all()
        user = self.request.user
        if not user.is_superuser and getattr(user, 'role', None) not in ['admin', 'regional_manager']:
            if getattr(user, 'branch', None):
                queryset = queryset.filter(branch=user.branch)
        
        branch_id = self.request.GET.get('branch_id')
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
            
        start_date = self.request.GET.get('start_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
            
        end_date = self.request.GET.get('end_date')
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_branches'] = Branch.objects.filter(is_active=True)
        return context

