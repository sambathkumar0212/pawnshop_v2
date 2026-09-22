"""
Customer Self-Service Portal Views & Controller
Handles Customer Portal Authentication, Main Overview Dashboard,
Active/Closed Loan tracking, and Dynamic UPI QR 12-Digit UTR Payment Submission.
"""

import re
import logging
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, View
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db.models import Sum, Q

from accounts.models import Customer, CustomUser, Role
from transactions.models import Loan, Payment
from transactions.services_upi import get_loan_upi_payment_payload

logger = logging.getLogger(__name__)


class PortalRootRedirectView(View):
    """Redirects /portal/ to /portal/dashboard/ if authenticated or /portal/login/ if not."""
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('portal_dashboard')
        return redirect('portal_login')


class PortalLoginView(LoginView):
    """Customer Portal Login View."""
    template_name = 'portal/portal_login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('portal_dashboard')
        
    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password. Please verify your Customer ID / Username and PIN.")
        return super().form_invalid(form)


class PortalLogoutView(LogoutView):
    """Customer Portal Logout View."""
    next_page = 'portal_login'


class PortalDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main Self-Service Customer Portal Dashboard.
    Presents:
    - Customer Profile header context
    - Active Loans Table (with balances, interest due, and 'Pay via UPI QR' triggers)
    - Closed Loans History Table
    - Chronological Repayment Logs with verification status badges
    """
    template_name = 'portal/portal_dashboard.html'
    login_url = reverse_lazy('portal_login')

    def get_customer(self):
        user = self.request.user
        # 1. Direct one-to-one reverse relationship
        if hasattr(user, 'customer_profile') and user.customer_profile:
            return user.customer_profile
            
        # 2. Match by linked user FK or phone number
        customer = Customer.objects.filter(user=user).first()
        if customer:
            return customer
            
        # 3. Match by phone digits
        phone_digits = re.sub(r'\D', '', user.phone or user.username or '')[-10:]
        if phone_digits:
            customer = Customer.objects.filter(phone__icontains=phone_digits).first()
            if customer:
                # Associate for future requests
                customer.user = user
                customer.save(update_fields=['user'])
                return customer
                
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_customer()
        
        if not customer:
            context['no_customer_profile'] = True
            return context

        context['customer'] = customer
        
        # 1. Active Loans
        active_loans = Loan.objects.filter(
            customer=customer, 
            status='active'
        ).select_related('scheme', 'branch').prefetch_related('loanitem_set__item').order_by('-issue_date')
        
        # Compute real-time outstanding balances and accrued interest for active loans
        total_outstanding = Decimal('0.00')
        total_principal = Decimal('0.00')
        total_interest_due = Decimal('0.00')
        
        for loan in active_loans:
            # Principal
            prin = getattr(loan, 'principal_amount', None) or getattr(loan, 'amount', Decimal('0.00')) or Decimal('0.00')
            total_principal += prin
            
            # Current calculated interest
            interest = getattr(loan, 'accrued_interest', None) or getattr(loan, 'total_interest_amount', None)
            if interest is None and hasattr(loan, 'calculate_interest'):
                try:
                    interest = loan.calculate_interest()
                except Exception:
                    interest = Decimal('0.00')
            interest = interest or Decimal('0.00')
            loan.calculated_interest = interest
            total_interest_due += interest
            
            # Balance
            bal = getattr(loan, 'total_outstanding_amount', None) or (prin + interest)
            loan.current_total_due = bal
            total_outstanding += bal

        context['active_loans'] = active_loans
        context['active_loans_count'] = len(active_loans)
        context['total_outstanding'] = total_outstanding
        context['total_principal'] = total_principal
        context['total_interest_due'] = total_interest_due
        
        # 2. Closed / Settled Loans
        closed_loans = Loan.objects.filter(
            customer=customer
        ).exclude(status='active').select_related('scheme', 'branch').order_by('-updated_at', '-id')
        context['closed_loans'] = closed_loans
        context['closed_loans_count'] = len(closed_loans)

        # 3. Repayment History Logs
        repayments = Payment.objects.filter(
            loan__customer=customer
        ).select_related('loan', 'loan__branch').order_by('-payment_date', '-created_at')
        context['repayments'] = repayments
        context['repayments_count'] = len(repayments)
        
        total_repaid = repayments.filter(verification_status='verified').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        context['total_repaid'] = total_repaid
        
        # 4. Nearest next payment due date
        next_due_loan = active_loans.order_by('due_date').first() if active_loans else None
        context['next_due_date'] = getattr(next_due_loan, 'due_date', None) if next_due_loan else None

        return context


class PortalLoanUPIModalView(LoginRequiredMixin, View):
    """
    Returns JSON payload containing the dynamic Base64 QR code and UPI URI
    for a specific loan belonging to the logged-in customer.
    """
    login_url = reverse_lazy('portal_login')

    def get(self, request, loan_number, *args, **kwargs):
        customer = getattr(request.user, 'customer_profile', None) or Customer.objects.filter(user=request.user).first()
        if not customer and not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Customer profile not found.'}, status=403)
            
        if request.user.is_superuser:
            loan = get_object_or_404(Loan, loan_number=loan_number)
        else:
            loan = get_object_or_404(Loan, loan_number=loan_number, customer=customer)
            
        requested_amount = request.GET.get('amount')
        try:
            payload = get_loan_upi_payment_payload(loan, requested_amount=requested_amount)
            return JsonResponse({'success': True, **payload})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class PortalSubmitUPIPaymentView(LoginRequiredMixin, View):
    """
    Handles customer submission of their 12-digit UPI UTR / Transaction Reference number.
    Creates a Payment record with status='pending'.
    """
    login_url = reverse_lazy('portal_login')

    def post(self, request, loan_number, *args, **kwargs):
        customer = getattr(request.user, 'customer_profile', None) or Customer.objects.filter(user=request.user).first()
        if not customer and not request.user.is_superuser:
            messages.error(request, "Unauthorized customer account.")
            return redirect('portal_login')
            
        if request.user.is_superuser:
            loan = get_object_or_404(Loan, loan_number=loan_number)
        else:
            loan = get_object_or_404(Loan, loan_number=loan_number, customer=customer)

        utr_number = (request.POST.get('utr_number') or '').strip()
        amount_raw = (request.POST.get('amount') or '').strip()
        payment_notes = (request.POST.get('notes') or '').strip()

        # Validation
        if not utr_number:
            messages.error(request, "⚠️ Please enter your 12-digit UPI reference / transaction UTR number.")
            return redirect('portal_dashboard')

        # Clean UTR digits
        utr_clean = re.sub(r'[^a-zA-Z0-9]', '', utr_number)
        if len(utr_clean) < 6:
            messages.error(request, "⚠️ Invalid UTR / Reference number provided. Please check your UPI app receipt.")
            return redirect('portal_dashboard')

        # Validate amount
        try:
            amount = Decimal(str(amount_raw))
            if amount <= Decimal('0.00'):
                raise ValueError()
        except Exception:
            messages.error(request, "⚠️ Please enter a valid payment amount.")
            return redirect('portal_dashboard')

        # Check for existing duplicate pending payment with same UTR
        duplicate = Payment.objects.filter(
            utr_number=utr_clean,
            verification_status='pending'
        ).exists()
        if duplicate:
            messages.warning(request, f"ℹ️ Payment with UTR {utr_clean} has already been submitted and is awaiting branch verification.")
            return redirect('portal_dashboard')

        # Create Payment in Pending status
        payment = Payment.objects.create(
            loan=loan,
            amount=amount,
            payment_date=timezone.localdate() if hasattr(timezone, 'localdate') else timezone.now().date(),
            payment_method='upi',
            reference_number=utr_clean,
            utr_number=utr_clean,
            verification_status='pending',
            notes=f"Customer Portal UPI Submission. {payment_notes}".strip(),
            received_by=None
        )

        messages.success(
            request,
            f"🎉 UPI Payment of ₹{amount:,.2f} for Loan #{loan.loan_number} submitted successfully! 📲 UTR Ref: {utr_clean}. Your branch staff will verify and credit it shortly."
        )
        return redirect('portal_dashboard')
