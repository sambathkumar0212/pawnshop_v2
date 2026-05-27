from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.DashboardListView.as_view(), name='dashboard_list'),
    path('dashboards/', views.DashboardListView.as_view(), name='dashboard_list'),
    path('dashboards/create/', views.DashboardCreateView.as_view(), name='dashboard_create'),
    path('dashboards/<int:pk>/', views.DashboardView.as_view(), name='dashboard_detail'),
    path('dashboards/<int:pk>/update/', views.DashboardUpdateView.as_view(), name='dashboard_update'),
    path('dashboards/<int:pk>/delete/', views.DashboardDeleteView.as_view(), name='dashboard_delete'),
    
    # Widget management
    path('dashboards/<int:dashboard_id>/widgets/create/', views.WidgetCreateView.as_view(), name='widget_create'),
    path('widgets/<int:pk>/update/', views.WidgetUpdateView.as_view(), name='widget_update'),
    path('widgets/<int:pk>/delete/', views.WidgetDeleteView.as_view(), name='widget_delete'),
    
    # Reports
    path('reports/', views.ReportListView.as_view(), name='report_list'),
    path('reports/create/', views.ReportCreateView.as_view(), name='report_create'),
    path('reports/<int:pk>/', views.ReportDetailView.as_view(), name='report_detail'),
    path('reports/<int:pk>/update/', views.ReportUpdateView.as_view(), name='report_update'),
    path('reports/<int:pk>/delete/', views.ReportDeleteView.as_view(), name='report_delete'),
    path('reports/<int:pk>/run/', views.ReportRunView.as_view(), name='report_run'),
    path('reports/<int:pk>/schedule/', views.ReportScheduleCreateView.as_view(), name='report_schedule'),
    path('reports/<int:pk>/download/', views.ReportDownloadView.as_view(), name='report_download'),
    path('reports/generate/', views.ReportGenerateView.as_view(), name='report_generate'),
    
    # Specific report types
    path('reports/financial/', views.FinancialReportView.as_view(), name='financial_report'),
    path('reports/inventory/', views.InventoryReportView.as_view(), name='inventory_report'),
    path('reports/loan/', views.LoanReportView.as_view(), name='loan_report'),
    path('reports/customer/', views.CustomerReportView.as_view(), name='customer_report'),
    path('reports/operational/', views.OperationalReportView.as_view(), name='operational_report'),
    
    # Specific dashboard types
    path('dashboards/financial/', views.FinancialDashboardView.as_view(), name='financial_dashboard'),
    path('dashboards/inventory/', views.InventoryDashboardView.as_view(), name='inventory_dashboard'),
    path('dashboards/loan/', views.LoanDashboardView.as_view(), name='loan_dashboard'),
    path('dashboards/customer/', views.CustomerDashboardView.as_view(), name='customer_dashboard'),
    path('dashboards/branch/', views.BranchDashboardView.as_view(), name='branch_dashboard'),
    path('dashboards/executive/', views.ExecutiveDashboardView.as_view(), name='executive_dashboard'),
    
    # Schedule management
    path('schedules/', views.ScheduleListView.as_view(), name='schedule_list'),
    path('schedules/<int:pk>/update/', views.ScheduleUpdateView.as_view(), name='schedule_update'),
    path('schedules/<int:pk>/delete/', views.ScheduleDeleteView.as_view(), name='schedule_delete'),
    
    # Report executions
    path('executions/', views.ExecutionListView.as_view(), name='execution_list'),
    path('executions/<int:pk>/', views.ExecutionDetailView.as_view(), name='execution_detail'),
    
    # Analysis tools
    path('analysis/sales/', views.SalesAnalysisView.as_view(), name='sales_analysis'),
    path('analysis/inventory/', views.InventoryAnalysisView.as_view(), name='inventory_analysis'),
    path('analysis/loans/', views.LoanAnalysisView.as_view(), name='loan_analysis'),
    path('analysis/branches/', views.BranchAnalysisView.as_view(), name='branch_analysis'),
]