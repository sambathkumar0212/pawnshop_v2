from django.urls import path
from . import views

urlpatterns = [
    path('', views.BranchListView.as_view(), name='branch_list'),
    path('<int:pk>/', views.BranchDetailView.as_view(), name='branch_detail'),
    path('create/', views.BranchCreateView.as_view(), name='branch_create'),
    path('<int:pk>/update/', views.BranchUpdateView.as_view(), name='branch_update'),
    path('<int:pk>/delete/', views.BranchDeleteView.as_view(), name='branch_delete'),
    path('<int:branch_id>/settings/', views.BranchSettingsUpdateView.as_view(), name='branch_settings_update'),
    
    # Task 1.4: Cash Drawer, Cash Till & Daily Cash Scroll
    path('cash-till/', views.CashTillDashboardView.as_view(), name='cash_till_dashboard'),
    path('cash-till/open/', views.CashTillOpenView.as_view(), name='cash_till_open'),
    path('cash-till/<int:pk>/reconcile/', views.CashTillReconcileView.as_view(), name='cash_till_reconcile'),
    path('cash-till/<int:pk>/signoff/', views.CashTillManagerSignoffView.as_view(), name='cash_till_signoff'),
    path('cash-till/<int:pk>/bank-deposit/', views.CashTillBankDepositView.as_view(), name='cash_till_bank_deposit'),
    path('cash-till/<int:pk>/print/', views.CashTillPrintScrollView.as_view(), name='cash_till_print'),
    path('cash-till/history/', views.CashTillHistoryListView.as_view(), name='cash_till_history'),
]