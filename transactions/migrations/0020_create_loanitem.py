from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_alter_item_tamil_tags'),
        ('transactions', '0019_sale_place_of_supply_tamil'),
    ]

    operations = [
        # Create LoanItem table only if it doesn't exist
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS transactions_loanitem (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    loan_id INTEGER NOT NULL REFERENCES transactions_loan(id) ON DELETE CASCADE,
                    item_id INTEGER NOT NULL REFERENCES inventory_item(id) ON DELETE CASCADE,
                    gold_karat DECIMAL(4,2) NOT NULL,
                    gross_weight DECIMAL(7,3) NOT NULL,
                    net_weight DECIMAL(7,3) NOT NULL,
                    stone_weight DECIMAL(7,3) NULL,
                    market_price_22k DECIMAL(10,2) NOT NULL,
                    UNIQUE(loan_id, item_id)
                );
            """,
            reverse_sql="DROP TABLE IF EXISTS transactions_loanitem;",
        ),
        # Drop quantity column if it exists (SQLite workaround via recreate)
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS transactions_loanitem_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    loan_id INTEGER NOT NULL REFERENCES transactions_loan(id) ON DELETE CASCADE,
                    item_id INTEGER NOT NULL REFERENCES inventory_item(id) ON DELETE CASCADE,
                    gold_karat DECIMAL(4,2) NOT NULL,
                    gross_weight DECIMAL(7,3) NOT NULL,
                    net_weight DECIMAL(7,3) NOT NULL,
                    stone_weight DECIMAL(7,3) NULL,
                    market_price_22k DECIMAL(10,2) NOT NULL,
                    UNIQUE(loan_id, item_id)
                );
                INSERT OR IGNORE INTO transactions_loanitem_new
                    (id, loan_id, item_id, gold_karat, gross_weight, net_weight, stone_weight, market_price_22k)
                SELECT id, loan_id, item_id, gold_karat, gross_weight, net_weight, stone_weight, market_price_22k
                FROM transactions_loanitem;
                DROP TABLE transactions_loanitem;
                ALTER TABLE transactions_loanitem_new RENAME TO transactions_loanitem;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
