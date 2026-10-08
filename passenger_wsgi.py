"""
Passenger WSGI Handler for cPanel Phusion Passenger Deployment.
Pawnshop Management ERP (Django 5.x)
"""
import os
import sys

# 1. Add application directory to sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# 2. Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')

# 3. Set production environment default
os.environ.setdefault('DJANGO_ENV', 'production')

# 4. Initialize Django WSGI application
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
