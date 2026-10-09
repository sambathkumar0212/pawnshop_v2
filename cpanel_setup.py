"""
cpanel_setup.py
One-Time Initialization Script for cPanel Hosting Without Terminal / SSH.

Usage via cPanel Cron Jobs (run once, then delete cron):
Command:
/home/hinfotechnolo/virtualenv/FMG_ERP/3.11/bin/python /home/hinfotechnolo/FMG_ERP/cpanel_setup.py > /home/hinfotechnolo/FMG_ERP/setup_log.txt 2>&1
"""

import os
import sys

# Add project root to sys.path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
os.environ.setdefault('DJANGO_ENV', 'production')

def main():
    try:
        import django
        django.setup()
        from django.core.management import call_command
        from django.contrib.auth import get_user_model

        print("==================================================")
        print("STARTING CPANEL INITIALIZATION FOR PAWNSHOP ERP")
        print("==================================================")

        # 1. Database Migrations
        print("\n[Step 1/3] Running Database Migrations...")

        def run_migrations_with_retry(max_retries=10):
            """
            Run migrations. If a 'table already exists' OperationalError is raised,
            fake that migration and retry. This handles cases where the DB and
            migration history are out of sync (e.g. after a DB restore or copy).
            """
            import re
            from django.db import OperationalError as DjangoOperationalError

            for attempt in range(1, max_retries + 1):
                try:
                    call_command('migrate', interactive=False)
                    return  # success
                except Exception as exc:
                    err_str = str(exc)
                    # Detect "table X already exists" pattern
                    match = re.search(r'table["\s]+"?(\w+)"?\s+already exists', err_str, re.IGNORECASE)
                    if not match:
                        raise  # Unknown error — re-raise
                    table_name = match.group(1)
                    print(f"\n  [WARNING] Table '{table_name}' already exists in DB.")
                    # Derive app + migration from Django's pending migrations
                    from django.db.migrations.executor import MigrationExecutor
                    from django.db import connection
                    executor = MigrationExecutor(connection)
                    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
                    faked = False
                    for migration, _backward in pending:
                        # Identify which migration creates the conflicting table
                        for op in migration.operations:
                            op_class = type(op).__name__
                            guessed_table = f"{migration.app_label}_{op.name.lower()}" \
                                if hasattr(op, 'name') else ''
                            if op_class == 'CreateModel' and guessed_table == table_name:
                                print(f"  [FIX] Faking migration: {migration.app_label}.{migration.name}")
                                call_command('migrate', migration.app_label, migration.name,
                                             '--fake', interactive=False)
                                faked = True
                                break
                        if faked:
                            break
                    if not faked:
                        print(f"  [WARNING] Could not identify migration for table '{table_name}'. "
                              f"Attempt {attempt}/{max_retries}. Retrying migrate...")
                    if attempt >= max_retries:
                        raise RuntimeError(
                            f"Migration failed after {max_retries} attempts. "
                            f"Last error: {exc}"
                        ) from exc

        run_migrations_with_retry()
        print(" -> Database tables created/updated successfully.")

        # 2. Collect Static Files
        print("\n[Step 2/3] Collecting Static Files...")
        call_command('collectstatic', interactive=False)
        print(" -> Static assets successfully gathered in staticfiles/.")

        # 3. Create Default Superuser if None Exists
        print("\n[Step 3/3] Checking Superuser Account...")
        User = get_user_model()
        admin_username = os.environ.get('DEFAULT_ADMIN_USER', 'admin')
        admin_email = os.environ.get('DEFAULT_ADMIN_EMAIL', 'admin@firstmoneygold.com')
        admin_password = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'Admin@12345')

        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username=admin_username,
                email=admin_email,
                password=admin_password
            )
            print(f" -> Superuser created successfully!")
            print(f"    Username: {admin_username}")
            print(f"    Password: {admin_password}")
            print("    [IMPORTANT] Log in immediately and change this password!")
        else:
            existing_admins = [u.username for u in User.objects.filter(is_superuser=True)]
            print(f" -> Superuser already exists ({', '.join(existing_admins)}). Skipping.")

        print("\n==================================================")
        print("SUCCESS: CPANEL SETUP COMPLETE!")
        print("You can now safely delete this cron job.")
        print("==================================================")

    except Exception as e:
        import traceback
        print("\n[ERROR] An error occurred during setup:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
