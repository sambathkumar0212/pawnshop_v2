from django.db import migrations

def add_updated_at_if_missing(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == 'postgresql':
            cursor.execute("""
                ALTER TABLE transactions_loan 
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
            """)
        elif connection.vendor == 'sqlite':
            cursor.execute("PRAGMA table_info(transactions_loan);")
            columns = [row[1] for row in cursor.fetchall()]
            if 'updated_at' not in columns:
                cursor.execute("ALTER TABLE transactions_loan ADD COLUMN updated_at datetime NULL;")

def reverse_code(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0043_loan_is_otp_verified_loan_otp_attempts_loan_otp_code_and_more'),
    ]

    operations = [
        migrations.RunPython(add_updated_at_if_missing, reverse_code),
    ]

