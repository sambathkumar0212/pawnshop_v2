from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import csv
from datetime import datetime, timedelta

from .models import RiskProfile, RiskAlert, CashFlowForecast, MarketIndicator, LoanPrediction
from .services import RiskAnalytics
from accounts.models import Customer
from branches.models import Branch
from transactions.models import Loan


@login_required
def dashboard(request):
    """Main Risk Analytics Dashboard"""
    try:
        # Initialize analytics service
        analytics = RiskAnalytics()
        
        # Get portfolio health metrics
        portfolio_metrics = analytics.get_portfolio_health_metrics()
        
        # Get seasonal analysis
        seasonal_analysis = analytics.analyze_seasonal_patterns()
        
        # Get recent risk alerts
        recent_alerts = RiskAlert.objects.filter(
            status='active'
        ).order_by('-created_at')[:5]
        
        # Get high-risk customers
        high_risk_customers = RiskProfile.objects.filter(
            risk_level__in=['high', 'very_high']
        ).select_related('customer').order_by('-risk_score')[:10]
        
        context = {
            'portfolio_metrics': portfolio_metrics,
            'seasonal_analysis': seasonal_analysis,
            'recent_alerts': recent_alerts,
            'high_risk_customers': high_risk_customers,
        }
        
        return render(request, 'analytics/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return render(request, 'analytics/dashboard.html', {
            'portfolio_metrics': {'portfolio_health_score': 0, 'active_loans': 0, 'default_rate': 0, 'risk_distribution': {}},
            'seasonal_analysis': {'monthly_patterns': {}},
            'recent_alerts': [],
            'high_risk_customers': [],
        })


@login_required
def cash_flow_forecast(request):
    """Cash Flow Forecast view"""
    if request.method == 'POST':
        try:
            # Handle AJAX forecast generation
            branch_id = int(request.POST.get('branch_id'))
            time_period = request.POST.get('time_period', 'monthly')
            periods_ahead = int(request.POST.get('periods_ahead', 3))
            
            analytics = RiskAnalytics()
            forecasts = analytics.predict_cash_flow(
                branch_id=branch_id,
                time_period=time_period,
                periods_ahead=periods_ahead
            )
            
            return JsonResponse({'forecasts': forecasts})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    # GET request - show the form and recent forecasts
    branches = Branch.objects.all()
    recent_forecasts = CashFlowForecast.objects.select_related('branch').order_by('-created_at')[:10]
    
    context = {
        'branches': branches,
        'forecasts': recent_forecasts,
    }
    
    return render(request, 'analytics/cash_flow_forecast.html', context)


@login_required
def customer_risk_analysis(request, customer_id):
    """Detailed risk analysis for a specific customer"""
    customer = get_object_or_404(Customer, id=customer_id)
    
    # Calculate or get risk profile
    analytics = RiskAnalytics()
    risk_data = analytics.calculate_default_risk(customer)
    
    # Get customer's loans and payment history
    loans = customer.loans.all().order_by('-created_at')
    
    # Get any alerts for this customer
    alerts = RiskAlert.objects.filter(customer=customer).order_by('-created_at')
    
    context = {
        'customer': customer,
        'risk_data': risk_data,
        'loans': loans,
        'alerts': alerts,
    }
    
    return render(request, 'analytics/customer_risk_analysis.html', context)


@login_required
def portfolio_analysis(request):
    """Portfolio analysis view"""
    analytics = RiskAnalytics()
    
    # Get overall portfolio metrics
    portfolio_metrics = analytics.get_portfolio_health_metrics()
    
    # Get risk distribution by branch
    branch_metrics = {}
    for branch in Branch.objects.all():
        branch_metrics[branch.name] = analytics.get_portfolio_health_metrics(branch.id)
    
    # Get seasonal patterns
    seasonal_data = analytics.analyze_seasonal_patterns()
    
    context = {
        'portfolio_metrics': portfolio_metrics,
        'branch_metrics': branch_metrics,
        'seasonal_data': seasonal_data,
    }
    
    return render(request, 'analytics/portfolio_analysis.html', context)


@login_required
def risk_alerts(request):
    """Risk alerts listing"""
    alerts_list = RiskAlert.objects.all().order_by('-created_at')
    
    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter:
        alerts_list = alerts_list.filter(status=status_filter)
    
    # Filter by severity if requested
    severity_filter = request.GET.get('severity')
    if severity_filter:
        alerts_list = alerts_list.filter(severity=severity_filter)
    
    # Pagination
    paginator = Paginator(alerts_list, 25)
    page_number = request.GET.get('page')
    alerts = paginator.get_page(page_number)
    
    context = {
        'alerts': alerts,
        'status_filter': status_filter,
        'severity_filter': severity_filter,
    }
    
    return render(request, 'analytics/risk_alerts.html', context)


