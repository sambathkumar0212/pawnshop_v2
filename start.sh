#!/bin/bash
set -e
        
echo "Starting application deployment process..."

# Set environment variables
export DJANGO_SETTINGS_MODULE=pawnshop_management.settings
export RENDER=true

# Add the current directory to the Python path to fix import issues
export PYTHONPATH="$PYTHONPATH:$(pwd)"
echo "PYTHONPATH set to: $PYTHONPATH"

# First, let's fix any critical database schema issues
echo "Checking and fixing database schema issues..."
timeout 60 python scripts/fix_missing_columns.py || echo "⚠️ Column fix script timed out but proceeding anyway"

# Run migrations BEFORE starting Gunicorn to ensure database is ready
echo "Running migrations before starting application server..."
python manage.py migrate --noinput
MIGRATE_STATUS=$?

if [ $MIGRATE_STATUS -eq 0 ]; then
  echo "✅ Initial migrations completed successfully!"
else
  echo "⚠️ Initial migrations had issues, trying specialized migration script..."
  python scripts/run_migrations.py
  
  # Fix django_session table specifically if needed - RUN AS SEPARATE COMMAND
  echo "Ensuring django_session table exists..."
  # python scripts/fix_session_table.py
fi

# Restore all critical data (this ensures all important data exists even if post_deploy.sh failed)
echo "Ensuring all critical data is restored..."
python scripts/restore_all_data.py || echo "⚠️ Data restoration had issues, but continuing"

# Create superuser if environment variables are set
echo "Checking for superuser credentials..."
if [[ -n "$DJANGO_SUPERUSER_USERNAME" && -n "$DJANGO_SUPERUSER_PASSWORD" && -n "$DJANGO_SUPERUSER_EMAIL" ]]; then
    echo "Creating superuser from environment variables..."
    python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if User.objects.filter(username=username).exists():
    print(f'Superuser {username} already exists. Updating password...')
    user = User.objects.get(username=username)
    user.set_password(password)
    user.email = email
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()
    print(f'Superuser {username} updated successfully')
else:
    print(f'Creating new superuser {username}...')
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'Superuser {username} created successfully')
"
else
    # Create default superuser if environment variables aren't set
    echo "Creating default superuser 'admin'..."
    python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = 'admin'
email = 'admin@example.com'
password = 'admin123'  # You should change this immediately after first login!

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print('Default superuser created. Username: admin, Password: admin123')
    print('IMPORTANT: Please change this password immediately after logging in!')
else:
    print('Default superuser already exists')
"
    # Create a file to record the default admin credentials
    echo "Default admin credentials: username=admin, password=admin123" > static/admin_credentials.txt
    echo "IMPORTANT: Change this password immediately after logging in!" >> static/admin_credentials.txt
fi

# Create migration status file
echo "Creating migration status file..."
MIGRATION_STATUS_DIR="static/status"
mkdir -p $MIGRATION_STATUS_DIR
python scripts/check_migrations.py > $MIGRATION_STATUS_DIR/migrations.json
echo "Last migration check: $(date)" > $MIGRATION_STATUS_DIR/migration_status.txt

# Log some diagnostic info
echo "PORT=$PORT"
echo "PYTHON_VERSION=$(python --version)"
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la
echo "Python path:"
python -c "import sys; print(sys.path)"

# Start the application server as a separate process
echo "Starting web server..."
if [ -z "$PORT" ]; then
  export PORT=8000
  echo "PORT not set, defaulting to $PORT"
fi

# Start Gunicorn as a completely separate process (no command chaining)
echo "Starting Gunicorn on port $PORT..."
exec gunicorn pawnshop_management.wsgi:application \
  --bind 0.0.0.0:$PORT \
  --workers=1 \
  --threads=4 \
  --timeout=300 \
  --log-level=debug \
  --access-logfile=-
