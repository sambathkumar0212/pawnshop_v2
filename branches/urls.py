from django.urls import path
from . import views

urlpatterns = [
    path('', views.BranchListView.as_view(), name='branch_list'),
    path('<int:pk>/', views.BranchDetailView.as_view(), name='branch_detail'),
    path('create/', views.BranchCreateView.as_view(), name='branch_create'),
    path('<int:pk>/update/', views.BranchUpdateView.as_view(), name='branch_update'),
    path('<int:pk>/delete/', views.BranchDeleteView.as_view(), name='branch_delete'),
    path('<int:branch_id>/settings/', views.BranchSettingsUpdateView.as_view(), name='branch_settings_update'),
]