@login_required
def risk_alert_detail(request, alert_id):
    """Risk alert detail view"""
    alert = get_object_or_404(RiskAlert, id=alert_id)
    
    if request.method == 'POST':
        # Handle alert status updates
        action = request.POST.get('action')
        if action == 'resolve':
            alert.status = 'resolved'
            alert.resolved_at = timezone.now()
            alert.resolved_by = request.user
            alert.save()
            messages.success(request, 'Alert marked as resolved.')
        elif action == 'dismiss':
            alert.status = 'dismissed'
            alert.resolved_at = timezone.now()
            alert.resolved_by = request.user
            alert.save()
            messages.success(request, 'Alert dismissed.')
        
        return redirect('analytics:risk_alert_detail', alert_id=alert.id)
    
    context = {
        'alert': alert,
    }
    
    return render(request, 'analytics/risk_alert_detail.html', context)


@login_required
def seasonal_analysis(request):
    """Seasonal analysis view"""
    analytics = RiskAnalytics()
    seasonal_data = analytics.analyze_seasonal_patterns()
    
    # Get data by branch if requested
    branch_id = request.GET.get('branch_id')
    if branch_id:
        try:
            seasonal_data = analytics.analyze_seasonal_patterns(int(branch_id))
        except (ValueError, TypeError):
            pass
    
    branches = Branch.objects.all()
    
    context = {
        'seasonal_data': seasonal_data,
        'branches': branches,
        'selected_branch_id': branch_id,
    }
    
    return render(request, 'analytics/seasonal_analysis.html', context)


@login_required
def market_indicators(request):
    """Market indicators management"""
    indicators = MarketIndicator.objects.all().order_by('-date', 'indicator_type')
    
    # Pagination
    paginator = Paginator(indicators, 50)
    page_number = request.GET.get('page')
    indicators_page = paginator.get_page(page_number)
    
    context = {
        'indicators': indicators_page,
    }
    
    return render(request, 'analytics/market_indicators.html', context)


@login_required
def add_market_indicator(request):
    """Add new market indicator"""
    if request.method == 'POST':
        try:
            indicator_type = request.POST.get('indicator_type')
            value = float(request.POST.get('value'))
            date = datetime.strptime(request.POST.get('date'), '%Y-%m-%d').date()
            source = request.POST.get('source', '')
            notes = request.POST.get('notes', '')
            
            MarketIndicator.objects.create(
                indicator_type=indicator_type,
                value=value,
                date=date,
                source=source,
                notes=notes
            )
            
            messages.success(request, 'Market indicator added successfully.')
            return redirect('analytics:market_indicators')
            
        except Exception as e:
            messages.error(request, f'Error adding market indicator: {str(e)}')
    
    return render(request, 'analytics/add_market_indicator.html')


# API Views for AJAX calls

@login_required
@require_http_methods(["POST"])
def api_calculate_risk(request, customer_id):
    """API endpoint to calculate risk for a specific customer"""
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        analytics = RiskAnalytics()
        risk_data = analytics.calculate_default_risk(customer)
        return JsonResponse(risk_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_bulk_risk_calculation(request):
    """API endpoint for bulk risk calculation"""
    try:
        # Get all customers without recent risk profiles
        cutoff_date = timezone.now() - timedelta(days=30)
        customers_to_update = Customer.objects.filter(
            Q(risk_profile__isnull=True) | 
            Q(risk_profile__updated_at__lt=cutoff_date)
        )
        
        analytics = RiskAnalytics()
        updated_count = 0
        
        for customer in customers_to_update[:100]:  # Limit to 100 for performance
            try:
                analytics.calculate_default_risk(customer)
                updated_count += 1
            except Exception as e:
                continue
        
        return JsonResponse({
            'status': 'success',
            'updated_count': updated_count,
            'total_eligible': customers_to_update.count()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_cash_flow_forecast(request):
    """API endpoint for cash flow forecasting"""
    try:
        data = json.loads(request.body)
        branch_id = data.get('branch_id')
        time_period = data.get('time_period', 'monthly')
        periods_ahead = data.get('periods_ahead', 3)
        
        analytics = RiskAnalytics()
        forecasts = analytics.predict_cash_flow(
            branch_id=branch_id,
            time_period=time_period,
            periods_ahead=periods_ahead
        )
        
        return JsonResponse({'forecasts': forecasts})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# Export Views

@login_required
def export_risk_report(request):
    """Export risk analysis report as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="risk_analysis_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Customer ID', 'Customer Name', 'Risk Score', 'Risk Level',
        'Payment History Score', 'LTV Score', 'Demographic Score',
        'Economic Score', 'Behavioral Score', 'Last Updated'
    ])
    
    risk_profiles = RiskProfile.objects.select_related('customer').all()
    
    for profile in risk_profiles:
        writer.writerow([
            profile.customer.id,
            profile.customer.full_name,
            profile.risk_score,
            profile.get_risk_level_display(),
            profile.payment_history_score,
            profile.loan_to_value_score,
            profile.demographic_score,
            profile.economic_indicator_score,
            profile.behavioral_score,
            profile.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response


@login_required
def export_portfolio_report(request):
    """Export portfolio analysis report as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="portfolio_analysis_report.csv"'
    
    analytics = RiskAnalytics()
    portfolio_metrics = analytics.get_portfolio_health_metrics()
    
    writer = csv.writer(response)
    writer.writerow(['Metric', 'Value'])
    
    for key, value in portfolio_metrics.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                writer.writerow([f"{key}_{sub_key}", sub_value])
        else:
            writer.writerow([key, value])
    
    return response
