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

# 2. Set Django settings module & environment BEFORE loading .env
#    so env_loader picks the correct .env.production / .env file.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
os.environ.setdefault('DJANGO_ENV', 'production')

# 3. Load .env file (dotenv) so all settings are available to Django
try:
    from env_loader import load_env
    load_env()
except Exception:
    pass  # On platforms where env vars are injected natively, this is a no-op

# 4. Initialize Django WSGI application
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

