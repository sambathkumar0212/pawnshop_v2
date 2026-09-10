from django.urls import path
from .api_views import (
    LoanListAPIView,
    LoanDetailAPIView,
    LoanCreateAPIView,
    LoanPaymentAPIView,
    PaymentListAPIView,
)

app_name = 'transactions_api'

urlpatterns = [
    # Loans
    path('loans/', LoanListAPIView.as_view(), name='loan_list'),
    path('loans/create/', LoanCreateAPIView.as_view(), name='loan_create'),
    path('loans/<str:loan_identifier>/', LoanDetailAPIView.as_view(), name='loan_detail'),
    path('loans/<str:loan_identifier>/repay/', LoanPaymentAPIView.as_view(), name='loan_repay'),

    # Payments
    path('payments/', PaymentListAPIView.as_view(), name='payment_list'),
]
