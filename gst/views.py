from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, FormView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Q
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db import transaction
from datetime import datetime, timedelta, date
from decimal import Decimal
import csv
import json
import io
import xlsxwriter

# PDF generation imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from .models import GSTRate, GSTTransaction, CompanyGSTDetails, GSTReportLog
from .forms import GSTRateForm, GSTTransactionForm, CompanyGSTDetailsForm, GSTReportForm
from utils.download_utils import DownloadMixin
# Utility functions
def get_current_month_stats():
    """Get GST statistics for the current month"""
    today = timezone.now().date()
    first_day = today.replace(day=1)
    
    transactions = GSTTransaction.objects.filter(
        transaction_date__gte=first_day,
        transaction_date__lte=today
    )
    
    return {
        'total_taxable': transactions.aggregate(Sum('taxable_value'))['taxable_value__sum'] or 0,
        'total_tax': transactions.aggregate(Sum('total_tax'))['total_tax__sum'] or 0,
        'cgst': transactions.aggregate(Sum('cgst_amount'))['cgst_amount__sum'] or 0,
        'sgst': transactions.aggregate(Sum('sgst_amount'))['sgst_amount__sum'] or 0,
        'igst': transactions.aggregate(Sum('igst_amount'))['igst_amount__sum'] or 0,
    }

def get_financial_year_stats():
    """Get GST statistics for the current financial year (April to March in India)"""
    today = timezone.now().date()
    
    # Determine financial year start date
    if today.month < 4:  # Jan to March
        fy_start = date(today.year - 1, 4, 1)
    else:  # April to Dec
        fy_start = date(today.year, 4, 1)
    
    transactions = GSTTransaction.objects.filter(
        transaction_date__gte=fy_start,
        transaction_date__lte=today
    )
    
    return {
        'total_taxable': transactions.aggregate(Sum('taxable_value'))['taxable_value__sum'] or 0,
        'total_tax': transactions.aggregate(Sum('total_tax'))['total_tax__sum'] or 0,
        'cgst': transactions.aggregate(Sum('cgst_amount'))['cgst_amount__sum'] or 0,
        'sgst': transactions.aggregate(Sum('sgst_amount'))['sgst_amount__sum'] or 0,
        'igst': transactions.aggregate(Sum('igst_amount'))['igst_amount__sum'] or 0,
    }

def get_financial_year_str():
    """Get the current financial year as a string (e.g., '2023-24')"""
    today = timezone.now().date()
    
    if today.month < 4:  # Jan to March
        return f"{today.year-1}-{str(today.year)[2:]}"
    else:  # April to Dec
        return f"{today.year}-{str(today.year+1)[2:]}"

# Dashboard View
@login_required
def gst_dashboard(request):
    """GST Dashboard showing summary and recent transactions"""
    # Get company GST details
    company_gst_details = CompanyGSTDetails.objects.first()
    
    # Get recent transactions (last 10)
    recent_transactions = GSTTransaction.objects.all().order_by('-transaction_date')[:10]
    
    # Get current month stats
    current_month_stats = get_current_month_stats()
    
    # Get financial year stats
    fy_stats = get_financial_year_stats()
    
    # Current month name
    current_month = timezone.now().date().strftime('%B %Y')
    
    # Financial year
    financial_year = get_financial_year_str()
    
    context = {
        'company_gst_details': company_gst_details,
        'recent_transactions': recent_transactions,
        'current_month_stats': current_month_stats,
        'fy_stats': fy_stats,
        'current_month': current_month,
        'financial_year': financial_year,
    }
    
    return render(request, 'gst/gst_dashboard.html', context)

# GST Rate Views
class GSTRateListView(LoginRequiredMixin, ListView):
    """View to list all GST rates"""
    model = GSTRate
    template_name = 'gst/gst_rate_list.html'
    context_object_name = 'rates'
    
    def get_queryset(self):
        # Order by active status first, then by name
        return GSTRate.objects.all().order_by('-is_active', 'name')

class GSTRateCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """View to create new GST rate"""
    model = GSTRate
    form_class = GSTRateForm
    template_name = 'gst/gst_rate_form.html'
    success_url = reverse_lazy('gst_rate_list')
    permission_required = 'gst.add_gstrate'
    
    def form_valid(self, form):
        messages.success(self.request, "GST rate created successfully.")
        return super().form_valid(form)

class GSTRateUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """View to update GST rate"""
    model = GSTRate
    form_class = GSTRateForm
    template_name = 'gst/gst_rate_form.html'
    success_url = reverse_lazy('gst_rate_list')
    permission_required = 'gst.change_gstrate'
    
    def form_valid(self, form):
        messages.success(self.request, "GST rate updated successfully.")
        return super().form_valid(form)

@login_required
@permission_required('gst.delete_gstrate')
def gst_rate_toggle_active(request, pk):
    """Toggle active status of a GST rate"""
    rate = get_object_or_404(GSTRate, pk=pk)
    rate.is_active = not rate.is_active
    rate.save()
    
    status = "activated" if rate.is_active else "deactivated"
    messages.success(request, f"GST rate '{rate.name}' {status} successfully.")
    
    return redirect('gst_rate_list')

