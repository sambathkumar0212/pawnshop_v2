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
]