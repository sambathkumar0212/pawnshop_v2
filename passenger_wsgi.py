import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'pawnshop_management.settings'

# Import the WSGI application
from pawnshop_management.wsgi import application