# GST Rate API endpoint for AJAX calls
@login_required
def get_gst_rate_details(request):
    """API endpoint to get GST rate details for AJAX calls"""
    rate_id = request.GET.get('rate_id')
    
    if not rate_id:
        return JsonResponse({'success': False, 'error': 'Rate ID not provided'})
    
    try:
        gst_rate = GSTRate.objects.get(id=rate_id, is_active=True)
        return JsonResponse({
            'success': True,
            'cgst_rate': float(gst_rate.cgst_rate),
            'sgst_rate': float(gst_rate.sgst_rate),
            'igst_rate': float(gst_rate.igst_rate),
            'hsn_code': gst_rate.hsn_code or '',
            'name': gst_rate.name,
            'description': gst_rate.description or '',
        })
    except GSTRate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'GST rate not found'})

# GST Transaction Views
class GSTTransactionListView(LoginRequiredMixin, DownloadMixin, ListView):
    """View to list all GST transactions"""
    model = GSTTransaction
    template_name = 'gst/gst_transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 20
    
    # Download configuration
    download_filename = 'gst_transactions'
    download_fields = [
        'Transaction Date', 'Invoice Number', 'Transaction Type', 'Party Name', 'Party GSTIN',
        'Place of Supply', 'Is Interstate', 'Is Registered Dealer', 'Taxable Value', 'CGST Rate',
        'CGST Amount', 'SGST Rate', 'SGST Amount', 'IGST Rate', 'IGST Amount', 'Total Tax',
        'Total Amount', 'HSN Code', 'Item Description', 'Quantity', 'Rate per Unit', 'Created At'
    ]
    download_headers = [
        'Transaction Date', 'Invoice Number', 'Transaction Type', 'Party Name', 'Party GSTIN',
        'Place of Supply', 'Is Interstate', 'Is Registered Dealer', 'Taxable Value', 'CGST Rate',
        'CGST Amount', 'SGST Rate', 'SGST Amount', 'IGST Rate', 'IGST Amount', 'Total Tax',
        'Total Amount', 'HSN Code', 'Item Description', 'Quantity', 'Rate per Unit', 'Created At'
    ]
    
    def get_queryset(self):
        queryset = GSTTransaction.objects.all()
        
        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(transaction_date__gte=start_date)
            except ValueError:
                pass
                
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(transaction_date__lte=end_date)
            except ValueError:
                pass
        
        # Filter by transaction type if provided
        transaction_type = self.request.GET.get('transaction_type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
            
        # Filter by is_interstate if provided
        is_interstate = self.request.GET.get('is_interstate')
        if is_interstate:
            is_interstate_bool = is_interstate.lower() == 'true'
            queryset = queryset.filter(is_interstate=is_interstate_bool)
            
        # Filter by is_registered_dealer if provided
        is_registered_dealer = self.request.GET.get('is_registered_dealer')
        if is_registered_dealer:
            is_registered_dealer_bool = is_registered_dealer.lower() == 'true'
            queryset = queryset.filter(is_registered_dealer=is_registered_dealer_bool)
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(party_name__icontains=search) |
                Q(invoice_number__icontains=search) |
                Q(party_gstin__icontains=search) |
                Q(place_of_supply__icontains=search)
            )
        
        # Sorting
        sort_by = self.request.GET.get('sort', '-transaction_date')  # Default sort by newest first
        valid_sort_fields = {
            'transaction_date': 'transaction_date',
            '-transaction_date': '-transaction_date',
            'invoice_number': 'invoice_number',
            '-invoice_number': '-invoice_number',
            'party_name': 'party_name',
            '-party_name': '-party_name',
            'transaction_type': 'transaction_type',
            '-transaction_type': '-transaction_type',
            'taxable_value': 'taxable_value',
            '-taxable_value': '-taxable_value',
            'total_tax': 'total_tax',
            '-total_tax': '-total_tax',
            'total_amount': 'total_amount',
            '-total_amount': '-total_amount',
            'place_of_supply': 'place_of_supply',
            '-place_of_supply': '-place_of_supply',
        }
        
        if sort_by in valid_sort_fields:
            queryset = queryset.order_by(valid_sort_fields[sort_by])
        else:
            queryset = queryset.order_by('-transaction_date', '-created_at')  # Default fallback
            
        return queryset.select_related('gst_rate')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter parameters to context
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['transaction_type'] = self.request.GET.get('transaction_type', '')
        context['is_interstate'] = self.request.GET.get('is_interstate', '')
        context['is_registered_dealer'] = self.request.GET.get('is_registered_dealer', '')
        context['search_query'] = self.request.GET.get('search', '')
        context['current_sort'] = self.request.GET.get('sort', '-transaction_date')
        
        # Add transaction type choices to context
        context['transaction_type_choices'] = GSTTransaction.TRANSACTION_TYPE_CHOICES
        
        # Calculate totals
        transactions = self.get_queryset()
        context['totals'] = {
            'taxable_value': transactions.aggregate(Sum('taxable_value'))['taxable_value__sum'] or 0,
            'cgst_amount': transactions.aggregate(Sum('cgst_amount'))['cgst_amount__sum'] or 0,
            'sgst_amount': transactions.aggregate(Sum('sgst_amount'))['sgst_amount__sum'] or 0,
            'igst_amount': transactions.aggregate(Sum('igst_amount'))['igst_amount__sum'] or 0,
            'total_tax': transactions.aggregate(Sum('total_tax'))['total_tax__sum'] or 0,
            'total_amount': transactions.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
        }
        
        return context
    
        return super().get(request, *args, **kwargs)

