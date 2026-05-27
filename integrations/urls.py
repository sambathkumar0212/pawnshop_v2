from django.urls import path
from . import views

urlpatterns = [
    # Integration management
    path('', views.IntegrationListView.as_view(), name='integration_list'),
    path('add/', views.IntegrationCreateView.as_view(), name='integration_create'),
    path('<int:pk>/', views.IntegrationDetailView.as_view(), name='integration_detail'),
    path('<int:pk>/edit/', views.IntegrationUpdateView.as_view(), name='integration_edit'),
    path('<int:pk>/delete/', views.IntegrationDeleteView.as_view(), name='integration_delete'),
    path('<int:pk>/toggle/', views.IntegrationToggleView.as_view(), name='integration_toggle'),
    
    # POS integrations
    path('pos/', views.POSIntegrationListView.as_view(), name='pos_integration_list'),
    path('pos/add/', views.POSIntegrationCreateView.as_view(), name='pos_integration_create'),
    path('pos/<int:pk>/edit/', views.POSIntegrationUpdateView.as_view(), name='pos_integration_edit'),
    
    # Accounting integrations
    path('accounting/', views.AccountingIntegrationListView.as_view(), name='accounting_integration_list'),
    path('accounting/add/', views.AccountingIntegrationCreateView.as_view(), name='accounting_integration_create'),
    path('accounting/<int:pk>/edit/', views.AccountingIntegrationUpdateView.as_view(), name='accounting_integration_edit'),
    
    # CRM integrations
    path('crm/', views.CRMIntegrationListView.as_view(), name='crm_integration_list'),
    path('crm/add/', views.CRMIntegrationCreateView.as_view(), name='crm_integration_create'),
    path('crm/<int:pk>/edit/', views.CRMIntegrationUpdateView.as_view(), name='crm_integration_edit'),
    
    # Webhooks
    path('webhooks/', views.WebhookListView.as_view(), name='webhook_list'),
    path('webhooks/add/', views.WebhookCreateView.as_view(), name='webhook_create'),
    path('webhooks/<int:pk>/edit/', views.WebhookUpdateView.as_view(), name='webhook_edit'),
    path('webhooks/<int:pk>/delete/', views.WebhookDeleteView.as_view(), name='webhook_delete'),
    path('webhook/<str:endpoint_url>/', views.WebhookReceiveView.as_view(), name='webhook_receive'),
    
    # Integration logs
    path('logs/', views.IntegrationLogListView.as_view(), name='integration_log_list'),
    path('logs/<int:integration_id>/', views.IntegrationLogDetailView.as_view(), name='integration_log_detail'),
    
    # Sync operations
    path('<int:pk>/sync/', views.IntegrationSyncView.as_view(), name='integration_sync'),
]