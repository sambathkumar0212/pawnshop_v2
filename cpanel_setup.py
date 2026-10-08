"""
cpanel_setup.py
One-Time Initialization Script for cPanel Hosting Without Terminal / SSH.

Usage via cPanel Cron Jobs (run once, then delete cron):
Command:
/home/USERNAME/virtualenv/pawnshop_v2/3.11/bin/python /home/USERNAME/pawnshop_v2/cpanel_setup.py > /home/USERNAME/pawnshop_v2/setup_log.txt 2>&1
"""

import os
import sys

# Add project root to sys.path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
os.environ.setdefault('DJANGO_ENV', 'production')

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
    call_command('migrate', interactive=False)
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