class GSTTransactionDetailView(LoginRequiredMixin, DetailView):
    """View to display details of a GST transaction"""
    model = GSTTransaction
    template_name = 'gst/gst_transaction_detail.html'
    context_object_name = 'transaction'

class GSTTransactionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """View to create new GST transaction"""
    model = GSTTransaction
    form_class = GSTTransactionForm
    template_name = 'gst/gst_transaction_form.html'
    success_url = reverse_lazy('gst_transaction_list')
    permission_required = 'gst.add_gsttransaction'
    
    def form_valid(self, form):
        messages.success(self.request, "GST transaction created successfully.")
        return super().form_valid(form)

class GSTTransactionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """View to update GST transaction"""
    model = GSTTransaction
    form_class = GSTTransactionForm
    template_name = 'gst/gst_transaction_form.html'
    success_url = reverse_lazy('gst_transaction_list')
    permission_required = 'gst.change_gsttransaction'
    
    def form_valid(self, form):
        messages.success(self.request, "GST transaction updated successfully.")
        return super().form_valid(form)

@login_required
@permission_required('gst.delete_gsttransaction')
def gst_transaction_delete(request, pk):
    """Delete a GST transaction"""
    transaction = get_object_or_404(GSTTransaction, pk=pk)
    
    if request.method == 'POST':
        transaction.delete()
        messages.success(request, "GST transaction deleted successfully.")
        return redirect('gst_transaction_list')
    
    return render(request, 'gst/gst_transaction_confirm_delete.html', {'transaction': transaction})

# Company GST Details Views
@login_required
@permission_required('gst.change_companygstdetails')
def company_gst_details_update(request, pk=None):
    """View to create or update company GST details"""
    # If pk is 0, try to get the first record or create a new one
    if pk == 0:
        instance = CompanyGSTDetails.objects.first()
    else:
        instance = get_object_or_404(CompanyGSTDetails, pk=pk)
    
    if request.method == 'POST':
        form = CompanyGSTDetailsForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Company GST details updated successfully.")
            return redirect('gst_dashboard')
    else:
        form = CompanyGSTDetailsForm(instance=instance)
    
    return render(request, 'gst/company_gst_details_form.html', {'form': form})

# GST Report Views
@login_required
def gst_report(request):
    """View to generate GST reports"""
    if request.method == 'POST':
        form = GSTReportForm(request.POST)
        if form.is_valid():
            # Get form data
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            report_type = form.cleaned_data['report_type']
            export_format = form.cleaned_data['export_format']
            
            # Generate the report
            return generate_gst_report(request, start_date, end_date, report_type, export_format)
    else:
        form = GSTReportForm()
    
    return render(request, 'gst/gst_report_form.html', {'form': form})

def generate_gst_report(request, start_date, end_date, report_type, export_format):
    """Generate GST report based on parameters"""
    # Get transactions within date range
    transactions = GSTTransaction.objects.filter(
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    ).order_by('transaction_date')
    
    # Get company details
    company = CompanyGSTDetails.objects.first()
    
    # Prepare report data based on report type
    if report_type == 'gstr1':
        # GSTR-1 report (Outward supplies)
        report_data = generate_gstr1_data(transactions, company)
        filename = f"GSTR1_{start_date.strftime('%d%m%Y')}_{end_date.strftime('%d%m%Y')}"
    elif report_type == 'gstr3b':
        # GSTR-3B report (Summary return)
        report_data = generate_gstr3b_data(transactions, company)
        filename = f"GSTR3B_{start_date.strftime('%d%m%Y')}_{end_date.strftime('%d%m%Y')}"
    elif report_type == 'b2b':
        # B2B invoices (Business to Business)
        report_data = generate_b2b_data(transactions, company)
        filename = f"B2B_{start_date.strftime('%d%m%Y')}_{end_date.strftime('%d%m%Y')}"
    elif report_type == 'b2c':
        # B2C invoices (Business to Consumer)
        report_data = generate_b2c_data(transactions, company)
        filename = f"B2C_{start_date.strftime('%d%m%Y')}_{end_date.strftime('%d%m%Y')}"
    elif report_type == 'hsn_summary':
        # HSN summary
        report_data = generate_hsn_data(transactions, company)
        filename = f"HSN_{start_date.strftime('%d%m%Y')}_{end_date.strftime('%d%m%Y')}"
    else:
        # Default to transaction list
        report_data = [
            {
                'date': t.transaction_date.strftime('%d-%m-%Y'),
                'invoice': t.invoice_number,
                'type': t.get_transaction_type_display(),
                'party': t.party_name,
                'gstin': t.party_gstin or '',
                'place': t.place_of_supply,
                'taxable': t.taxable_value,
                'cgst': t.cgst_amount,
                'sgst': t.sgst_amount,
                'igst': t.igst_amount,
                'total_tax': t.total_tax,
                'total': t.total_amount,
            }
            for t in transactions
        ]
        filename = f"GST_Transactions_{start_date.strftime('%d%m%Y')}_{end_date.strftime('%d%m%Y')}"
    
    # Export in the requested format
    if export_format == 'csv':
        return export_to_csv(report_data, filename, request, start_date, end_date, report_type)
    elif export_format == 'excel':
        return export_to_excel(report_data, filename, report_type, request, start_date, end_date)
    elif export_format == 'pdf':
        return export_to_pdf(report_data, filename, report_type, request, start_date, end_date)
    elif export_format == 'json':
        return export_to_json(report_data, filename, request, start_date, end_date, report_type)
    
    # Default to CSV if format not recognized
    return export_to_csv(report_data, filename, request, start_date, end_date, report_type)

