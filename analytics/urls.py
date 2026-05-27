from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Main dashboard
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Risk analysis views
    path('customer-risk/<int:customer_id>/', views.customer_risk_analysis, name='customer_risk_analysis'),
    path('portfolio-analysis/', views.portfolio_analysis, name='portfolio_analysis'),
    path('risk-alerts/', views.risk_alerts, name='risk_alerts'),
    path('risk-alert/<int:alert_id>/', views.risk_alert_detail, name='risk_alert_detail'),
    
    # Cash flow and forecasting
    path('cash-flow-forecast/', views.cash_flow_forecast, name='cash_flow_forecast'),
    path('seasonal-analysis/', views.seasonal_analysis, name='seasonal_analysis'),
    
    # Market indicators
    path('market-indicators/', views.market_indicators, name='market_indicators'),
    path('market-indicators/add/', views.add_market_indicator, name='add_market_indicator'),
    
    # API endpoints for AJAX calls
    path('api/calculate-risk/<int:customer_id>/', views.api_calculate_risk, name='api_calculate_risk'),
    path('api/bulk-risk-calculation/', views.api_bulk_risk_calculation, name='api_bulk_risk_calculation'),
    path('api/cash-flow-forecast/', views.api_cash_flow_forecast, name='api_cash_flow_forecast'),
    
    # Export/Reports
    path('export/risk-report/', views.export_risk_report, name='export_risk_report'),
    path('export/portfolio-report/', views.export_portfolio_report, name='export_portfolio_report'),
]