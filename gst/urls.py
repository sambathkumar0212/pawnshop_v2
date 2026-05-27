from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.gst_dashboard, name='gst_dashboard'),
    
    # GST Rates
    path('rates/', views.GSTRateListView.as_view(), name='gst_rate_list'),
    path('rates/add/', views.GSTRateCreateView.as_view(), name='gst_rate_create'),
    path('rates/<int:pk>/edit/', views.GSTRateUpdateView.as_view(), name='gst_rate_update'),
    path('rates/<int:pk>/toggle/', views.gst_rate_toggle_active, name='gst_rate_toggle_active'),
    
    # GST Transactions
    path('transactions/', views.GSTTransactionListView.as_view(), name='gst_transaction_list'),
    path('transactions/add/', views.GSTTransactionCreateView.as_view(), name='gst_transaction_create'),
    path('transactions/<int:pk>/', views.GSTTransactionDetailView.as_view(), name='gst_transaction_detail'),
    path('transactions/<int:pk>/edit/', views.GSTTransactionUpdateView.as_view(), name='gst_transaction_update'),
    path('transactions/<int:pk>/delete/', views.gst_transaction_delete, name='gst_transaction_delete'),
    
    # GST Rate API
    path('api/rate-details/', views.get_gst_rate_details, name='get_gst_rate_details'),
    
    # Company GST Details
    path('company/<int:pk>/', views.company_gst_details_update, name='company_gst_details_update'),
    
    # GST Reports
    path('reports/', views.gst_report, name='gst_report'),
]