# Helper functions for report generation
def generate_gstr1_data(transactions, company):
    """Generate data for GSTR-1 report"""
    # B2B invoices (registered dealers)
    b2b_invoices = transactions.filter(
        is_registered_dealer=True,
        transaction_type='SALE'
    )
    
    # B2C invoices (consumers)
    b2c_invoices = transactions.filter(
        is_registered_dealer=False,
        transaction_type='SALE'
    )
    
    # HSN summary
    hsn_summary = {}
    for t in transactions.filter(transaction_type='SALE'):
        hsn_code = t.gst_rate.hsn_code or 'Unknown'
        if hsn_code not in hsn_summary:
            hsn_summary[hsn_code] = {
                'hsn_code': hsn_code,
                'description': t.gst_rate.description or t.gst_rate.name,
                'taxable_value': 0,
                'cgst': 0,
                'sgst': 0,
                'igst': 0,
                'total_tax': 0,
            }
        
        hsn_summary[hsn_code]['taxable_value'] += t.taxable_value
        hsn_summary[hsn_code]['cgst'] += t.cgst_amount
        hsn_summary[hsn_code]['sgst'] += t.sgst_amount
        hsn_summary[hsn_code]['igst'] += t.igst_amount
        hsn_summary[hsn_code]['total_tax'] += t.total_tax
    
    # Combine all data
    report_data = {
        'company': {
            'name': company.legal_name if company else '',
            'gstin': company.gstin if company else '',
            'period': transactions.first().transaction_date.strftime('%B %Y') if transactions.exists() else '',
        },
        'b2b': [
            {
                'gstin': t.party_gstin,
                'party_name': t.party_name,
                'invoice_number': t.invoice_number,
                'date': t.transaction_date.strftime('%d-%m-%Y'),
                'place_of_supply': t.place_of_supply,
                'is_interstate': t.is_interstate,
                'taxable_value': t.taxable_value,
                'cgst': t.cgst_amount,
                'sgst': t.sgst_amount,
                'igst': t.igst_amount,
                'total_tax': t.total_tax,
                'total': t.total_amount,
                'gst_rate': t.gst_rate.igst_rate,
            }
            for t in b2b_invoices
        ],
        'b2c': [
            {
                'party_name': t.party_name,
                'invoice_number': t.invoice_number,
                'date': t.transaction_date.strftime('%d-%m-%Y'),
                'place_of_supply': t.place_of_supply,
                'is_interstate': t.is_interstate,
                'taxable_value': t.taxable_value,
                'cgst': t.cgst_amount,
                'sgst': t.sgst_amount,
                'igst': t.igst_amount,
                'total_tax': t.total_tax,
                'total': t.total_amount,
                'gst_rate': t.gst_rate.igst_rate,
            }
            for t in b2c_invoices
        ],
        'hsn': list(hsn_summary.values()),
    }
    
    return report_data

def generate_gstr3b_data(transactions, company):
    """Generate data for GSTR-3B report"""
    # Filter outward supplies (sales)
    outward_supplies = transactions.filter(transaction_type='SALE')
    
    # Aggregate totals
    taxable_outward = outward_supplies.aggregate(
        taxable=Sum('taxable_value'),
        cgst=Sum('cgst_amount'),
        sgst=Sum('sgst_amount'),
        igst=Sum('igst_amount'),
        total_tax=Sum('total_tax'),
    )
    
    # Interstate supplies to unregistered persons
    interstate_b2c = outward_supplies.filter(
        is_interstate=True,
        is_registered_dealer=False,
    ).aggregate(
        taxable=Sum('taxable_value'),
        igst=Sum('igst_amount'),
    )
    
    # Prepare data
    report_data = {
        'company': {
            'name': company.legal_name if company else '',
            'gstin': company.gstin if company else '',
            'period': transactions.first().transaction_date.strftime('%B %Y') if transactions.exists() else '',
        },
        'outward_supplies': {
            'taxable_value': taxable_outward['taxable'] or 0,
            'cgst': taxable_outward['cgst'] or 0,
            'sgst': taxable_outward['sgst'] or 0,
            'igst': taxable_outward['igst'] or 0,
            'total_tax': taxable_outward['total_tax'] or 0,
        },
        'interstate_b2c': {
            'taxable_value': interstate_b2c['taxable'] or 0,
            'igst': interstate_b2c['igst'] or 0,
        },
    }
    
    return report_data

