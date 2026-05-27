#!/usr/bin/env python
"""
Script to safely run all migrations in production environment.
This script should be run manually after the application has successfully started.

Run this on Render.com using:
python scripts/run_migrations.py
"""
import os
import sys
import django
import time
import logging
import traceback
from django.db import connection
from django.conf import settings
import datetime
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("migration-runner")

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

def backup_database():
    """Create a backup of the database schema and data if possible."""
    if not settings.DEBUG and not os.environ.get('SKIP_BACKUP'):
        try:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                import shutil
                db_path = settings.DATABASES['default']['NAME']
                backup_path = os.path.join(backup_dir, f'db_backup_{timestamp}.sqlite3')
                shutil.copy2(db_path, backup_path)
                logger.info(f"✅ SQLite database backed up to {backup_path}")
                return backup_path
            elif 'postgresql' in settings.DATABASES['default']['ENGINE']:
                backup_path = os.path.join(backup_dir, f'db_backup_{timestamp}.sql')
                db_settings = settings.DATABASES['default']
                pg_dump_cmd = f"pg_dump -h {db_settings['HOST']} -U {db_settings['USER']} -F c -b -v -f {backup_path} {db_settings['NAME']}"
                os.environ['PGPASSWORD'] = db_settings['PASSWORD']
                ret = os.system(pg_dump_cmd)
                if ret == 0:
                    logger.info(f"✅ PostgreSQL database backed up to {backup_path}")
                    return backup_path
                else:
                    logger.warning("⚠️ PostgreSQL backup failed")
        except Exception as e:
            logger.warning(f"⚠️ Database backup failed: {str(e)}")
    return None

def get_current_state():
    """Get the current state of the database for comparison."""
    state = {}
    with connection.cursor() as cursor:
        # Get list of all tables
        if 'sqlite' in connection.vendor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        else:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
        tables = cursor.fetchall()
        
        # For each table, get row count and sample data
        for (table_name,) in tables:
            if table_name.startswith('django_') or table_name.startswith('auth_'):
                continue  # Skip Django internal tables
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                state[table_name] = {'count': count}
            except:
                continue
    return state

def run_migrations():
    """Run all pending migrations with safety checks."""
    try:
        # Get pre-migration state
        pre_state = get_current_state()
        logger.info("Captured pre-migration database state")
        
        # Run migrations using Django's management command
        from django.core.management import execute_from_command_line
        execute_from_command_line(['manage.py', 'migrate'])
        
        # Get post-migration state
        post_state = get_current_state()
        logger.info("Captured post-migration database state")
        
        # Check for data loss
        has_data_loss = False
        for table, pre_data in pre_state.items():
            if table in post_state:
                if post_state[table]['count'] < pre_data['count']:
                    has_data_loss = True
                    logger.error(f"⚠️ Data loss detected in table {table}: {pre_data['count']} -> {post_state[table]['count']} records")
        
        if has_data_loss:
            logger.error("❌ Migration resulted in data loss! Check the backup and investigate.")
            return False
        
        logger.info("✅ Migrations completed successfully with no data loss")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main function to run the migrations safely."""
    logger.info("Starting production migration process...")
    
    # Backup database first
    backup_file = backup_database()
    
    # Run the migrations with safety checks
    success = run_migrations()
    
    if success:
        logger.info("✅ All migrations successfully applied!")
        if backup_file:
            logger.info(f"Database backup was created at {backup_file}")
        return 0
    else:
        logger.error("❌ Migrations failed. Check the logs for details.")
        if backup_file:
            logger.info(f"You can restore from backup at {backup_file} if needed")
        return 1

if __name__ == "__main__":
    sys.exit(main())