# This file ensures compatibility with platforms expecting 'app' in the root directory
# For platforms that look for 'app:app' pattern
from pawnshop_management.wsgi import application
app = application