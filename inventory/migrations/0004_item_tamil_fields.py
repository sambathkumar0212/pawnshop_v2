from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_alter_item_loans'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='tamil_description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='item',
            name='tamil_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
