#!/usr/bin/env python
"""
Script to check migration status from command line.
This helps you verify if migrations have been applied correctly.

Usage:
  python scripts/check_migrations.py

Output:
  - JSON summary of applied migrations
  - Exit code 0 if all critical migrations applied
  - Exit code 1 if migrations are incomplete
"""
import os
import sys
import django
import json
from datetime import datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
django.setup()

def check_migrations():
    """Check migration status and return a report"""
    from django.db.migrations.recorder import MigrationRecorder
    from django.apps import apps
    
    try:
        # Get all migrations that have been applied
        applied_migrations = MigrationRecorder.Migration.objects.all().order_by('app', 'name')
        
        # Group migrations by app
        migrations_by_app = {}
        for migration in applied_migrations:
            app_name = migration.app
            if app_name not in migrations_by_app:
                migrations_by_app[app_name] = []
            migrations_by_app[app_name].append(migration.name)
        
        # Get all installed apps that might have migrations
        installed_apps = [app_config.name for app_config in apps.get_app_configs() 
                          if app_config.name.startswith('django.') == False]
        
        # List critical apps that must have migrations
        critical_apps = ['accounts', 'branches', 'inventory', 'transactions']
        missing_apps = [app for app in critical_apps if app not in migrations_by_app]
        
        # Check for unapplied migrations
        unapplied_migrations = []
        for app_label in installed_apps:
            try:
                app_config = apps.get_app_config(app_label.split('.')[-1])
                if not hasattr(app_config, 'migrations_module'):
                    continue
                    
                # Try to get the migrations directory
                migrations_dir = os.path.join(app_config.path, 'migrations')
                if not os.path.exists(migrations_dir):
                    continue
                    
                # Check which migrations should be applied
                migration_files = [f[:-3] for f in os.listdir(migrations_dir) 
                                  if f.endswith('.py') and f != '__init__.py']
                
                # Compare with applied migrations
                applied = migrations_by_app.get(app_label, [])
                for migration in migration_files:
                    if migration not in applied:
                        unapplied_migrations.append(f"{app_label}.{migration}")
            except Exception as e:
                print(f"Error checking app {app_label}: {e}")
                
        # Determine status
        status_ok = len(missing_apps) == 0 and len(unapplied_migrations) == 0
        
        # Build the report
        report = {
            "status": "ok" if status_ok else "incomplete",
            "timestamp": datetime.now().isoformat(),
            "applied_migrations": migrations_by_app,
            "total_applied": applied_migrations.count(),
            "missing_critical_apps": missing_apps,
            "unapplied_migrations": unapplied_migrations
        }
        
        # Add the last applied migration if any exist
        if applied_migrations.exists():
            last_migration = applied_migrations.last()
            report["last_migration"] = {
                "app": last_migration.app,
                "name": last_migration.name,
                "applied": last_migration.applied.isoformat()
            }
        
        return report, status_ok
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }, False

def main():
    """Main function to run the migration check"""
    report, status_ok = check_migrations()
    
    # Print the report as JSON
    print(json.dumps(report, indent=2))
    
    # Exit with appropriate status code
    return 0 if status_ok else 1

if __name__ == "__main__":
    sys.exit(main())