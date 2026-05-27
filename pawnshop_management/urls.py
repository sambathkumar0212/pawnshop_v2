"""
URL configuration for pawnshop_management project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.db.migrations.recorder import MigrationRecorder
from django.views.i18n import set_language

from .views.home_views import home_page

def migration_status(request):
    """View to check migration status - useful for monitoring if migrations have run"""
    if not request.user.is_superuser and not settings.DEBUG:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    try:
        # Get all applied migrations
        applied_migrations = MigrationRecorder.Migration.objects.all()
        
        # Group by app
        migrations_by_app = {}
        for migration in applied_migrations:
            app_name = migration.app
            if app_name not in migrations_by_app:
                migrations_by_app[app_name] = []
            migrations_by_app[app_name].append(migration.name)
        
        # Check for specific migrations that indicate successful deployment
        critical_apps = ['accounts', 'branches', 'inventory', 'transactions']
        status_ok = all(app in migrations_by_app for app in critical_apps)
        
        return JsonResponse({
            'status': 'ok' if status_ok else 'incomplete',
            'migrations': migrations_by_app,
            'total_count': applied_migrations.count(),
            'last_migration': {
                'app': applied_migrations.last().app,
                'name': applied_migrations.last().name,
                'applied': applied_migrations.last().applied.isoformat() 
            } if applied_migrations.exists() else None
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('branches/', include('branches.urls')),
    path('inventory/', include('inventory.urls')),
    path('transactions/', include('transactions.urls')),
    path('biometrics/', include('biometrics.urls')),
    path('reporting/', include('reporting.urls')),
    path('integrations/', include('integrations.urls')),
    path('schemes/', include('schemes.urls')),  # Schemes management URLs
    path('gst/', include('gst.urls')),  # GST management URLs
    path('analytics/', include('analytics.urls')),  # Risk Analytics and Business Intelligence URLs
    path('api/', include('rest_framework.urls')),
    path('dashboard/', include('accounts.urls')),  # Keep accounts as dashboard
    path('i18n/set-language/', set_language, name='set_language'),  # Language switcher
    path('', home_page, name='home'),  # New home page as the root URL
    # Migration status endpoint - for monitoring migrations
    path('migration-status/', migration_status, name='migration_status'),
    # Add camera test URL for debugging
    path('camera-test/', TemplateView.as_view(template_name='camera_test.html'), name='camera_test'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
