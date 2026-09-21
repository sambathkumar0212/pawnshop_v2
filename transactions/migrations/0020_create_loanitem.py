from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_alter_item_tamil_tags'),
        ('transactions', '0019_sale_place_of_supply_tamil'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoanItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gold_karat', models.DecimalField(decimal_places=2, max_digits=4)),
                ('gross_weight', models.DecimalField(decimal_places=3, max_digits=7)),
                ('net_weight', models.DecimalField(decimal_places=3, max_digits=7)),
                ('stone_weight', models.DecimalField(blank=True, decimal_places=3, max_digits=7, null=True)),
                ('market_price_22k', models.DecimalField(decimal_places=2, max_digits=10)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.item')),
                ('loan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='transactions.loan')),
            ],
            options={
                'unique_together': {('loan', 'item')},
            },
        ),
    ]
