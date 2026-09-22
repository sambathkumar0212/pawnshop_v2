"""
URLs configuration for Self-Service Customer Portal
"""

from django.urls import path
from accounts import views_portal

urlpatterns = [
    path('', views_portal.PortalRootRedirectView.as_view(), name='portal_root'),
    path('login/', views_portal.PortalLoginView.as_view(), name='portal_login'),
    path('logout/', views_portal.PortalLogoutView.as_view(), name='portal_logout'),
    path('dashboard/', views_portal.PortalDashboardView.as_view(), name='portal_dashboard'),
    path('pay/<str:loan_number>/', views_portal.PortalSubmitUPIPaymentView.as_view(), name='portal_submit_upi_payment'),
    path('pay-qr/<str:loan_number>/', views_portal.PortalLoanUPIModalView.as_view(), name='portal_loan_upi_modal'),
]
