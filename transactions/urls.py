from django.urls import path
from . import views
from . import views_eod
from . import views_partial_release
from . import views_marketing
from . import views_gold_purchase
from . import views_autopilot

urlpatterns = [
    # 24/7 Autopilot Automation Console & Control Hub
    path('autopilot/', views_autopilot.AutopilotConsoleView.as_view(), name='autopilot_console'),
    path('autopilot/save-config/', views_autopilot.AutopilotSaveConfigView.as_view(), name='autopilot_save_config'),
    path('autopilot/trigger/', views_autopilot.AutopilotTriggerActionView.as_view(), name='autopilot_trigger'),
    path('autopilot/logs/export/', views_autopilot.AutopilotLogsExportView.as_view(), name='autopilot_export_logs'),

    # Loans
    path('loans/', views.LoanListView.as_view(), name='loan_list'),
    path('loans/add/', views.LoanCreateView.as_view(), name='loan_create'),
    path('loans/whatsapp/preview/', views.LoanBatchWhatsAppPreviewView.as_view(), name='loan_batch_whatsapp_preview'),
    path('loans/whatsapp/dispatch/', views.LoanBatchWhatsAppDispatchView.as_view(), name='loan_batch_whatsapp_dispatch'),
    path('loans/<str:loan_number>/', views.LoanDetailView.as_view(), name='loan_detail'),
    path('loans/<int:pk>/verify-otp/', views.LoanVerifyOTPView.as_view(), name='loan_verify_otp'),
    path('loans/<int:pk>/resend-otp/', views.LoanResendOTPView.as_view(), name='loan_resend_otp'),
    path('loans/<int:pk>/disburse/', views.LoanDisburseActionView.as_view(), name='loan_disburse'),
    path('loans/<str:loan_number>/edit/', views.LoanUpdateView.as_view(), name='loan_update'),
    path('loans/<str:loan_number>/update-gold-status/', views.UpdateGoldStatusView.as_view(), name='update_gold_status'),
    path('loans/<str:loan_number>/delete/', views.LoanDeleteView.as_view(), name='loan_delete'),
    path('loans/<str:loan_number>/payment/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('loans/<str:loan_number>/extend/', views.LoanExtensionCreateView.as_view(), name='loan_extend'),
    path('loans/<str:loan_number>/foreclose/', views.LoanForecloseView.as_view(), name='loan_foreclose'),
    path('loans/<str:loan_number>/document/', views.LoanDocumentView.as_view(), name='loan_document'),
    path('loans/<str:loan_number>/expiry-notice/', views.LoanExpiryNoticeView.as_view(), name='loan_expiry_notice'),
    path('loans/<str:loan_number>/send-email/', views.LoanSendEmailView.as_view(), name='loan_send_email'),
    path('loans/<str:loan_number>/send-whatsapp/', views.LoanSendWhatsAppView.as_view(), name='loan_send_whatsapp'),
    path('loans/<str:loan_number>/track-whatsapp/', views.LoanTrackWhatsAppClickView.as_view(), name='loan_track_whatsapp_click'),
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
    path('eod-console/irac-alert/', views_eod.SendIRACAlertActionView.as_view(), name='eod_send_irac_alert'),
    path('eod-console/irac-export/', views_eod.ExportIRACWatchlistCSVView.as_view(), name='eod_export_irac_watchlist'),
    path('eod-console/pair-whatsapp/', views_eod.PairWhatsAppSessionView.as_view(), name='eod_pair_whatsapp'),
    path('eod-console/reset-whatsapp/', views_eod.ResetWhatsAppSessionView.as_view(), name='eod_reset_whatsapp'),
    path('eod-console/get-whatsapp-qr/', views_eod.GetWhatsAppQRView.as_view(), name='eod_get_whatsapp_qr'),
    path('eod-console/auto-dispatch-irac/', views_eod.AutoDispatchIRACAlertsView.as_view(), name='eod_auto_dispatch_irac'),
    
    # Payments
    path('payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('payments/pending-upi/', views.PendingUPIPaymentsListView.as_view(), name='pending_upi_payments'),
    path('payments/<int:pk>/verify-upi/', views.VerifyUPIPaymentActionView.as_view(), name='verify_upi_payment'),
    path('loans/<str:loan_number>/upi-qr-data/', views.LoanUPIQRDataView.as_view(), name='loan_upi_qr_data'),
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

    # Buy Used Gold (Old Gold Purchases)
    path('gold-purchases/', views_gold_purchase.GoldPurchaseListView.as_view(), name='gold_purchase_list'),
    path('gold-purchases/add/', views_gold_purchase.GoldPurchaseCreateView.as_view(), name='gold_purchase_create'),
    path('gold-purchases/<int:pk>/', views_gold_purchase.GoldPurchaseDetailView.as_view(), name='gold_purchase_detail'),
    path('gold-purchases/<int:pk>/delete/', views_gold_purchase.GoldPurchaseDeleteView.as_view(), name='gold_purchase_delete'),
    path('gold-purchases/<int:pk>/receipt/', views_gold_purchase.GoldPurchaseReceiptPDFView.as_view(), name='gold_purchase_receipt'),

    # Digital Marketing & WhatsApp Broadcast Campaign Hub
    path('marketing/', views_marketing.DigitalMarketingDashboardView.as_view(), name='digital_marketing'),
    path('marketing/broadcast/', views_marketing.ExecuteBroadcastActionView.as_view(), name='marketing_broadcast_execute'),
    path('marketing/broadcast/status/', views_marketing.MarketingBroadcastStatusView.as_view(), name='marketing_broadcast_status'),
    path('marketing/broadcast/control/', views_marketing.MarketingBroadcastControlView.as_view(), name='marketing_broadcast_control'),
    path('marketing/log-broadcast/', views_marketing.LogBroadcastAPIView.as_view(), name='marketing_log_broadcast'),
    path('marketing/logs/export/', views_marketing.ExportCampaignLogsView.as_view(), name='marketing_export_logs'),
    path('marketing/generate-ai/', views_marketing.GenerateAICampaignView.as_view(), name='marketing_generate_ai'),
    path('marketing/templates/save/', views_marketing.SaveMarketingTemplateView.as_view(), name='marketing_save_template'),
    path('marketing/leads/import/', views_marketing.ImportMarketingLeadsView.as_view(), name='marketing_import_leads'),
    path('marketing/groups/contacts/', views_marketing.GroupContactsAPIView.as_view(), name='marketing_group_contacts_api'),
    path('marketing/whatsapp/reset-status/', views_marketing.ResetWhatsAppStatusAPIView.as_view(), name='marketing_reset_whatsapp_status'),

    # Utilities
    path('number_to_words/<str:number>/', views.number_to_words, name='number_to_words'),
    path('customer-bank-details/<int:customer_id>/', views.get_customer_bank_details, name='customer_bank_details'),
    path('transliterate/', views.transliterate_between_english_tamil, name='transliterate_between_english_tamil'),
]
