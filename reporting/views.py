# Django imports
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q, F, Value, ExpressionWrapper, DecimalField
from django.utils import timezone
from django.http import HttpResponse, FileResponse
from decimal import Decimal

# Model imports
from transactions.models import Sale, Loan, Payment
from branches.models import Branch
from .models import Report, ReportSchedule, ReportExecution, Dashboard, DashboardWidget
from utils.download_utils import DownloadMixin

import csv
import io
from datetime import datetime, timedelta

# Placeholder views for reporting functionality
class DashboardListView(LoginRequiredMixin, DownloadMixin, ListView):
    template_name = 'reporting/dashboard_list.html'
    context_object_name = 'dashboards'
    
    def get_queryset(self):
        # Will be implemented with actual Dashboard model
        return []
    
    def get_download_filename(self):
        return f"dashboards_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
    
    def get_download_data(self):
        dashboards = self.get_queryset()
        data = []
        for dashboard in dashboards:
            data.append({
                'ID': getattr(dashboard, 'id', ''),
                'Name': getattr(dashboard, 'name', ''),
                'Description': getattr(dashboard, 'description', ''),
                'Created Date': getattr(dashboard, 'created_at', ''),
                'Status': getattr(dashboard, 'status', ''),
            })
        return data


class DashboardView(LoginRequiredMixin, DetailView):
    template_name = 'reporting/dashboard_detail.html'
    context_object_name = 'dashboard'
    
    def get_object(self):
        # Will be implemented with actual Dashboard model
        return None


class DashboardCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/dashboard_form.html'


class DashboardUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/dashboard_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dashboard_id'] = self.kwargs.get('pk')
        return context


class DashboardDeleteView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/dashboard_confirm_delete.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dashboard_id'] = self.kwargs.get('pk')
        return context


class WidgetCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/widget_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dashboard_id'] = self.kwargs.get('dashboard_id')
        return context


class WidgetUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/widget_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['widget_id'] = self.kwargs.get('pk')
        return context


class WidgetDeleteView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/widget_confirm_delete.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['widget_id'] = self.kwargs.get('pk')
        return context


class ReportListView(LoginRequiredMixin, DownloadMixin, ListView):
    template_name = 'reporting/report_list.html'
    context_object_name = 'reports'
    
    def get_queryset(self):
        # Will be implemented with actual Report model
        return []
    
    def get_download_filename(self):
        return f"reports_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
    
    def get_download_data(self):
        reports = self.get_queryset()
        data = []
        for report in reports:
            data.append({
                'ID': getattr(report, 'id', ''),
                'Name': getattr(report, 'name', ''),
                'Type': getattr(report, 'report_type', ''),
                'Created Date': getattr(report, 'created_at', ''),
                'Last Run': getattr(report, 'last_run', ''),
                'Status': getattr(report, 'status', ''),
            })
        return data


class ReportCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/report_form.html'


class ReportDetailView(LoginRequiredMixin, DetailView):
    template_name = 'reporting/report_detail.html'
    context_object_name = 'report'
    
    def get_object(self):
        # Will be implemented with actual Report model
        return None


class ReportUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/report_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['report_id'] = self.kwargs.get('pk')
        return context


class ReportDeleteView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/report_confirm_delete.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['report_id'] = self.kwargs.get('pk')
        return context

# Missing views referenced in URLs
class ReportRunView(LoginRequiredMixin, View):
    def get(self, request, pk):
        # Logic to run a report based on its ID
        messages.success(request, "Report execution started")
        return redirect('report_detail', pk=pk)


class ReportScheduleCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/report_schedule_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['report_id'] = self.kwargs.get('pk')
        return context


class ReportDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        # Logic to download report results
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="report_{pk}_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        # Sample CSV data
        writer = csv.writer(response)
        writer.writerow(['Date', 'Category', 'Amount'])
        writer.writerow([timezone.now().date(), 'Sample Category', '100.00'])
        
        return response


class ReportGenerateView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/report_generate.html'


# Specific report type views
class FinancialReportView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/financial_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add financial report specific context here
        context['title'] = 'Financial Report'
        return context


class InventoryReportView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/inventory_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add inventory report specific context here
        context['title'] = 'Inventory Report'
        return context


class LoanReportView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/loan_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add loan report specific context here
        context['title'] = 'Loan Report'
        return context


class CustomerReportView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/customer_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add customer report specific context here
        context['title'] = 'Customer Report'
        return context


class OperationalReportView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/operational_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add operational report specific context here
        context['title'] = 'Operational Report'
        return context


