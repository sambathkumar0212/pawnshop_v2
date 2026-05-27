#!/bin/bash
set -e

# Create a timestamped log file to verify execution
TIMESTAMP=$(date "+%Y-%m-%d_%H-%M-%S")
LOG_FILE="post_deploy_executed_${TIMESTAMP}.log"
LOGS_DIR="/tmp/pawnshop_logs"
mkdir -p $LOGS_DIR

echo "Post-deployment script started at $(date)" > ${LOGS_DIR}/${LOG_FILE}
echo "Hostname: $(hostname)" >> ${LOGS_DIR}/${LOG_FILE}

# Also create a marker file in a visible location
touch "post_deploy_ran_${TIMESTAMP}.marker"

echo "Running post-deployment tasks..."

# Set environment variables
export DJANGO_SETTINGS_MODULE=pawnshop_management.settings
export RENDER=true

# Print database configuration
echo "Verifying database configuration..."
DB_INFO=$(python -c "import os; from django.conf import settings; import django; django.setup(); db = settings.DATABASES['default']; print(f\"DATABASE ENGINE: {db.get('ENGINE', 'Not set')}\"); print(f\"DATABASE NAME: {db.get('NAME', 'Not set')}\"); print(f\"DATABASE HOST: {db.get('HOST', 'Not set')}\")")
echo "$DB_INFO"
echo "$DB_INFO" >> ${LOGS_DIR}/${LOG_FILE}

# Record execution in database
echo "Recording execution in database..."
python -c "
import os, django, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()
from django.db import connection
from django.utils import timezone

with connection.cursor() as cursor:
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deployment_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_name VARCHAR(100),
                execution_time TIMESTAMP,
                status TEXT,
                message TEXT
            )
        ''')
        
        cursor.execute('''
            INSERT INTO deployment_logs (script_name, execution_time, status, message)
            VALUES (?, ?, ?, ?)
        ''', ('post_deploy.sh', timezone.now(), 'STARTED', 'Post-deployment script execution started'))
        
    except Exception as e:
        print(f'Error creating log table: {e}')
"

# Check current database state before migrations
echo "Checking current database state..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()
from django.db import connection
import json

def get_table_stats():
    stats = {}
    with connection.cursor() as cursor:
        if 'sqlite' in connection.vendor:
            cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';\")
        else:
            cursor.execute(\"SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';\")
        
        tables = cursor.fetchall()
        for (table,) in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table};')
                count = cursor.fetchone()[0]
                stats[table] = count
            except:
                continue
    return stats

# Save current state
with open('pre_migration_state.json', 'w') as f:
    json.dump(get_table_stats(), f)
"

# Run migrations using the safe migration script
echo "Running migrations safely..."
if python scripts/run_migrations.py; then
    echo "✅ Migrations completed successfully"
else
    echo "❌ Migration failed, checking for data loss..."
    python -c "
import json
import os

# Load pre-migration state
with open('pre_migration_state.json', 'r') as f:
    pre_state = json.load(f)

# Get current state
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
import django
django.setup()
from django.db import connection

def get_current_stats():
    stats = {}
    with connection.cursor() as cursor:
        if 'sqlite' in connection.vendor:
            cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';\")
        else:
            cursor.execute(\"SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';\")
        
        tables = cursor.fetchall()
        for (table,) in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table};')
                count = cursor.fetchone()[0]
                stats[table] = count
            except:
                continue
    return stats

current_state = get_current_stats()

# Check for data loss
has_data_loss = False
for table, pre_count in pre_state.items():
    if table in current_state:
        if current_state[table] < pre_count:
            print(f'⚠️ Data loss detected in {table}: {pre_count} -> {current_state[table]} records')
            has_data_loss = True

if has_data_loss:
    print('❌ Migration resulted in data loss!')
    exit(1)
else:
    print('✅ No data loss detected')
    exit(0)
"
    
    if [ $? -ne 0 ]; then
        echo "❌ Data loss detected! Please restore from backup."
        exit 1
    fi
fi

# Set up staff roles for multi-branch management
echo "Setting up staff roles for multi-branch management..."
python manage.py setup_roles

# Create a superuser if needed (non-interactive)
if [[ -n "$DJANGO_SUPERUSER_USERNAME" && -n "$DJANGO_SUPERUSER_PASSWORD" && -n "$DJANGO_SUPERUSER_EMAIL" ]]; then
    echo "Creating superuser if not exists..."
    python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', 
                                '$DJANGO_SUPERUSER_EMAIL', 
                                '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created successfully')
else:
    print('Superuser already exists, skipping creation')
"
fi

# Restore all critical data from backups
echo "Restoring all data from backups..."
python scripts/restore_all_data.py

# Complete the database log entry
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()
from django.db import connection
from django.utils import timezone

with connection.cursor() as cursor:
    try:
        cursor.execute('''
            INSERT INTO deployment_logs (script_name, execution_time, status, message)
            VALUES (?, ?, ?, ?)
        ''', ('post_deploy.sh', timezone.now(), 'COMPLETED', 'Post-deployment script completed successfully'))
    except Exception as e:
        print(f'Error logging completion: {e}')
"

echo "Post-deployment tasks completed at $(date)" >> ${LOGS_DIR}/${LOG_FILE}

# Create visible notification files in multiple locations
echo "Post-deploy script ran successfully at $(date)" > post_deploy_success.log
echo "Post-deploy script ran successfully at $(date)" > /tmp/post_deploy_success.log
echo "Post-deploy script ran successfully at $(date)" > static/post_deploy_success.log 2>/dev/null || true

# Cleanup temporary files
rm -f pre_migration_state.json