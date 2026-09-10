from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .api_views import (
    CustomTokenObtainPairView,
    CurrentUserView,
    UpdateProfileView,
    ChangePasswordView,
)

app_name = 'accounts_api'

urlpatterns = [
    # JWT Authentication
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # User Profile
    path('me/', CurrentUserView.as_view(), name='current_user'),
    path('update-profile/', UpdateProfileView.as_view(), name='update_profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
]
