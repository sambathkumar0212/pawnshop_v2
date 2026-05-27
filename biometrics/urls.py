from django.urls import path
from . import views

urlpatterns = [
    # User face enrollment
    path('enroll/user/', views.UserFaceEnrollmentView.as_view(), name='user_face_enroll'),
    path('enroll/user/capture/', views.UserFaceCaptureView.as_view(), name='user_face_capture'),
    path('enroll/user/verify/', views.UserFaceVerificationView.as_view(), name='user_face_verify'),
    
    # Customer face enrollment
    path('enroll/customer/<int:customer_id>/', views.CustomerFaceEnrollmentView.as_view(), name='customer_face_enroll'),
    path('enroll/customer/capture/<int:customer_id>/', views.CustomerFaceCaptureView.as_view(), name='customer_face_capture'),
    path('enroll/customer/verify/<int:customer_id>/', views.CustomerFaceVerificationView.as_view(), name='customer_face_verify'),
    
    # Authentication
    path('auth/face-login/', views.FaceLoginView.as_view(), name='face_login'),
    path('auth/customer-identify/', views.CustomerIdentificationView.as_view(), name='customer_identify'),
    
    # Settings
    path('settings/', views.BiometricSettingsView.as_view(), name='biometric_settings'),
    path('settings/branch/<int:branch_id>/', views.BranchBiometricSettingsView.as_view(), name='branch_biometric_settings'),
    
    # Logs and monitoring
    path('logs/', views.BiometricLogListView.as_view(), name='biometric_logs'),
]