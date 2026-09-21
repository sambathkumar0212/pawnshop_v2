from django.urls import path
from . import views

urlpatterns = [
    # Tiered interest rate scheme URLs
    path('tiered/create/', views.SchemeCreateView.as_view(), name='tiered_scheme_create'),
    path('tiered/<int:pk>/update/', views.SchemeUpdateView.as_view(), name='tiered_scheme_update'),
    
    # New, simplified scheme management URLs
    path('new/', views.NewSchemeListView.as_view(), name='new_scheme_list'),
    path('new/create/', views.NewSchemeCreateView.as_view(), name='new_scheme_create'),
    path('new/<int:pk>/', views.NewSchemeDetailView.as_view(), name='new_scheme_detail'),
    path('new/<int:pk>/update/', views.NewSchemeUpdateView.as_view(), name='new_scheme_update'),
    path('new/<int:pk>/delete/', views.NewSchemeDeleteView.as_view(), name='new_scheme_delete'),
    
    # Original URLs (kept for backward compatibility)
    path('', views.NewSchemeListView.as_view(), name='scheme_list'),  # Redirect to new implementation
    path('<int:pk>/', views.NewSchemeDetailView.as_view(), name='scheme_detail'),
    path('create/', views.SchemeCreateView.as_view(), name='scheme_create'),  # Changed to use tiered interest scheme creation
    path('<int:pk>/update/', views.SchemeUpdateView.as_view(), name='scheme_update'),  # Use the smart update view
    path('<int:pk>/delete/', views.NewSchemeDeleteView.as_view(), name='scheme_delete'),
    path('<int:pk>/json/', views.SchemeJsonView.as_view(), name='scheme_json'),

    # Central Daily Gold Rate & RBI 75% LTV Cap Management
    path('gold-rates/', views.DailyGoldRateManageView.as_view(), name='daily_gold_rates'),
    path('api/today-rate/', views.api_get_today_gold_rate, name='api_today_gold_rate'),
    path('api/fetch-live-rate/', views.api_fetch_live_gold_rates, name='api_fetch_live_gold_rates'),
]