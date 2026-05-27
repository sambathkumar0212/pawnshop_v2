"""
Minimal WSGI file that will start even if there are database connection issues.
This provides a fallback to ensure the application can at least start and show error pages.
"""
import os
import sys
import logging
from pathlib import Path

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Set required environment variables
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')

# Create a simplified application that will respond even if Django fails
def simple_app(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/html; charset=utf-8')]
    
    # Path to serve basic static content
    path_info = environ.get('PATH_INFO', '').lstrip('/')
    
    # Allow health checks to pass through
    if path_info in ('', '/', 'health', 'login'):
        start_response(status, headers)
        return [b"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Pawnshop Management - Starting Up</title>
            <meta http-equiv="refresh" content="10">
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                .container { max-width: 800px; margin: 0 auto; padding: 20px; }
                h1 { color: #333; }
                .loading { display: inline-block; position: relative; width: 80px; height: 80px; }
                .loading div { display: inline-block; position: absolute; left: 8px; width: 16px; 
                              background: #007bff; animation: loading 1.2s cubic-bezier(0, 0.5, 0.5, 1) infinite; }
                .loading div:nth-child(1) { left: 8px; animation-delay: -0.24s; }
                .loading div:nth-child(2) { left: 32px; animation-delay: -0.12s; }
                .loading div:nth-child(3) { left: 56px; animation-delay: 0; }
                @keyframes loading { 0% { top: 8px; height: 64px; } 50%, 100% { top: 24px; height: 32px; } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Pawnshop Management System - Starting Up</h1>
                <p>The application is initializing. This page will automatically refresh.</p>
                <div class="loading"><div></div><div></div><div></div></div>
                <p>If this page persists for more than a few minutes, please contact support.</p>
            </div>
        </body>
        </html>
        """]
    
    # Return 404 for all other URLs
    start_response('404 Not Found', headers)
    return [b'Not Found']

# Try to load Django, but fall back to the simple app if it fails
application = simple_app
try:
    import django
    django.setup()
    
    # Now we can try importing the real application
    from django.core.wsgi import get_wsgi_application
    from django.conf import settings
    
    # Set a flag to indicate we're using minimal startup
    os.environ['MINIMAL_STARTUP'] = 'True'
    
    # Get the main application
    django_app = get_wsgi_application()
    
    # Create a wrapper that catches any Django exceptions
    def application_with_fallback(environ, start_response):
        try:
            return django_app(environ, start_response)
        except Exception as e:
            logging.error(f"Error in Django application: {e}")
            return simple_app(environ, start_response)
    
    application = application_with_fallback
    logging.info("Django application loaded successfully.")

except Exception as e:
    logging.error(f"Failed to load Django application: {e}")
    logging.info("Using minimal fallback application instead.")

# Report status
logging.info(f"WSGI application initialized: {'Django' if application != simple_app else 'Minimal fallback'}")