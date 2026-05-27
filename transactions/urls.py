from django.urls import path
from . import views

urlpatterns = [
    # Loans
    path('loans/', views.LoanListView.as_view(), name='loan_list'),
    path('loans/add/', views.LoanCreateView.as_view(), name='loan_create'),
    path('loans/<str:loan_number>/', views.LoanDetailView.as_view(), name='loan_detail'),
    path('loans/<str:loan_number>/edit/', views.LoanUpdateView.as_view(), name='loan_update'),
    path('loans/<str:loan_number>/delete/', views.LoanDeleteView.as_view(), name='loan_delete'),
    path('loans/<str:loan_number>/payment/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('loans/<str:loan_number>/extend/', views.LoanExtensionCreateView.as_view(), name='loan_extend'),
    path('loans/<str:loan_number>/foreclose/', views.LoanForecloseView.as_view(), name='loan_foreclose'),
    path('loans/<str:loan_number>/document/', views.LoanDocumentView.as_view(), name='loan_document'),
    path('loans/<str:loan_number>/expiry-notice/', views.LoanExpiryNoticeView.as_view(), name='loan_expiry_notice'),
    path('loans/<str:loan_number>/payment-history/', views.LoanPaymentHistoryDownloadView.as_view(), name='loan_payment_history_download'),
    
    # Payments
    path('payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('payments/<int:pk>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    path('payments/<int:payment_id>/receipt/', views.PaymentReceiptView.as_view(), name='payment_receipt'),
    
    # Sales
    path('sales/', views.SaleListView.as_view(), name='sale_list'),
    path('sales/add/', views.SaleCreateView.as_view(), name='sale_create'),
    path('sales/<int:pk>/', views.SaleDetailView.as_view(), name='sale_detail'),
    path('sales/<int:pk>/edit/', views.SaleUpdateView.as_view(), name='sale_update'),
    path('sales/<int:pk>/cancel/', views.SaleCancelView.as_view(), name='sale_cancel'),
    path('sales/<int:pk>/complete/', views.SaleCompleteView.as_view(), name='sale_complete'),
    path('sales/<int:pk>/receipt/', views.SaleReceiptView.as_view(), name='sale_receipt'),

    # Utilities
    path('number_to_words/<str:number>/', views.number_to_words, name='number_to_words'),
    path('transliterate/', views.transliterate_between_english_tamil, name='transliterate_between_english_tamil'),
]
