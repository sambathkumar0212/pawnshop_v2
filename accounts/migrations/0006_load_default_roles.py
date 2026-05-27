from django.db import migrations

def load_default_roles(apps, schema_editor):
    # Import and run management command
    from django.core.management import call_command
    call_command('setup_default_roles', verbosity=2)

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_region_role_category_role_role_type_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),  # Added auth dependency for permissions
    ]

    operations = [
        migrations.RunPython(load_default_roles),
    ]