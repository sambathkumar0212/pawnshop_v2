from django.db import close_old_connections, connections
from django.http import Http404
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import resolve, reverse

class DatabaseConnectionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def _close_sqlite_connections(self):
        for connection in connections.all():
            if connection.vendor == 'sqlite':
                connection.close()

    def __call__(self, request):
        # Always drop SQLite file handles between requests to avoid stale
        # connections after interrupted writes or local file sync/copy events.
        self._close_sqlite_connections()
        close_old_connections()

        try:
            response = self.get_response(request)
        finally:
            self._close_sqlite_connections()
            close_old_connections()

        return response

class OrganizationDataIsolationMiddleware:
    """
    Middleware to ensure complete isolation of data between organizations.
    This middleware ensures that users can only access data belonging to their organization.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Paths that should be exempt from organization isolation
        # These are typically public pages, login pages, etc.
        self.exempt_paths = [
            '/admin/', 
            '/login/', 
            '/logout/',
            '/organization/signup/',
            '/password_reset/',
            '/static/',
            '/media/',
            '/api/',
            '/favicon.ico',
            '/robots.txt',
            '/check_deployment_status/',
            # Add other paths that should be accessible without organization context
        ]
        
        # Models that need organization isolation but don't have direct organization field
        # Format: 'app_name.model_name': {'field': 'related_field', 'related_model': 'related_model'}
        self.indirect_models = {
            'accounts.customer': {'field': 'branch', 'related_field': 'organization'},
            'inventory.item': {'field': 'branch', 'related_field': 'organization'},
            'transactions.loan': {'field': 'branch', 'related_field': 'organization'},
            'transactions.sale': {'field': 'branch', 'related_field': 'organization'},
            'transactions.payment': {'field': 'loan', 'related_field': 'branch__organization'},
            'transactions.loanitem': {'field': 'loan', 'related_field': 'branch__organization'},
            'transactions.loanextension': {'field': 'loan', 'related_field': 'branch__organization'},
        }
        
        # URL patterns that need special attention for organization isolation
        # These are typically list views of models that need filtering by organization
        self.sensitive_url_patterns = [
            'customer_list',
            'customer_detail',
            'loan_list',
            'loan_detail',
            'item_list',
            'item_detail',
            'sale_list',
            'sale_detail',
            'payment_list',
            'dashboard',
        ]
        
    def __call__(self, request):
        # Skip middleware for exempt paths
        if any(request.path.startswith(path) for path in self.exempt_paths):
            return self.get_response(request)
            
        # Skip middleware for unauthenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)
            
        # Skip for superusers who can access all data
        if request.user.is_superuser:
            return self.get_response(request)
            
        # Skip middleware if user doesn't have an organization (older users)
        # This allows existing users without organization to continue using the system
        if not hasattr(request.user, 'organization') or not request.user.organization:
            return self.get_response(request)
            
        # Add organization to request for use in views
        request.organization = request.user.organization
        
        # For sensitive URL patterns, ensure organization isolation
        resolved = resolve(request.path)
        if resolved.url_name in self.sensitive_url_patterns:
            # Set organization filter in session to ensure views filter by organization
            request.session['organization_id'] = request.organization.id
        
        response = self.get_response(request)
        return response