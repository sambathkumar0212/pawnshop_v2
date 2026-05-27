from django.urls import path
from . import views

urlpatterns = [
    # Item URLs
    path('', views.ItemListView.as_view(), name='item_list'),
    path('<int:pk>/', views.ItemDetailView.as_view(), name='item_detail'),
    path('create/', views.ItemCreateView.as_view(), name='item_create'),
    path('<int:pk>/update/', views.ItemUpdateView.as_view(), name='item_update'),
    path('<int:pk>/delete/', views.ItemDeleteView.as_view(), name='item_delete'),
    
    # Item image URLs
    path('<int:item_id>/add-image/', views.add_item_image, name='add_item_image'),
    path('image/<int:image_id>/delete/', views.delete_item_image, name='delete_item_image'),
    
    # Category URLs
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/update/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    
    # Search URL
    path('search/', views.inventory_search, name='inventory_search'),
]