from django.db import migrations

def ensure_role_defaults(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    # Update any roles with null/empty role_type
    Role.objects.filter(role_type__isnull=True).update(role_type='cashier')
    Role.objects.filter(role_type='').update(role_type='cashier')
    # Update any roles with null/empty category
    Role.objects.filter(category__isnull=True).update(category='frontline')
    Role.objects.filter(category='').update(category='frontline')

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_load_default_roles'),
    ]

    operations = [
        migrations.RunPython(ensure_role_defaults),
    ]