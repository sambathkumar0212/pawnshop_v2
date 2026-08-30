from django.urls import path
from . import views

urlpatterns = [
    path('day-book/', views.DayBookView.as_view(), name='accounting_day_book'),
    path('cash-book/', views.CashBookView.as_view(), name='accounting_cash_book'),
    path('trial-balance/', views.TrialBalanceView.as_view(), name='accounting_trial_balance'),
    path('profit-and-loss/', views.ProfitAndLossView.as_view(), name='accounting_profit_loss'),
    path('balance-sheet/', views.BalanceSheetView.as_view(), name='accounting_balance_sheet'),
    path('chart-of-accounts/', views.ChartOfAccountsListView.as_view(), name='accounting_chart_of_accounts'),
    path('expense/new/', views.RecordExpenseView.as_view(), name='accounting_record_expense'),
    path('journal/<int:pk>/', views.JournalEntryDetailView.as_view(), name='accounting_journal_detail'),
]
