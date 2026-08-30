from django.urls import path
from . import views
from . import views_eod
from . import views_partial_release

urlpatterns = [
    # Loans
    path('loans/', views.LoanListView.as_view(), name='loan_list'),
    path('loans/add/', views.LoanCreateView.as_view(), name='loan_create'),
    path('loans/<str:loan_number>/', views.LoanDetailView.as_view(), name='loan_detail'),
    path('loans/<str:loan_number>/edit/', views.LoanUpdateView.as_view(), name='loan_update'),
    path('loans/<str:loan_number>/update-gold-status/', views.UpdateGoldStatusView.as_view(), name='update_gold_status'),
    path('loans/<str:loan_number>/delete/', views.LoanDeleteView.as_view(), name='loan_delete'),
    path('loans/<str:loan_number>/payment/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('loans/<str:loan_number>/extend/', views.LoanExtensionCreateView.as_view(), name='loan_extend'),
    path('loans/<str:loan_number>/foreclose/', views.LoanForecloseView.as_view(), name='loan_foreclose'),
    path('loans/<str:loan_number>/document/', views.LoanDocumentView.as_view(), name='loan_document'),
    path('loans/<str:loan_number>/expiry-notice/', views.LoanExpiryNoticeView.as_view(), name='loan_expiry_notice'),
    path('loans/<str:loan_number>/payment-history/', views.LoanPaymentHistoryDownloadView.as_view(), name='loan_payment_history_download'),
    path('loans/<str:loan_number>/tiered-schedule-download/', views.LoanTieredScheduleDownloadView.as_view(), name='loan_tiered_schedule_download'),
    path('loans/<str:loan_number>/edit-logs/', views.LoanEditLogsView.as_view(), name='loan_edit_logs'),
    
    # Task 2.3: Partial Ornament Release & Part-Payment Workflow
    path('loans/<str:loan_number>/partial-release/', views_partial_release.LoanPartialReleaseView.as_view(), name='loan_partial_release'),
    path('loans/<str:loan_number>/partial-release/<int:release_id>/voucher/', views_partial_release.LoanPartialReleaseVoucherView.as_view(), name='loan_partial_release_voucher'),
    
    # Task 2.1: Tiered Maker-Checker Loan Approvals Queue & Actions
    path('approvals/', views.LoanApprovalQueueView.as_view(), name='loan_approval_queue'),
    path('approvals/<int:pk>/approve/', views.LoanApproveActionView.as_view(), name='loan_approval_approve'),
    path('approvals/<int:pk>/reject/', views.LoanRejectActionView.as_view(), name='loan_approval_reject'),
    path('approvals/<int:pk>/reappraisal/', views.LoanReappraisalActionView.as_view(), name='loan_approval_reappraisal'),

    # Task 2.2: Automated EOD Batch Operations & RBI IRAC NPA Tagging Console
    path('eod-console/', views_eod.EODConsoleView.as_view(), name='eod_console'),
    path('eod-console/run/', views_eod.EODRunBatchActionView.as_view(), name='eod_run_batch'),
    
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
    path('customer-bank-details/<int:customer_id>/', views.get_customer_bank_details, name='customer_bank_details'),
    path('transliterate/', views.transliterate_between_english_tamil, name='transliterate_between_english_tamil'),
]
