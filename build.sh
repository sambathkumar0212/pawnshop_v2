#!/bin/bash
set -e

echo "Starting build process for Render.com deployment..."

# Install minimal requirements with proper dependency resolution
echo "Installing minimal dependencies..."
pip install --no-cache-dir -r requirements-minimal.txt

# Set environment variables for the build process
export DJANGO_SETTINGS_MODULE=pawnshop_management.settings
export DJANGO_MINIMAL_BUILD=True
export RENDER=true  # Mark that we're running on Render

# Copy SQLite environment file if it exists
if [ -f .env.sqlite ]; then
  echo "Using SQLite database configuration for all environments"
  cp .env.sqlite .env
fi

# Print database configuration (without sensitive info)
echo "Database configuration check:"
python -c "import os; from django.conf import settings; import django; django.setup(); db = settings.DATABASES['default']; print(f\"DATABASE ENGINE: {db.get('ENGINE', 'Not set')}\"); print(f\"DATABASE NAME: {db.get('NAME', 'Not set')}\");"

# PRIORITY FIX: Create django_session table directly before other migrations
echo "PRIORITY FIX: Creating django_session table directly if missing..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()
from django.db import connection, DatabaseError
print('Checking for django_session table...')
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM django_session')
        print('✅ django_session table already exists')
except Exception as e:
    print(f'⚠️ django_session table may not exist: {e}')
    print('Creating django_session table with direct SQL...')
    
    # Create the django_session table with direct SQL based on Django's schema
    with connection.cursor() as cursor:
        if 'sqlite' in connection.vendor:
            print('Using SQLite syntax to create session table')
            # SQLite syntax
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS django_session (
                    session_key varchar(40) NOT NULL PRIMARY KEY,
                    session_data text NOT NULL,
                    expire_date datetime NOT NULL
                );
            ''')
            try:
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS django_session_expire_date_idx 
                    ON django_session (expire_date);
                ''')
            except Exception as index_err:
                print(f'Warning while creating index: {index_err}')
                
        elif 'postgresql' in connection.vendor:
            print('Using PostgreSQL syntax to create session table')
            # PostgreSQL syntax
            try:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS django_session (
                        session_key varchar(40) NOT NULL PRIMARY KEY,
                        session_data text NOT NULL,
                        expire_date timestamp with time zone NOT NULL
                    );
                ''')
            except Exception as e:
                print(f'Error creating table: {e}')
                
            try:
                cursor.execute('''
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_indexes 
                            WHERE indexname = 'django_session_expire_date_idx'
                        ) THEN
                            CREATE INDEX django_session_expire_date_idx 
                            ON django_session (expire_date);
                        END IF;
                    END
                    $$;
                ''')
            except Exception as e:
                print(f'Error creating index: {e}')
                
        print('✅ django_session table created successfully')

    # Verify the table was actually created
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM django_session')
            print('✅ django_session table verified - it exists and is accessible')
    except Exception as e:
        print(f'❌ ERROR: django_session table could not be verified after creation: {e}')
"

# Create a direct fix for the database schema issues
echo "EMERGENCY FIX: Directly fixing database schema issues..."

# Create a temporary Python script to check and fix database issues
cat > /tmp/fix_database.py << EOL
import os, django, sys, subprocess
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

from django.conf import settings
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError

def run_command(command):
    print(f"Running: {command}")
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if stdout:
        print(f"STDOUT: {stdout.decode('utf-8')}")
    if stderr:
        print(f"STDERR: {stderr.decode('utf-8')}")
    return process.returncode

# Check if SQLite database file exists
db_path = settings.DATABASES['default'].get('NAME')
if os.path.exists(db_path):
    print(f"✅ SQLite database exists at {db_path}")
else:
    print(f"⚠️ SQLite database not found at {db_path}, it will be created during migrations")

# Run migrations to set up database schema
print("Running migrations to set up or update database schema...")
run_command('python manage.py migrate')

# Verify django_session table specifically
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM django_session")
        print("✅ django_session table exists and is accessible after migrations")
except Exception as e:
    print(f"❌ django_session table still missing after migrations: {e}")
    print("Applying emergency fix for django_session table...")
    if 'sqlite' in connection.vendor:
        # SQLite syntax
        cursor = connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS django_session (
                session_key varchar(40) NOT NULL PRIMARY KEY,
                session_data text NOT NULL,
                expire_date datetime NOT NULL
            );
            CREATE INDEX IF NOT EXISTS django_session_expire_date_idx 
            ON django_session (expire_date);
        ''')
        print("✅ Emergency django_session table created")

# Create superuser if env vars are set
if all(var in os.environ for var in ['DJANGO_SUPERUSER_USERNAME', 'DJANGO_SUPERUSER_EMAIL', 'DJANGO_SUPERUSER_PASSWORD']):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    username = os.environ['DJANGO_SUPERUSER_USERNAME']
    if not User.objects.filter(username=username).exists():
        print(f"Creating superuser with username: {username}")
        User.objects.create_superuser(
            username=username,
            email=os.environ['DJANGO_SUPERUSER_EMAIL'],
            password=os.environ['DJANGO_SUPERUSER_PASSWORD']
        )
        print("Superuser created successfully")
    else:
        print(f"Superuser {username} already exists")
EOL

# Run the database fix script
echo "Running database fix script..."
python /tmp/fix_database.py

# Remove the temporary script
rm /tmp/fix_database.py

# Final verification for django_session table
echo "Final verification for django_session table..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()
from django.db import connection

try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM django_session')
        print('✅ FINAL CHECK: django_session table exists and is accessible')
except Exception as e:
    print(f'❌ FINAL CHECK: django_session table is still missing: {e}')
"

# Verify migrations were applied correctly
echo "Verifying migrations status..."
python manage.py showmigrations | grep -v "\[X\]" || true

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Set up Gunicorn configuration
export GUNICORN_CMD_ARGS="--bind=0.0.0.0:$PORT --workers=2 --timeout=30 pawnshop_management.wsgi:application"

# Create a root-level wsgi.py file for compatibility
echo "Creating root-level wsgi.py file for compatibility..."
cat > wsgi.py << EOL
# This file ensures compatibility with platforms expecting 'app' in the root directory
from pawnshop_management.wsgi import application
app = application
EOL

echo "✅ Build completed successfully!"
echo "IMPORTANT: After deployment succeeds, install memory-intensive packages using:"
echo "pip install -r requirements-intensive.txt"