def generate_b2b_data(transactions, company):
    """Generate data for B2B invoices report"""
    # Filter B2B transactions (registered dealers)
    b2b_transactions = transactions.filter(
        is_registered_dealer=True,
        transaction_type='SALE'
    )
    
    # Prepare data
    report_data = [
        {
            'gstin': t.party_gstin,
            'party_name': t.party_name,
            'invoice_number': t.invoice_number,
            'date': t.transaction_date.strftime('%d-%m-%Y'),
            'place_of_supply': t.place_of_supply,
            'is_interstate': 'Yes' if t.is_interstate else 'No',
            'taxable_value': t.taxable_value,
            'cgst': t.cgst_amount,
            'sgst': t.sgst_amount,
            'igst': t.igst_amount,
            'total_tax': t.total_tax,
            'total': t.total_amount,
            'gst_rate': t.gst_rate.igst_rate,
            'hsn_code': t.gst_rate.hsn_code or '',
        }
        for t in b2b_transactions
    ]
    
    return report_data

def generate_b2c_data(transactions, company):
    """Generate data for B2C invoices report"""
    # Filter B2C transactions (unregistered persons)
    b2c_transactions = transactions.filter(
        is_registered_dealer=False,
        transaction_type='SALE'
    )
    
    # Prepare data
    report_data = [
        {
            'party_name': t.party_name,
            'invoice_number': t.invoice_number,
            'date': t.transaction_date.strftime('%d-%m-%Y'),
            'place_of_supply': t.place_of_supply,
            'is_interstate': 'Yes' if t.is_interstate else 'No',
            'taxable_value': t.taxable_value,
            'cgst': t.cgst_amount,
            'sgst': t.sgst_amount,
            'igst': t.igst_amount,
            'total_tax': t.total_tax,
            'total': t.total_amount,
            'gst_rate': t.gst_rate.igst_rate,
            'hsn_code': t.gst_rate.hsn_code or '',
        }
        for t in b2c_transactions
    ]
    
    return report_data

def generate_hsn_data(transactions, company):
    """Generate data for HSN summary report"""
    # Filter sales transactions
    sales_transactions = transactions.filter(transaction_type='SALE')
    
    # Group by HSN code
    hsn_summary = {}
    for t in sales_transactions:
        hsn_code = t.gst_rate.hsn_code or 'Unknown'
        if hsn_code not in hsn_summary:
            hsn_summary[hsn_code] = {
                'hsn_code': hsn_code,
                'description': t.gst_rate.description or t.gst_rate.name,
                'taxable_value': 0,
                'cgst': 0,
                'sgst': 0,
                'igst': 0,
                'total_tax': 0,
                'total_transactions': 0,
            }
        
        hsn_summary[hsn_code]['taxable_value'] += t.taxable_value
        hsn_summary[hsn_code]['cgst'] += t.cgst_amount
        hsn_summary[hsn_code]['sgst'] += t.sgst_amount
        hsn_summary[hsn_code]['igst'] += t.igst_amount
        hsn_summary[hsn_code]['total_tax'] += t.total_tax
        hsn_summary[hsn_code]['total_transactions'] += 1
    
    # Convert to list
    report_data = list(hsn_summary.values())
    
    return report_data