# Specific dashboard type views
class FinancialDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/financial_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        first_day = today.replace(day=1)
        last_month = (first_day - timedelta(days=1)).replace(day=1)
        
        # Get period from query params, default to 'month'
        period = self.request.GET.get('period', 'month')
        
        # Get the selected branch ID from request parameters
        selected_branch_id = self.request.GET.get('branch', None)
        
        # Get accessible branches based on user permissions
        accessible_branches = Branch.objects.filter(is_active=True)
        if not self.request.user.is_superuser:
            if self.request.user.branch:
                # Non-superuser with branch can only see their own branch 
                # unless they have the view_all_branches permission
                if not self.request.user.has_perm('branches.view_all_branches'):
                    accessible_branches = accessible_branches.filter(id=self.request.user.branch.id)
        
        # If branch is selected and user has access to it, filter by that branch
        branch_filter = Q()
        selected_branch = None
        
        if selected_branch_id:
            try:
                selected_branch_id = int(selected_branch_id)
                # Check if selected branch is in accessible branches
                if accessible_branches.filter(id=selected_branch_id).exists():
                    selected_branch = accessible_branches.get(id=selected_branch_id)
                    branch_filter = Q(branch=selected_branch)
            except (ValueError, Branch.DoesNotExist):
                pass
        # If no specific branch is selected but user is restricted to a branch
        elif not self.request.user.is_superuser and self.request.user.branch and not self.request.user.has_perm('branches.view_all_branches'):
            selected_branch = self.request.user.branch
            branch_filter = Q(branch=selected_branch)
        
        # Adjust date range based on selected period
        date_range = Q()
        if period == 'today':
            date_range = Q(sale_date=today)
            previous_range = Q(sale_date=today - timedelta(days=1))
            comparison_label = "vs yesterday"
        elif period == 'week':
            week_start = today - timedelta(days=today.weekday())
            date_range = Q(sale_date__gte=week_start, sale_date__lte=today)
            previous_start = week_start - timedelta(days=7)
            previous_end = week_start - timedelta(days=1)
            previous_range = Q(sale_date__gte=previous_start, sale_date__lte=previous_end)
            comparison_label = "vs last week"
        elif period == 'quarter':
            quarter_month = (today.month - 1) // 3 * 3 + 1
            quarter_start = today.replace(month=quarter_month, day=1)
            date_range = Q(sale_date__gte=quarter_start, sale_date__lte=today)
            previous_quarter_start = quarter_start.replace(month=quarter_start.month - 3)
            if previous_quarter_start.month <= 0:
                previous_quarter_start = previous_quarter_start.replace(year=previous_quarter_start.year - 1, month=previous_quarter_start.month + 12)
            previous_quarter_end = quarter_start - timedelta(days=1)
            previous_range = Q(sale_date__gte=previous_quarter_start, sale_date__lte=previous_quarter_end)
            comparison_label = "vs last quarter"
        elif period == 'year':
            year_start = today.replace(month=1, day=1)
            date_range = Q(sale_date__gte=year_start, sale_date__lte=today)
            previous_start = year_start.replace(year=year_start.year - 1)
            previous_end = today.replace(year=today.year - 1)
            previous_range = Q(sale_date__gte=previous_start, sale_date__lte=previous_end)
            comparison_label = "vs last year"
        else:  # Default to month
            date_range = Q(sale_date__year=today.year, sale_date__month=today.month)
            previous_range = Q(sale_date__year=last_month.year, sale_date__month=last_month.month)
            comparison_label = "vs last month"
        
        # Calculate revenue metrics
        current_period_sales = Sale.objects.filter(
            branch_filter,
            date_range,
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        previous_period_sales = Sale.objects.filter(
            branch_filter,
            previous_range,
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Calculate loan metrics
        loan_portfolio = Loan.objects.filter(
            branch_filter,
            status='active'
        ).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')
        
        # Compare with previous period for loans
        previous_portfolio = Loan.objects.filter(
            branch_filter,
            status='active',
            created_at__lt=first_day  # This is simplified, should be adjusted based on period
        ).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')
        
        # Get branch data for visualization
        branch_data = []
        branch_labels = []
        branch_revenue = []
        branch_colors = []
        
        for idx, branch in enumerate(accessible_branches):
            revenue = Sale.objects.filter(
                Q(branch=branch),
                date_range,
                status='completed'
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            loan_amount = Loan.objects.filter(
                Q(branch=branch),
                status='active'
            ).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')
            
            color = [
                'rgba(78, 115, 223, 0.8)',
                'rgba(28, 200, 138, 0.8)',
                'rgba(246, 194, 62, 0.8)',
                'rgba(231, 74, 59, 0.8)',
                'rgba(54, 185, 204, 0.8)'
            ][idx % 5]
            
            branch_data.append({
                'id': branch.id,
                'name': branch.name,
                'revenue': revenue,
                'loan_amount': loan_amount,
                'color': color,
                'is_selected': selected_branch and selected_branch.id == branch.id
            })
            branch_labels.append(branch.name)
            branch_revenue.append(float(revenue))  # Convert to float for JavaScript
            branch_colors.append(color)
        
        # Calculate monthly data for charts
        months = range(1, 13)
        interest_income_data = []
        sales_revenue_data = []
        other_revenue_data = []
        gross_margin_data = []
        net_margin_data = []
        
        for month in months:
            # Interest income from loans - Using Python-level calculation to handle Decimal properly
            loans = Loan.objects.filter(
                branch_filter,
                created_at__year=today.year,
                created_at__month=month
            )
            
            # Calculate interest at the Python level to handle Decimal properly
            interest = Decimal('0')
            for loan in loans:
                if loan.principal_amount and loan.interest_rate:
                    interest += loan.principal_amount * Decimal(str(loan.interest_rate)) / Decimal('100')
            
            # Sales revenue
            sales = Sale.objects.filter(
                branch_filter,
                sale_date__year=today.year,
                sale_date__month=month,
                status='completed'
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            # Other revenue (placeholder - implement based on your needs)
            other = Decimal('0')
            
            # Calculate estimated expenses (60% of revenue as placeholder)
            total_revenue = interest + sales + other
            estimated_expenses = total_revenue * Decimal('0.6')
            estimated_profit = total_revenue * Decimal('0.2')
            
            # Calculate margins
            if total_revenue > 0:
                gross_margin = ((total_revenue - estimated_expenses) / total_revenue) * Decimal('100')
                net_margin = (estimated_profit / total_revenue) * Decimal('100')
            else:
                gross_margin = Decimal('0')
                net_margin = Decimal('0')
            
            # Convert to float for JavaScript charts
            interest_income_data.append(float(interest))
            sales_revenue_data.append(float(sales))
            other_revenue_data.append(float(other))
            gross_margin_data.append(float(gross_margin))
            net_margin_data.append(float(net_margin))
        
        # Calculate growth rates - safely handle division by zero
        if previous_period_sales and previous_period_sales != 0:
            revenue_growth = ((current_period_sales - previous_period_sales) / previous_period_sales * Decimal('100'))
        else:
            revenue_growth = Decimal('0')
            
        if previous_portfolio and previous_portfolio != 0:
            portfolio_growth = ((loan_portfolio - previous_portfolio) / previous_portfolio * Decimal('100'))
        else:
            portfolio_growth = Decimal('0')
        
        # Add all data to context
        context.update({
            'total_revenue': current_period_sales,
            'revenue_growth': revenue_growth,
            'comparison_label': comparison_label,
            'net_profit': current_period_sales * Decimal('0.2'),  # Placeholder - implement actual calculation
            'profit_growth': Decimal('2.5'),  # Placeholder - implement actual calculation
            'loan_portfolio': loan_portfolio,
            'portfolio_growth': portfolio_growth,
            'expenses': current_period_sales * Decimal('0.6'),  # Placeholder - implement actual calculation
            'expense_growth': Decimal('1.8'),  # Placeholder - implement actual calculation
            
            # Chart data
            'interest_income_data': interest_income_data,
            'sales_revenue_data': sales_revenue_data,
            'other_revenue_data': other_revenue_data,
            'gross_margin_data': gross_margin_data,
            'net_margin_data': net_margin_data,
            
            # Branch data
            'branches': branch_data,
            'accessible_branches': accessible_branches,
            'branch_labels': branch_labels,
            'branch_revenue_data': branch_revenue,
            'branch_colors': branch_colors,
            'selected_branch': selected_branch,
            'selected_period': period,
            
            # Financial metrics
            'roa_current': Decimal('15.2'),  # Placeholder - implement actual calculation
            'roa_previous': Decimal('14.8'),
            'roa_change': Decimal('0.4'),
            'roa_target': Decimal('15.0'),
            
            'current_ratio': Decimal('2.1'),  # Placeholder - implement actual calculation
            'previous_ratio': Decimal('2.0'),
            'ratio_change': Decimal('0.1'),
            'ratio_target': Decimal('2.0'),
            
            'default_rate': Decimal('3.2'),  # Placeholder - implement actual calculation
            'previous_default_rate': Decimal('3.4'),
            'default_rate_change': Decimal('-0.2'),
            'default_rate_target': Decimal('3.5'),
        })
        
        return context


# Add the missing InventoryDashboardView class
class InventoryDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/inventory_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add inventory dashboard specific context here
        context['title'] = 'Inventory Dashboard'
        # Add more inventory-related metrics and data as needed
        return context


# Add other missing dashboard views
class LoanDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/loan_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        first_day = today.replace(day=1)
        last_month = (first_day - timedelta(days=1)).replace(day=1)
        
        # Get period from query params, default to 'month'
        period = self.request.GET.get('period', 'month')
        
        # Get the selected branch ID from request parameters
        selected_branch_id = self.request.GET.get('branch', None)
        
        # Get accessible branches based on user permissions
        accessible_branches = Branch.objects.filter(is_active=True)
        if not self.request.user.is_superuser:
            if self.request.user.branch:
                # Non-superuser with branch can only see their own branch 
                # unless they have the view_all_branches permission
                if not self.request.user.has_perm('branches.view_all_branches'):
                    accessible_branches = accessible_branches.filter(id=self.request.user.branch.id)
        
        # If branch is selected and user has access to it, filter by that branch
        branch_filter = Q()
        selected_branch = None
        
        if selected_branch_id:
            try:
                selected_branch_id = int(selected_branch_id)
                # Check if selected branch is in accessible branches
                if accessible_branches.filter(id=selected_branch_id).exists():
                    selected_branch = accessible_branches.get(id=selected_branch_id)
                    branch_filter = Q(branch=selected_branch)
            except (ValueError, Branch.DoesNotExist):
                pass
        # If no specific branch is selected but user is restricted to a branch
        elif not self.request.user.is_superuser and self.request.user.branch and not self.request.user.has_perm('branches.view_all_branches'):
            selected_branch = self.request.user.branch
            branch_filter = Q(branch=selected_branch)
        
        # Adjust date range based on selected period
        date_range = Q()
        previous_date_range = Q()
        
        if period == 'today':
            date_range = Q(issue_date=today)
            previous_date_range = Q(issue_date=today - timedelta(days=1))
            comparison_label = "vs yesterday"
        elif period == 'week':
            week_start = today - timedelta(days=today.weekday())
            date_range = Q(issue_date__gte=week_start, issue_date__lte=today)
            previous_start = week_start - timedelta(days=7)
            previous_end = week_start - timedelta(days=1)
            previous_date_range = Q(issue_date__gte=previous_start, issue_date__lte=previous_end)
            comparison_label = "vs last week"
        elif period == 'quarter':
            quarter_month = (today.month - 1) // 3 * 3 + 1
            quarter_start = today.replace(month=quarter_month, day=1)
            date_range = Q(issue_date__gte=quarter_start, issue_date__lte=today)
            previous_quarter_start = quarter_start.replace(month=quarter_start.month - 3)
            if previous_quarter_start.month <= 0:
                previous_quarter_start = previous_quarter_start.replace(year=previous_quarter_start.year - 1, month=previous_quarter_start.month + 12)
            previous_quarter_end = quarter_start - timedelta(days=1)
            previous_date_range = Q(issue_date__gte=previous_quarter_start, issue_date__lte=previous_quarter_end)
            comparison_label = "vs last quarter"
        elif period == 'year':
            year_start = today.replace(month=1, day=1)
            date_range = Q(issue_date__gte=year_start, issue_date__lte=today)
            previous_start = year_start.replace(year=year_start.year - 1)
            previous_end = today.replace(year=today.year - 1)
            previous_date_range = Q(issue_date__gte=previous_start, issue_date__lte=previous_end)
            comparison_label = "vs last year"
        else:  # Default to month
            date_range = Q(issue_date__year=today.year, issue_date__month=today.month)
            previous_date_range = Q(issue_date__year=last_month.year, issue_date__month=last_month.month)
            comparison_label = "vs last month"
        
        # Active loans count
        active_loans_count = Loan.objects.filter(
            branch_filter,
            status='active'
        ).count()
        
        # Previous period active loans count
        previous_active_loans = Loan.objects.filter(
            branch_filter,
            status='active',
            issue_date__lt=first_day
        ).count()
        
        # Calculate active loans growth
        if previous_active_loans > 0:
            active_loans_growth = ((active_loans_count - previous_active_loans) / previous_active_loans) * 100
        else:
            active_loans_growth = 0
        
        # Loan portfolio value (total principal of active loans)
        loan_portfolio_value = Loan.objects.filter(
            branch_filter,
            status='active'
        ).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')
        
        # Previous period loan portfolio value
        previous_portfolio_value = Loan.objects.filter(
            branch_filter,
            status='active',
            issue_date__lt=first_day
        ).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')
        
        # Calculate portfolio growth
        if previous_portfolio_value > 0:
            portfolio_growth = ((loan_portfolio_value - previous_portfolio_value) / previous_portfolio_value) * 100
        else:
            portfolio_growth = 0
        
        # Calculate interest income (estimate based on active loans)
        interest_income = Decimal('0')
        for loan in Loan.objects.filter(branch_filter, status='active'):
            if hasattr(loan, 'monthly_interest') and callable(getattr(loan, 'monthly_interest')):
                interest_info = loan.monthly_interest()
                if interest_info and 'amount' in interest_info:
                    interest_income += interest_info['amount']
        
        # Previous period interest income (simplified)
        previous_interest_income = interest_income * Decimal('0.9')  # Placeholder
        
        # Calculate interest growth
        if previous_interest_income > 0:
            interest_growth = ((interest_income - previous_interest_income) / previous_interest_income) * 100
        else:
            interest_growth = 0
        
        # Calculate default rate
        total_loans = Loan.objects.filter(branch_filter).count()
        defaulted_loans = Loan.objects.filter(branch_filter, status='defaulted').count()
        
        if total_loans > 0:
            default_rate = (defaulted_loans / total_loans) * 100
        else:
            default_rate = 0
            
        # Previous default rate
        previous_defaulted = defaulted_loans - 1 if defaulted_loans > 1 else 0  # Placeholder
        previous_total = total_loans - 5 if total_loans > 5 else 1  # Placeholder
        previous_default_rate = (previous_defaulted / previous_total) * 100 if previous_total > 0 else 0
        
        # Calculate default rate change
        default_rate_change = default_rate - previous_default_rate
        
        # Get monthly loan disbursement data
        months = range(1, 13)
        loan_count_data = []
        loan_value_data = []
        
        for month in months:
            month_loans = Loan.objects.filter(
                branch_filter,
                issue_date__year=today.year,
                issue_date__month=month
            )
            
            loan_count = month_loans.count()
            loan_value = month_loans.aggregate(total=Sum('principal_amount'))['total'] or 0
            
            loan_count_data.append(loan_count)
            loan_value_data.append(float(loan_value))
        
        # Get loan status distribution
        active_count = Loan.objects.filter(branch_filter, status='active').count()
        repaid_count = Loan.objects.filter(branch_filter, status='repaid').count()
        extended_count = Loan.objects.filter(branch_filter, status='extended').count()
        defaulted_count = Loan.objects.filter(branch_filter, status='defaulted').count()
        
        loan_status_data = [active_count, repaid_count, extended_count, defaulted_count]
        
        # Calculate branch distribution
        branch_loan_data = []
        branch_labels = []
        branch_colors = []
        
        for idx, branch in enumerate(accessible_branches):
            loan_count = Loan.objects.filter(Q(branch=branch), status='active').count()
            
            color = [
                'rgba(78, 115, 223, 0.8)',
                'rgba(28, 200, 138, 0.8)',
                'rgba(246, 194, 62, 0.8)',
                'rgba(231, 74, 59, 0.8)',
                'rgba(54, 185, 204, 0.8)'
            ][idx % 5]
            
            branch_loan_data.append(loan_count)
            branch_labels.append(branch.name)
            branch_colors.append(color)
        
        # Calculate loan performance metrics
        avg_loan_amount = Loan.objects.filter(branch_filter).aggregate(avg=Avg('principal_amount'))['avg'] or Decimal('0')
        prev_avg_loan_amount = avg_loan_amount * Decimal('0.95')  # Placeholder
        avg_loan_amount_change = ((avg_loan_amount - prev_avg_loan_amount) / prev_avg_loan_amount * 100) if prev_avg_loan_amount > 0 else 0
        avg_loan_amount_target = avg_loan_amount * Decimal('1.05')  # Placeholder
        
        # Repayment rate
        total_due = Loan.objects.filter(branch_filter, status__in=['repaid', 'active', 'defaulted']).count()
        repaid = Loan.objects.filter(branch_filter, status='repaid').count()
        repayment_rate = (repaid / total_due * 100) if total_due > 0 else 0
        
        prev_repayment_rate = repayment_rate - 2  # Placeholder
        repayment_rate_change = repayment_rate - prev_repayment_rate
        repayment_rate_target = 85  # Placeholder
        
        # Extension rate
        extensions = Loan.objects.filter(branch_filter, status='extended').count()
        extension_rate = (extensions / total_due * 100) if total_due > 0 else 0
        
        prev_extension_rate = extension_rate + 1  # Placeholder
        extension_rate_change = extension_rate - prev_extension_rate
        extension_rate_target = 15  # Placeholder
        
        # Prepare branch data with loan info
        branches_with_data = []
        for idx, branch in enumerate(accessible_branches):
            loan_count = Loan.objects.filter(Q(branch=branch), status='active').count()
            loan_value = Loan.objects.filter(
                Q(branch=branch), 
                status='active'
            ).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')
            
            color = [
                'rgba(78, 115, 223, 0.8)',
                'rgba(28, 200, 138, 0.8)',
                'rgba(246, 194, 62, 0.8)',
                'rgba(231, 74, 59, 0.8)',
                'rgba(54, 185, 204, 0.8)'
            ][idx % 5]
            
            branches_with_data.append({
                'id': branch.id,
                'name': branch.name,
                'loan_count': loan_count,
                'loan_value': loan_value,
                'color': color,
                'is_selected': selected_branch and selected_branch.id == branch.id
            })
        
        # Add data to context
        context.update({
            'title': 'Loan Dashboard',
            'comparison_label': comparison_label,
            'selected_branch': selected_branch,
            'selected_period': period,
            'accessible_branches': accessible_branches,
            
            # Quick stats
            'active_loans_count': active_loans_count,
            'active_loans_growth': active_loans_growth,
            'loan_portfolio_value': loan_portfolio_value,
            'portfolio_growth': portfolio_growth,
            'interest_income': interest_income,
            'interest_growth': interest_growth,
            'default_rate': default_rate,
            'default_rate_change': default_rate_change,
            
            # Chart data
            'loan_count_data': loan_count_data,
            'loan_value_data': loan_value_data,
            'loan_status_data': loan_status_data,
            'branch_loan_data': branch_loan_data,
            'branch_labels': branch_labels,
            'branch_colors': branch_colors,
            
            # Performance metrics
            'avg_loan_amount': avg_loan_amount,
            'prev_avg_loan_amount': prev_avg_loan_amount,
            'avg_loan_amount_change': avg_loan_amount_change,
            'avg_loan_amount_target': avg_loan_amount_target,
            
            'repayment_rate': repayment_rate,
            'prev_repayment_rate': prev_repayment_rate,
            'repayment_rate_change': repayment_rate_change,
            'repayment_rate_target': repayment_rate_target,
            
            'extension_rate': extension_rate,
            'prev_extension_rate': prev_extension_rate,
            'extension_rate_change': extension_rate_change,
            'extension_rate_target': extension_rate_target,
            
            # Branch data
            'branches': branches_with_data,
        })
        
        return context


class CustomerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/customer_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        first_day = today.replace(day=1)
        last_month = (first_day - timedelta(days=1)).replace(day=1)
        
        # Import the Customer model from accounts app
        from accounts.models import Customer
        
        # Get period from query params, default to 'month'
        period = self.request.GET.get('period', 'month')
        
        # Get the selected branch ID from request parameters
        selected_branch_id = self.request.GET.get('branch', None)
        
        # Get accessible branches based on user permissions
        accessible_branches = Branch.objects.filter(is_active=True)
        if not self.request.user.is_superuser:
            if self.request.user.branch:
                # Non-superuser with branch can only see their own branch 
                # unless they have the view_all_branches permission
                if not self.request.user.has_perm('branches.view_all_branches'):
                    accessible_branches = accessible_branches.filter(id=self.request.user.branch.id)
        
        # If branch is selected and user has access to it, filter by that branch
        branch_filter = Q()
        selected_branch = None
        
        if selected_branch_id:
            try:
                selected_branch_id = int(selected_branch_id)
                # Check if selected branch is in accessible branches
                if accessible_branches.filter(id=selected_branch_id).exists():
                    selected_branch = accessible_branches.get(id=selected_branch_id)
                    branch_filter = Q(branch=selected_branch)
            except (ValueError, Branch.DoesNotExist):
                pass
        # If no specific branch is selected but user is restricted to a branch
        elif not self.request.user.is_superuser and self.request.user.branch and not self.request.user.has_perm('branches.view_all_branches'):
            selected_branch = self.request.user.branch
            branch_filter = Q(branch=selected_branch)
        
        # Adjust date range based on selected period
        date_range = Q()
        previous_date_range = Q()
        
        if period == 'today':
            date_range = Q(created_at__date=today)
            previous_date_range = Q(created_at__date=today - timedelta(days=1))
            comparison_label = "vs yesterday"
        elif period == 'week':
            week_start = today - timedelta(days=today.weekday())
            date_range = Q(created_at__date__gte=week_start, created_at__date__lte=today)
            previous_start = week_start - timedelta(days=7)
            previous_end = week_start - timedelta(days=1)
            previous_date_range = Q(created_at__date__gte=previous_start, created_at__date__lte=previous_end)
            comparison_label = "vs last week"
        elif period == 'quarter':
            quarter_month = (today.month - 1) // 3 * 3 + 1
            quarter_start = today.replace(month=quarter_month, day=1)
            date_range = Q(created_at__date__gte=quarter_start, created_at__date__lte=today)
            previous_quarter_start = quarter_start.replace(month=quarter_start.month - 3)
            if previous_quarter_start.month <= 0:
                previous_quarter_start = previous_quarter_start.replace(year=previous_quarter_start.year - 1, month=previous_quarter_start.month + 12)
            previous_quarter_end = quarter_start - timedelta(days=1)
            previous_date_range = Q(created_at__date__gte=previous_quarter_start, created_at__date__lte=previous_quarter_end)
            comparison_label = "vs last quarter"
        elif period == 'year':
            year_start = today.replace(month=1, day=1)
            date_range = Q(created_at__date__gte=year_start, created_at__date__lte=today)
            previous_start = year_start.replace(year=year_start.year - 1)
            previous_end = today.replace(year=today.year - 1)
            previous_date_range = Q(created_at__date__gte=previous_start, created_at__date__lte=previous_end)
            comparison_label = "vs last year"
        else:  # Default to month
            date_range = Q(created_at__date__year=today.year, created_at__date__month=today.month)
            previous_date_range = Q(created_at__date__year=last_month.year, created_at__date__month=last_month.month)
            comparison_label = "vs last month"
        
        # Total customers count
        total_customers = Customer.objects.filter(branch_filter).count()
        
        # New customers in the current period
        new_customers = Customer.objects.filter(branch_filter, date_range).count()
        
        # New customers in the previous period
        previous_new_customers = Customer.objects.filter(branch_filter, previous_date_range).count()
        
        # Calculate customer growth
        if previous_new_customers > 0:
            new_customer_growth = ((new_customers - previous_new_customers) / previous_new_customers) * 100
        else:
            new_customer_growth = 0
            
        # Calculate total customer growth (this month vs last month)
        previous_total = Customer.objects.filter(
            branch_filter, 
            created_at__lt=first_day
        ).count()
        
        if previous_total > 0:
            customer_growth = ((total_customers - previous_total) / previous_total) * 100
        else:
            customer_growth = 0
        
        # Active customers (with active loans)
        active_customers = Customer.objects.filter(
            branch_filter,
            loans__status='active'
        ).distinct().count()
        
        # Previous period active customers
        previous_active = Customer.objects.filter(
            branch_filter,
            loans__status='active',
            loans__issue_date__lt=first_day
        ).distinct().count() or 1  # Avoid division by zero
        
        # Calculate active rate change
        active_rate_change = ((active_customers - previous_active) / previous_active) * 100
        
        # Calculate retention rate (simplified version)
        # Retention is defined as customers who have done more than one transaction
        total_transaction_customers = Customer.objects.filter(
            branch_filter,
            loans__isnull=False
        ).distinct().count()
        
        repeat_customers = Customer.objects.filter(
            branch_filter,
            loans__isnull=False
        ).annotate(
            loan_count=Count('loans')
        ).filter(
            loan_count__gt=1
        ).count()
        
        if total_transaction_customers > 0:
            retention_rate = (repeat_customers / total_transaction_customers) * 100
        else:
            retention_rate = 0
            
        # Previous retention rate (simplified)
        prev_retention_rate = retention_rate - 2 if retention_rate > 2 else retention_rate
        retention_rate_change = retention_rate - prev_retention_rate
        
        # Get monthly customer acquisition data
        months = range(1, 13)
        customer_acquisition_data = []
        retention_rate_data = []
        
        for month in months:
            month_customers = Customer.objects.filter(
                branch_filter,
                created_at__year=today.year,
                created_at__month=month
            ).count()
            
            # For simplicity, use placeholder data for monthly retention
            # In a real implementation, you'd calculate this per month
            month_retention = 90 - ((month % 5) * 2)  # Sample data between 80-90%
            
            customer_acquisition_data.append(month_customers)
            retention_rate_data.append(month_retention)
        
        # Get gender demographics if available in your model
        # This is simplified - you'll need to adjust based on your model structure
        males = females = others = 0
        
        try:
            # If you have a gender field, uncomment this
            # males = Customer.objects.filter(branch_filter, gender='male').count()
            # females = Customer.objects.filter(branch_filter, gender='female').count()
            # others = total_customers - males - females
            
            # For now, just use sample data
            males = int(total_customers * 0.6)
            females = int(total_customers * 0.35)
            others = total_customers - males - females
        except:
            # If gender field doesn't exist or another error occurs
            males = int(total_customers * 0.6)
            females = int(total_customers * 0.35)
            others = total_customers - males - females
        
        demographics_data = [males, females, others]
        
        # Calculate branch distribution
        branch_customer_data = []
        branch_labels = []
        branch_colors = []
        
        for idx, branch in enumerate(accessible_branches):
            customer_count = Customer.objects.filter(Q(branch=branch)).count()
            
            color = [
                'rgba(78, 115, 223, 0.8)',
                'rgba(28, 200, 138, 0.8)',
                'rgba(246, 194, 62, 0.8)',
                'rgba(231, 74, 59, 0.8)',
                'rgba(54, 185, 204, 0.8)'
            ][idx % 5]
            
            branch_customer_data.append(customer_count)
            branch_labels.append(branch.name)
            branch_colors.append(color)
        
        # Calculate customer segments
        # New customers (last 30 days)
        new_customers_date = today - timedelta(days=30)
        new_customers_count = Customer.objects.filter(
            branch_filter, 
            created_at__gte=new_customers_date
        ).count()
        
        # Regular customers (2+ transactions)
        regular_customers_count = Customer.objects.filter(
            branch_filter
        ).annotate(
            loan_count=Count('loans')
        ).filter(
            loan_count__gte=2,
            loan_count__lt=5
        ).count()
        
        # Premium customers (5+ transactions)
        premium_customers_count = Customer.objects.filter(
            branch_filter
        ).annotate(
            loan_count=Count('loans')
        ).filter(
            loan_count__gte=5
        ).count()
        
        # Calculate segment percentages
        if total_customers > 0:
            new_customers_percent = (new_customers_count / total_customers) * 100
            regular_customers_percent = (regular_customers_count / total_customers) * 100
            premium_customers_percent = (premium_customers_count / total_customers) * 100
        else:
            new_customers_percent = 0
            regular_customers_percent = 0
            premium_customers_percent = 0
        
        # Calculate average loan values by segment
        # New customers
        new_customers_avg_loan = Loan.objects.filter(
            branch_filter,
            customer__created_at__gte=new_customers_date
        ).aggregate(avg=Avg('principal_amount'))['avg'] or Decimal('0')
        
        # Regular customers
        regular_customers_avg_loan = Loan.objects.filter(
            branch_filter,
            customer__in=Customer.objects.filter(
                branch_filter
            ).annotate(
                loan_count=Count('loans')
            ).filter(
                loan_count__gte=2,
                loan_count__lt=5
            )
        ).aggregate(avg=Avg('principal_amount'))['avg'] or Decimal('0')
        
        # Premium customers
        premium_customers_avg_loan = Loan.objects.filter(
            branch_filter,
            customer__in=Customer.objects.filter(
                branch_filter
            ).annotate(
                loan_count=Count('loans')
            ).filter(
                loan_count__gte=5
            )
        ).aggregate(avg=Avg('principal_amount'))['avg'] or Decimal('0')
        
        # Calculate average transactions by segment
        new_customers_avg_trans = 1.0
        
        regular_customers_avg_trans = Customer.objects.filter(
            branch_filter
        ).annotate(
            loan_count=Count('loans')
        ).filter(
            loan_count__gte=2,
            loan_count__lt=5
        ).aggregate(avg=Avg('loan_count'))['avg'] or 0
        
        premium_customers_avg_trans = Customer.objects.filter(
            branch_filter
        ).annotate(
            loan_count=Count('loans')
        ).filter(
            loan_count__gte=5
        ).aggregate(avg=Avg('loan_count'))['avg'] or 0
        
        # Retention rates by segment (simplified)
        new_customers_retention = 70.0  # Placeholder
        regular_customers_retention = 85.0  # Placeholder
        premium_customers_retention = 95.0  # Placeholder
        
        # Prepare branch data
        branches_with_data = []
        for idx, branch in enumerate(accessible_branches):
            customer_count = Customer.objects.filter(Q(branch=branch)).count()
            new_customers_count = Customer.objects.filter(
                Q(branch=branch), 
                created_at__gte=new_customers_date
            ).count()
            
            color = [
                'rgba(78, 115, 223, 0.8)',
                'rgba(28, 200, 138, 0.8)',
                'rgba(246, 194, 62, 0.8)',
                'rgba(231, 74, 59, 0.8)',
                'rgba(54, 185, 204, 0.8)'
            ][idx % 5]
            
            branches_with_data.append({
                'id': branch.id,
                'name': branch.name,
                'customer_count': customer_count,
                'new_customers': new_customers_count,
                'color': color,
                'is_selected': selected_branch and selected_branch.id == branch.id
            })
        
        # Add data to context
        context.update({
            'title': 'Customer Dashboard',
            'comparison_label': comparison_label,
            'selected_branch': selected_branch,
            'selected_period': period,
            'accessible_branches': accessible_branches,
            
            # Quick stats
            'total_customers': total_customers,
            'customer_growth': customer_growth,
            'new_customers': new_customers,
            'new_customer_growth': new_customer_growth,
            'active_customers': active_customers,
            'active_rate_change': active_rate_change,
            'retention_rate': retention_rate,
            'retention_rate_change': retention_rate_change,
            
            # Chart data
            'customer_acquisition_data': customer_acquisition_data,
            'retention_rate_data': retention_rate_data,
            'demographics_data': demographics_data,
            'branch_customer_data': branch_customer_data,
            'branch_labels': branch_labels,
            'branch_colors': branch_colors,
            
            # Customer segments
            'new_customers_count': new_customers_count,
            'new_customers_percent': new_customers_percent,
            'new_customers_avg_loan': new_customers_avg_loan,
            'new_customers_avg_trans': new_customers_avg_trans,
            'new_customers_retention': new_customers_retention,
            
            'regular_customers_count': regular_customers_count,
            'regular_customers_percent': regular_customers_percent,
            'regular_customers_avg_loan': regular_customers_avg_loan,
            'regular_customers_avg_trans': regular_customers_avg_trans,
            'regular_customers_retention': regular_customers_retention,
            
            'premium_customers_count': premium_customers_count,
            'premium_customers_percent': premium_customers_percent,
            'premium_customers_avg_loan': premium_customers_avg_loan,
            'premium_customers_avg_trans': premium_customers_avg_trans,
            'premium_customers_retention': premium_customers_retention,
            
            # Branch data
            'branches': branches_with_data,
        })
        
        return context


class BranchDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/branch_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        first_day = today.replace(day=1)
        last_month = (first_day - timedelta(days=1)).replace(day=1)
        
        # Get period from query params, default to 'month'
        period = self.request.GET.get('period', 'month')
        
        # Get the selected branch ID from request parameters
        selected_branch_id = self.request.GET.get('branch', None)
        
        # Get accessible branches based on user permissions
        accessible_branches = Branch.objects.filter(is_active=True)
        if not self.request.user.is_superuser:
            if self.request.user.branch:
                # Non-superuser with branch can only see their own branch 
                # unless they have the view_all_branches permission
                if not self.request.user.has_perm('branches.view_all_branches'):
                    accessible_branches = accessible_branches.filter(id=self.request.user.branch.id)
        
        # If branch is selected and user has access to it, filter by that branch
        branch_filter = Q()
        selected_branch = None
        
        if selected_branch_id:
            try:
                selected_branch_id = int(selected_branch_id)
                # Check if selected branch is in accessible branches
                if accessible_branches.filter(id=selected_branch_id).exists():
                    selected_branch = accessible_branches.get(id=selected_branch_id)
                    branch_filter = Q(id=selected_branch.id)
            except (ValueError, Branch.DoesNotExist):
                pass
        # If no specific branch is selected but user is restricted to a branch
        elif not self.request.user.is_superuser and self.request.user.branch and not self.request.user.has_perm('branches.view_all_branches'):
            selected_branch = self.request.user.branch
            branch_filter = Q(id=selected_branch.id)
        
        # Adjust date range based on selected period
        date_range = Q()
        previous_date_range = Q()
        
        if period == 'today':
            date_range = Q(created_at__date=today)
            previous_date_range = Q(created_at__date=today - timedelta(days=1))
            comparison_label = "vs yesterday"
        elif period == 'week':
            week_start = today - timedelta(days=today.weekday())
            date_range = Q(created_at__date__gte=week_start, created_at__date__lte=today)
            previous_start = week_start - timedelta(days=7)
            previous_end = week_start - timedelta(days=1)
            previous_date_range = Q(created_at__date__gte=previous_start, created_at__date__lte=previous_end)
            comparison_label = "vs last week"
        elif period == 'quarter':
            quarter_month = (today.month - 1) // 3 * 3 + 1
            quarter_start = today.replace(month=quarter_month, day=1)
            date_range = Q(created_at__date__gte=quarter_start, created_at__date__lte=today)
            previous_quarter_start = quarter_start.replace(month=quarter_start.month - 3)
            if previous_quarter_start.month <= 0:
                previous_quarter_start = previous_quarter_start.replace(year=previous_quarter_start.year - 1, month=previous_quarter_start.month + 12)
            previous_quarter_end = quarter_start - timedelta(days=1)
            previous_date_range = Q(created_at__date__gte=previous_quarter_start, created_at__date__lte=previous_quarter_end)
            comparison_label = "vs last quarter"
        elif period == 'year':
            year_start = today.replace(month=1, day=1)
            date_range = Q(created_at__date__gte=year_start, created_at__date__lte=today)
            previous_start = year_start.replace(year=year_start.year - 1)
            previous_end = today.replace(year=today.year - 1)
            previous_date_range = Q(created_at__date__gte=previous_start, created_at__date__lte=previous_end)
            comparison_label = "vs last year"
        else:  # Default to month
            date_range = Q(created_at__date__year=today.year, created_at__date__month=today.month)
            previous_date_range = Q(created_at__date__year=last_month.year, created_at__date__month=last_month.month)
            comparison_label = "vs last month"
        
        # Import User model for staff counts
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Import Customer model for customer counts
        from accounts.models import Customer
        
        # Total branches count
        total_branches = accessible_branches.count()
        
        # New branches in the current period (if branch creation date is tracked)
        new_branches = accessible_branches.filter(date_range).count()
        
        # Branch growth calculation
        previous_branches_count = accessible_branches.filter(previous_date_range).count()
        
        if previous_branches_count > 0:
            branch_growth = ((total_branches - previous_branches_count) / previous_branches_count) * 100
        else:
            branch_growth = 0 if total_branches == 0 else 100
            
        # Staff counts
        total_staff = User.objects.filter(is_active=True).count()
        
        # Calculate staff growth (simplified)
        previous_staff = User.objects.filter(is_active=True, date_joined__lt=first_day).count()
        
        if previous_staff > 0:
            staff_growth = ((total_staff - previous_staff) / previous_staff) * 100
        else:
            staff_growth = 0
            
        # Transaction counts (combining loans and sales)
        total_transactions = Loan.objects.filter().count() + Sale.objects.filter().count()
        
        # Calculate transaction growth
        previous_transactions = (
            Loan.objects.filter(created_at__lt=first_day).count() + 
            Sale.objects.filter(sale_date__lt=first_day).count()
        )
        
        if previous_transactions > 0:
            transaction_growth = ((total_transactions - previous_transactions) / previous_transactions) * 100
        else:
            transaction_growth = 0
            
        # Active customers count
        active_customers = Customer.objects.filter(loans__status='active').distinct().count()
        
        # Calculate customer growth
        previous_customers = Customer.objects.filter(created_at__lt=first_day).count()
        
        if previous_customers > 0:
            customer_growth = ((active_customers - previous_customers) / previous_customers) * 100
        else:
            customer_growth = 0
            
        # Generate monthly branch performance data
        months = range(1, 13)
        revenue_data = []
        loans_data = []
        customers_data = []
        
        for month in months:
            # Monthly revenue data (from sales)
            month_revenue = Sale.objects.filter(
                sale_date__year=today.year,
                sale_date__month=month,
                status='completed'
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            # Monthly loan data
            month_loans = Loan.objects.filter(
                issue_date__year=today.year,
                issue_date__month=month
            ).count()
            
            # Monthly customer data
            month_customers = Customer.objects.filter(
                created_at__year=today.year,
                created_at__month=month
            ).count()
            
            revenue_data.append(float(month_revenue))
            loans_data.append(month_loans)
            customers_data.append(month_customers)
            
        # Calculate revenue distribution (loan interest vs sales)
        # For simplicity, we'll use a placeholder ratio - adjust based on your business model
        loan_revenue_pct = 60
        sales_revenue_pct = 30
        other_revenue_pct = 10
        
        revenue_distribution = [loan_revenue_pct, sales_revenue_pct, other_revenue_pct]
        
        # Branch comparison data
        branch_comparison = []
        branch_labels = []
        branch_colors = []
        staff_distribution = []
        
        for idx, branch in enumerate(accessible_branches):
            # Revenue for this branch
            branch_revenue = Sale.objects.filter(
                branch=branch,
                sale_date__year=today.year,
                sale_date__month=today.month,
                status='completed'
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            # Loans for this branch
            branch_loans = Loan.objects.filter(
                branch=branch,
                status='active'
            ).count()
            
            # Customers for this branch
            branch_customers = Customer.objects.filter(branch=branch).count()
            
            # Staff for this branch
            branch_staff = User.objects.filter(branch=branch, is_active=True).count()
            
            # Performance score (simplified calculation)
            # Scoring based on revenue, customer acquisition, loan performance
            # Adjust weights based on your business priorities
            if branch_customers > 0:
                avg_revenue_per_customer = float(branch_revenue) / branch_customers
            else:
                avg_revenue_per_customer = 0
                
            # Sample performance calculation - adjust based on your KPIs
            performance_score = min(100, max(0, (
                (float(branch_revenue) / 10000 * 40) +  # 40% weight to revenue
                (branch_customers / 100 * 30) +          # 30% weight to customer base
                (branch_loans / 50 * 20) +               # 20% weight to active loans
                (avg_revenue_per_customer / 1000 * 10)   # 10% weight to revenue per customer
            )))
            
            color = [
                'rgba(78, 115, 223, 0.8)',
                'rgba(28, 200, 138, 0.8)',
                'rgba(246, 194, 62, 0.8)',
                'rgba(231, 74, 59, 0.8)',
                'rgba(54, 185, 204, 0.8)'
            ][idx % 5]
            
            branch_comparison.append({
                'name': branch.name,
                'revenue': branch_revenue,
                'loans': branch_loans,
                'customers': branch_customers,
                'staff': branch_staff,
                'performance': performance_score
            })
            
            branch_labels.append(branch.name)
            branch_colors.append(color)
            staff_distribution.append(branch_staff)
            
        # Prepare branch data
        branches_with_data = []
        for idx, branch in enumerate(accessible_branches):
            # Get active loans count for this branch
            branch_loan_count = Loan.objects.filter(
                branch=branch,
                status='active'
            ).count()
            
            # Get customer count for this branch
            branch_customer_count = Customer.objects.filter(branch=branch).count()
            
            # Get staff count for this branch
            branch_staff_count = User.objects.filter(branch=branch, is_active=True).count()
            
            color = [
                'rgba(78, 115, 223, 0.8)',
                'rgba(28, 200, 138, 0.8)',
                'rgba(246, 194, 62, 0.8)',
                'rgba(231, 74, 59, 0.8)',
                'rgba(54, 185, 204, 0.8)'
            ][idx % 5]
            
            branches_with_data.append({
                'id': branch.id,
                'name': branch.name,
                'loan_count': branch_loan_count,
                'customer_count': branch_customer_count,
                'staff_count': branch_staff_count,
                'color': color,
                'is_selected': selected_branch and selected_branch.id == branch.id
            })
            
        # Add data to context
        context.update({
            'title': 'Branch Dashboard',
            'comparison_label': comparison_label,
            'selected_branch': selected_branch,
            'selected_period': period,
            'accessible_branches': accessible_branches,
            
            # Quick stats
            'total_branches': total_branches,
            'branch_growth': branch_growth,
            'total_staff': total_staff,
            'staff_growth': staff_growth,
            'total_transactions': total_transactions,
            'transaction_growth': transaction_growth,
            'active_customers': active_customers,
            'customer_growth': customer_growth,
            
            # Chart data
            'revenue_data': revenue_data,
            'loans_data': loans_data,
            'customers_data': customers_data,
            'revenue_distribution': revenue_distribution,
            
            # Branch comparison
            'branch_comparison': branch_comparison,
            'branch_labels': branch_labels,
            'branch_colors': branch_colors,
            'staff_distribution': staff_distribution,
            
            # Branch data
            'branches': branches_with_data,
        })
        
        return context


class ExecutiveDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/executive_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Executive Dashboard'
        return context


# Add missing schedule related views
class ScheduleListView(LoginRequiredMixin, ListView):
    template_name = 'reporting/schedule_list.html'
    context_object_name = 'schedules'
    
    def get_queryset(self):
        # Will be implemented with actual ReportSchedule model
        return []


class ScheduleUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/schedule_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['schedule_id'] = self.kwargs.get('pk')
        return context


class ScheduleDeleteView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/schedule_confirm_delete.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['schedule_id'] = self.kwargs.get('pk')
        return context


# Add missing execution related views
class ExecutionListView(LoginRequiredMixin, ListView):
    template_name = 'reporting/execution_list.html'
    context_object_name = 'executions'
    
    def get_queryset(self):
        # Will be implemented with actual ReportExecution model
        return []


class ExecutionDetailView(LoginRequiredMixin, DetailView):
    template_name = 'reporting/execution_detail.html'
    context_object_name = 'execution'
    
    def get_object(self):
        # Will be implemented with actual ReportExecution model
        return None


# Add missing analysis views
class SalesAnalysisView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/sales_analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Sales Analysis'
        return context


class InventoryAnalysisView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/inventory_analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Inventory Analysis'
        return context


class LoanAnalysisView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/loan_analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Loan Analysis'
        return context


class BranchAnalysisView(LoginRequiredMixin, TemplateView):
    template_name = 'reporting/branch_analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Branch Analysis'
        return context
