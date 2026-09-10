from django.urls import path
from .api_views import DashboardSummaryAPIView

app_name = 'analytics_api'

urlpatterns = [
    path('summary/', DashboardSummaryAPIView.as_view(), name='dashboard_summary'),
]
