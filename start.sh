#!/usr/bin/env bash
set -e

echo "==> Starting Pawnshop Management Web Service..."

# Set environment variables
export PYTHONPATH="$(pwd):$PYTHONPATH"
export DJANGO_SETTINGS_MODULE=pawnshop_management.settings
export RENDER=true
export PLAYWRIGHT_BROWSERS_PATH=0

# Run migrations to ensure database schema is up-to-date
echo "==> Ensuring migrations are applied..."
python manage.py migrate --noinput

# Create or update superuser if environment variables are set
if [[ -n "$DJANGO_SUPERUSER_USERNAME" && -n "$DJANGO_SUPERUSER_PASSWORD" && -n "$DJANGO_SUPERUSER_EMAIL" ]]; then
    echo "==> Configuring superuser credentials..."
    python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

user, created = User.objects.get_or_create(username=username, defaults={'email': email})
user.set_password(password)
user.email = email
user.is_staff = True
user.is_superuser = True
user.is_active = True
user.save()
print(f'Superuser {username} ready.')
"
fi

# Set default port if not set
if [ -z "$PORT" ]; then
    export PORT=8000
fi

# Start Gunicorn server
echo "==> Launching Gunicorn on 0.0.0.0:$PORT..."
exec gunicorn pawnshop_management.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers=2 \
    --threads=4 \
    --timeout=120 \
    --log-level=info \
    --access-logfile=-