# Export functions
def export_to_csv(data, filename, request=None, start_date=None, end_date=None, report_type=None):
    """Export data to CSV file"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    
    writer = csv.writer(response)
    
    # Write headers
    if data and isinstance(data, list):
        headers = data[0].keys()
        writer.writerow(headers)
        
        # Write data rows
        for row in data:
            writer.writerow(row.values())
    elif data and isinstance(data, dict):
        # For nested data like GSTR1
        if 'b2b' in data:
            # Write B2B invoices
            writer.writerow(['B2B Invoices'])
            if data['b2b']:
                headers = data['b2b'][0].keys()
                writer.writerow(headers)
                for row in data['b2b']:
                    writer.writerow(row.values())
            
            # Write B2C invoices
            writer.writerow([])
            writer.writerow(['B2C Invoices'])
            if data['b2c']:
                headers = data['b2c'][0].keys()
                writer.writerow(headers)
                for row in data['b2c']:
                    writer.writerow(row.values())
            
            # Write HSN summary
            writer.writerow([])
            writer.writerow(['HSN Summary'])
            if data['hsn']:
                headers = data['hsn'][0].keys()
                writer.writerow(headers)
                for row in data['hsn']:
                    writer.writerow(row.values())
        elif 'outward_supplies' in data:
            # GSTR3B data
            writer.writerow(['GSTR-3B Summary'])
            writer.writerow(['Company', data['company']['name']])
            writer.writerow(['GSTIN', data['company']['gstin']])
            writer.writerow(['Period', data['company']['period']])
            
            writer.writerow([])
            writer.writerow(['Outward Supplies'])
            writer.writerow(['Taxable Value', 'CGST', 'SGST', 'IGST', 'Total Tax'])
            writer.writerow([
                data['outward_supplies']['taxable_value'],
                data['outward_supplies']['cgst'],
                data['outward_supplies']['sgst'],
                data['outward_supplies']['igst'],
                data['outward_supplies']['total_tax'],
            ])
            
            writer.writerow([])
            writer.writerow(['Interstate Supplies to Unregistered Persons'])
            writer.writerow(['Taxable Value', 'IGST'])
            writer.writerow([
                data['interstate_b2c']['taxable_value'],
                data['interstate_b2c']['igst'],
            ])
    
    # Log the report generation
    if request and request.user.is_authenticated and all([start_date, end_date, report_type]):
        GSTReportLog.objects.create(
            report_type=report_type.upper(),
            start_date=start_date,
            end_date=end_date,
            file_format='CSV',
            generated_by=request.user,
        )
    
    return response

def export_to_excel(data, filename, report_type, request=None, start_date=None, end_date=None):
    """Export data to Excel file"""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    # Create styles
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4472C4',
        'color': 'white',
        'align': 'center',
        'valign': 'vcenter',
        'border': 1,
    })
    
    subheader_format = workbook.add_format({
        'bold': True,
        'bg_color': '#8EA9DB',
        'align': 'center',
        'valign': 'vcenter',
        'border': 1,
    })
    
    cell_format = workbook.add_format({
        'border': 1,
    })
    
    number_format = workbook.add_format({
        'border': 1,
        'num_format': '#,##0.00',
    })
    
    # Create worksheet based on report type
    if report_type == 'gstr1':
        # GSTR-1 report
        # Company info worksheet
        info_sheet = workbook.add_worksheet('Info')
        info_sheet.write(0, 0, 'GSTR-1 Report', header_format)
        info_sheet.write(1, 0, 'Company', subheader_format)
        info_sheet.write(1, 1, data['company']['name'], cell_format)
        info_sheet.write(2, 0, 'GSTIN', subheader_format)
        info_sheet.write(2, 1, data['company']['gstin'], cell_format)
        info_sheet.write(3, 0, 'Period', subheader_format)
        info_sheet.write(3, 1, data['company']['period'], cell_format)
        
        # B2B worksheet
        b2b_sheet = workbook.add_worksheet('B2B Invoices')
        # Write headers
        if data['b2b']:
            headers = list(data['b2b'][0].keys())
            for col, header in enumerate(headers):
                b2b_sheet.write(0, col, header.replace('_', ' ').title(), header_format)
            
            # Write data rows
            for row_idx, row_data in enumerate(data['b2b'], 1):
                for col_idx, (key, value) in enumerate(row_data.items()):
                    if isinstance(value, (int, float, Decimal)):
                        b2b_sheet.write(row_idx, col_idx, value, number_format)
                    else:
                        b2b_sheet.write(row_idx, col_idx, value, cell_format)
        
        # B2C worksheet
        b2c_sheet = workbook.add_worksheet('B2C Invoices')
        # Write headers
        if data['b2c']:
            headers = list(data['b2c'][0].keys())
            for col, header in enumerate(headers):
                b2c_sheet.write(0, col, header.replace('_', ' ').title(), header_format)
            
            # Write data rows
            for row_idx, row_data in enumerate(data['b2c'], 1):
                for col_idx, (key, value) in enumerate(row_data.items()):
                    if isinstance(value, (int, float, Decimal)):
                        b2c_sheet.write(row_idx, col_idx, value, number_format)
                    else:
                        b2c_sheet.write(row_idx, col_idx, value, cell_format)
        
        # HSN worksheet
        hsn_sheet = workbook.add_worksheet('HSN Summary')
        # Write headers
        if data['hsn']:
            headers = list(data['hsn'][0].keys())
            for col, header in enumerate(headers):
                hsn_sheet.write(0, col, header.replace('_', ' ').title(), header_format)
            
            # Write data rows
            for row_idx, row_data in enumerate(data['hsn'], 1):
                for col_idx, (key, value) in enumerate(row_data.items()):
                    if isinstance(value, (int, float, Decimal)):
                        hsn_sheet.write(row_idx, col_idx, value, number_format)
                    else:
                        hsn_sheet.write(row_idx, col_idx, value, cell_format)
    
    elif report_type == 'gstr3b':
        # GSTR-3B report
        worksheet = workbook.add_worksheet('GSTR-3B')
        
        # Company info
        worksheet.write(0, 0, 'GSTR-3B Summary', header_format)
        worksheet.write(1, 0, 'Company', subheader_format)
        worksheet.write(1, 1, data['company']['name'], cell_format)
        worksheet.write(2, 0, 'GSTIN', subheader_format)
        worksheet.write(2, 1, data['company']['gstin'], cell_format)
        worksheet.write(3, 0, 'Period', subheader_format)
        worksheet.write(3, 1, data['company']['period'], cell_format)
        
        # Outward supplies
        worksheet.write(5, 0, 'Outward Supplies', header_format)
        headers = ['Taxable Value', 'CGST', 'SGST', 'IGST', 'Total Tax']
        for col, header in enumerate(headers):
            worksheet.write(6, col, header, subheader_format)
        
        worksheet.write(7, 0, data['outward_supplies']['taxable_value'], number_format)
        worksheet.write(7, 1, data['outward_supplies']['cgst'], number_format)
        worksheet.write(7, 2, data['outward_supplies']['sgst'], number_format)
        worksheet.write(7, 3, data['outward_supplies']['igst'], number_format)
        worksheet.write(7, 4, data['outward_supplies']['total_tax'], number_format)
        
        # Interstate B2C
        worksheet.write(9, 0, 'Interstate Supplies to Unregistered Persons', header_format)
        worksheet.write(10, 0, 'Taxable Value', subheader_format)
        worksheet.write(10, 1, 'IGST', subheader_format)
        
        worksheet.write(11, 0, data['interstate_b2c']['taxable_value'], number_format)
        worksheet.write(11, 1, data['interstate_b2c']['igst'], number_format)
    
    else:
        # Simple list of data
        worksheet = workbook.add_worksheet('Data')
        
        # Write headers
        if data:
            headers = list(data[0].keys())
            for col, header in enumerate(headers):
                worksheet.write(0, col, header.replace('_', ' ').title(), header_format)
            
            # Write data rows
            for row_idx, row_data in enumerate(data, 1):
                for col_idx, (key, value) in enumerate(row_data.items()):
                    if isinstance(value, (int, float, Decimal)):
                        worksheet.write(row_idx, col_idx, value, number_format)
                    else:
                        worksheet.write(row_idx, col_idx, value, cell_format)
    
    # Close the workbook
    workbook.close()
    
    # Prepare response
    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    
    # Log the report generation
    if request and request.user.is_authenticated and all([start_date, end_date]):
        GSTReportLog.objects.create(
            report_type=report_type.upper(),
            start_date=start_date,
            end_date=end_date,
            file_format='Excel',
            generated_by=request.user,
        )
    
    return response

def export_to_json(data, filename, request=None, start_date=None, end_date=None, report_type=None):
    """Export data to JSON file"""
    response = HttpResponse(json.dumps(data, default=str, indent=4), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{filename}.json"'
    
    # Log the report generation
    if request and request.user.is_authenticated and all([start_date, end_date, report_type]):
        GSTReportLog.objects.create(
            report_type=report_type.upper(),
            start_date=start_date,
            end_date=end_date,
            file_format='JSON',
            generated_by=request.user,
        )
    
    return response

def export_to_pdf(data, filename, report_type, request=None, start_date=None, end_date=None):
    """Export data to PDF file"""
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    # Create PDF document
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # Center alignment
        textColor=colors.darkblue,
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        alignment=1,
        textColor=colors.darkblue,
    )
    
    company_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=20,
        alignment=1,
    )
    
    # Get company details
    company = CompanyGSTDetails.objects.first()
    
    # Helper function to format currency values
    def format_currency(value):
        """Format currency value without Unicode symbols for PDF compatibility"""
        try:
            return f"Rs. {float(value):,.2f}"
        except (ValueError, TypeError):
            return "Rs. 0.00"
    
    if report_type == 'gstr1' and isinstance(data, dict):
        # GSTR-1 Report
        elements.append(Paragraph("GSTR-1 Report", title_style))
        elements.append(Paragraph("Outward Supplies", subtitle_style))
        
        # Company information
        if company:
            company_info = f"""
            <b>{company.legal_name}</b><br/>
            GSTIN: {company.gstin}<br/>
            Period: {data['company'].get('period', 'N/A')}
            """
            elements.append(Paragraph(company_info, company_style))
        
        # B2B Invoices
        if data.get('b2b'):
            elements.append(Paragraph("B2B Invoices (Business to Business)", styles['Heading3']))
            b2b_table_data = [['GSTIN', 'Party Name', 'Invoice', 'Date', 'Taxable Value', 'CGST', 'SGST', 'IGST', 'Total']]
            
            for item in data['b2b'][:50]:  # Limit to first 50 records for PDF
                b2b_table_data.append([
                    str(item.get('gstin', '')),
                    str(item.get('party_name', ''))[:20] + ('...' if len(str(item.get('party_name', ''))) > 20 else ''),
                    str(item.get('invoice_number', '')),
                    str(item.get('date', '')),
                    format_currency(item.get('taxable_value', 0)),
                    format_currency(item.get('cgst', 0)),
                    format_currency(item.get('sgst', 0)),
                    format_currency(item.get('igst', 0)),
                    format_currency(item.get('total', 0)),
                ])
            
            b2b_table = Table(b2b_table_data, repeatRows=1)
            b2b_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(b2b_table)
            elements.append(Spacer(1, 20))
        
        # B2C Invoices
        if data.get('b2c'):
            elements.append(Paragraph("B2C Invoices (Business to Consumer)", styles['Heading3']))
            b2c_table_data = [['Party Name', 'Invoice', 'Date', 'Place of Supply', 'Taxable Value', 'Tax', 'Total']]
            
            for item in data['b2c'][:50]:  # Limit to first 50 records for PDF
                b2c_table_data.append([
                    str(item.get('party_name', ''))[:20] + ('...' if len(str(item.get('party_name', ''))) > 20 else ''),
                    str(item.get('invoice_number', '')),
                    str(item.get('date', '')),
                    str(item.get('place_of_supply', '')),
                    format_currency(item.get('taxable_value', 0)),
                    format_currency(item.get('total_tax', 0)),
                    format_currency(item.get('total', 0)),
                ])
            
            b2c_table = Table(b2c_table_data, repeatRows=1)
            b2c_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(b2c_table)
            elements.append(Spacer(1, 20))
        
        # HSN Summary
        if data.get('hsn'):
            elements.append(Paragraph("HSN Summary", styles['Heading3']))
            hsn_table_data = [['HSN Code', 'Description', 'Taxable Value', 'CGST', 'SGST', 'IGST', 'Total Tax']]
            
            for item in data['hsn']:
                hsn_table_data.append([
                    str(item.get('hsn_code', '')),
                    str(item.get('description', ''))[:25] + ('...' if len(str(item.get('description', ''))) > 25 else ''),
                    format_currency(item.get('taxable_value', 0)),
                    format_currency(item.get('cgst', 0)),
                    format_currency(item.get('sgst', 0)),
                    format_currency(item.get('igst', 0)),
                    format_currency(item.get('total_tax', 0)),
                ])
            
            hsn_table = Table(hsn_table_data, repeatRows=1)
            hsn_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(hsn_table)
    
    elif report_type == 'gstr3b' and isinstance(data, dict):
        # GSTR-3B Report
        elements.append(Paragraph("GSTR-3B Summary Report", title_style))
        
        # Company information
        if company:
            company_info = f"""
            <b>{company.legal_name}</b><br/>
            GSTIN: {company.gstin}<br/>
            Period: {data['company'].get('period', 'N/A')}
            """
            elements.append(Paragraph(company_info, company_style))
        
        # Outward Supplies Summary
        elements.append(Paragraph("Outward Supplies", styles['Heading3']))
        outward_data = [
            ['Description', 'Taxable Value', 'CGST', 'SGST', 'IGST', 'Total Tax'],
            [
                'Total Outward Supplies',
                format_currency(data['outward_supplies'].get('taxable_value', 0)),
                format_currency(data['outward_supplies'].get('cgst', 0)),
                format_currency(data['outward_supplies'].get('sgst', 0)),
                format_currency(data['outward_supplies'].get('igst', 0)),
                format_currency(data['outward_supplies'].get('total_tax', 0)),
            ]
        ]
        
        outward_table = Table(outward_data)
        outward_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(outward_table)
        elements.append(Spacer(1, 20))
        
        # Interstate B2C Summary
        elements.append(Paragraph("Interstate Supplies to Unregistered Persons", styles['Heading3']))
        interstate_data = [
            ['Description', 'Taxable Value', 'IGST'],
            [
                'Interstate B2C Supplies',
                format_currency(data['interstate_b2c'].get('taxable_value', 0)),
                format_currency(data['interstate_b2c'].get('igst', 0)),
            ]
        ]
        
        interstate_table = Table(interstate_data)
        interstate_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(interstate_table)
    
    else:
        # Simple list report (B2B, B2C, HSN, or transaction list)
        report_titles = {
            'b2b': 'B2B Invoices Report',
            'b2c': 'B2C Invoices Report',
            'hsn_summary': 'HSN Summary Report',
        }
        
        title = report_titles.get(report_type, 'GST Transaction Report')
        elements.append(Paragraph(title, title_style))
        
        # Company information
        if company:
            company_info = f"""
            <b>{company.legal_name}</b><br/>
            GSTIN: {company.gstin}<br/>
            Report Period: {start_date.strftime('%d-%m-%Y') if start_date else 'N/A'} to {end_date.strftime('%d-%m-%Y') if end_date else 'N/A'}
            """
            elements.append(Paragraph(company_info, company_style))
        
        # Table data
        if data and isinstance(data, list) and len(data) > 0:
            # Get headers from first item
            headers = list(data[0].keys())
            
            # Create table data with headers
            table_data = [[header.replace('_', ' ').title() for header in headers]]
            
            # Add data rows (limit to first 100 for PDF)
            for item in data[:100]:
                row = []
                for key in headers:
                    value = item.get(key, '')
                    if isinstance(value, (int, float)) and key in ['taxable_value', 'cgst', 'sgst', 'igst', 'total_tax', 'total']:
                        row.append(format_currency(value))
                    else:
                        # Truncate long text
                        str_value = str(value)
                        if len(str_value) > 20:
                            str_value = str_value[:17] + '...'
                        row.append(str_value)
                table_data.append(row)
            
            # Create table
            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No data available for the selected period.", styles['Normal']))
    
    # Add timestamp and footer
    elements.append(Spacer(1, 30))
    timestamp = Paragraph(
        f"Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
        styles['Normal']
    )
    elements.append(timestamp)
    
    # Disclaimer for large datasets
    if isinstance(data, list) and len(data) > 100:
        disclaimer = Paragraph(
            f"Note: This PDF contains the first 100 records out of {len(data)} total records. For complete data, please use Excel or CSV export.",
            ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=8, textColor=colors.red)
        )
        elements.append(Spacer(1, 10))
        elements.append(disclaimer)
    
    # Build PDF
    doc.build(elements)
    
    # Log the report generation
    if request and request.user.is_authenticated and all([start_date, end_date, report_type]):
        GSTReportLog.objects.create(
            report_type=report_type.upper(),
            start_date=start_date,
            end_date=end_date,
            file_format='PDF',
            generated_by=request.user,
        )
    
    return response
