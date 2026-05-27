from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import admin_views

urlpatterns = [
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(next_page='login'), name='logout'),
    path('password-change/', views.AdminOnlyPasswordChangeView.as_view(), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    path('password-reset/', views.AdminOnlyPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Organization signup and management (SaaS)
    path('signup/', views.OrganizationSignupView.as_view(), name='organization_signup'),
    path('organization/', views.OrganizationDashboardView.as_view(), name='organization_dashboard'),
    path('organization/edit/', views.OrganizationUpdateView.as_view(), name='organization_update'),
    path('organization/branch/add/', views.OrganizationBranchCreateView.as_view(), name='organization_branch_create'),
    path('organization/user/add/', views.OrganizationUserCreateView.as_view(), name='organization_user_create'),
    path('organization/subscription/toggle-auto-renew/', views.ToggleSubscriptionAutoRenewView.as_view(), name='toggle_subscription_auto_renew'),
    path('subscription-plans/', views.SubscriptionPlansView.as_view(), name='subscription_plans'),
    path('subscription-upgrade/<str:plan>/', views.SubscriptionUpgradeView.as_view(), name='subscription_upgrade'),
    
    # Super Admin URLs
    path('superadmin/', views.SuperAdminDashboardView.as_view(), name='superadmin_dashboard'),
    path('superadmin/organizations/', views.SuperAdminOrganizationListView.as_view(), name='superadmin_organization_list'),
    path('superadmin/organizations/<int:pk>/', views.SuperAdminOrganizationDetailView.as_view(), name='superadmin_organization_detail'),
    path('superadmin/organizations/<int:pk>/suspend/', views.SuperAdminOrganizationSuspendView.as_view(), name='superadmin_organization_suspend'),
    path('superadmin/organizations/<int:pk>/reactivate/', views.SuperAdminOrganizationReactivateView.as_view(), name='superadmin_organization_reactivate'),
    path('superadmin/organizations/<int:pk>/delete/', views.SuperAdminOrganizationDeleteView.as_view(), name='superadmin_organization_delete'),
    
    # User management
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/add/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    
    # Role management
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/add/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/edit/', views.RoleUpdateView.as_view(), name='role_update'),
    path('roles/<int:pk>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),
    
    # Customer management (moved from transactions app)
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/add/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('customers/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('customers/<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='customer_update'),
    path('customers/<int:pk>/delete/', views.CustomerDeleteView.as_view(), name='customer_delete'),
    path('customer/<int:pk>/json/', views.CustomerJsonView.as_view(), name='customer_json'),
    
    # User profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    
    # Debug view for branch issues (temporary)
    path('debug/branches/', views.DebugBranchView.as_view(), name='debug_branches'),
    
    # Face ID enrollment
    path('face-id/enroll/', views.FaceEnrollmentView.as_view(), name='face_enroll'),
    path('face-id/login/', views.FaceLoginView.as_view(), name='face_login'),
    
    # Deployment status check (no login required for easy access)
    path('deployment-status/', views.check_deployment_status, name='deployment_status'),
    
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Admin-only Staff Management URLs
    path('admin/dashboard/', admin_views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('admin/staff/', admin_views.StaffListView.as_view(), name='admin_staff_list'),
    path('admin/staff/add/', admin_views.StaffCreateView.as_view(), name='admin_staff_create'),
    path('admin/staff/<int:pk>/', admin_views.StaffDetailView.as_view(), name='admin_staff_detail'),
    path('admin/staff/<int:pk>/edit/', admin_views.StaffUpdateView.as_view(), name='admin_staff_update'),
    path('admin/staff/<int:pk>/reset-password/', admin_views.ResetStaffPasswordView.as_view(), name='admin_reset_password'),
    path('admin/staff/<int:pk>/delete/', admin_views.DeleteStaffView.as_view(), name='admin_staff_delete'),
    
    # Admin Audit Trail and History URLs
    path('admin/audit-trail/', admin_views.AuditTrailView.as_view(), name='admin_audit_trail'),
    path('admin/password-history/', admin_views.PasswordChangeHistoryView.as_view(), name='admin_password_history'),
    path('admin/deletion-history/', admin_views.StaffDeletionHistoryView.as_view(), name='admin_deletion_history'),
]