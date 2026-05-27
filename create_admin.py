#!/usr/bin/env python
"""Create admin user for pawnshop system"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawnshop_management.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from accounts.models import CustomUser

try:
    # Check if admin already exists
    if CustomUser.objects.filter(username='admin').exists():
        print("✓ Admin user already exists")
        admin = CustomUser.objects.get(username='admin')
        print(f"  Username: admin")
        print(f"  Email: {admin.email}")
    else:
        # Create admin user
        admin = CustomUser.objects.create_user(
            username='admin',
            email='admin@pawnshop.local',
            password='Admin@2024',
            first_name='Admin',
            last_name='User',
            is_pawnshop_admin=True,
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        
        print("✓ Admin user created successfully!")
        print(f"  Username: admin")
        print(f"  Password: Admin@2024")
        print(f"  is_pawnshop_admin: {admin.is_pawnshop_admin}")
except Exception as e:
    print(f"✗ Error: {str(e)}")
    sys.exit(1)
