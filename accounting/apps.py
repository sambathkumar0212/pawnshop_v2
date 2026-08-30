from django.apps import AppConfig


class AccountingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounting'
    verbose_name = 'General Ledger & Double-Entry Accounting'

    def ready(self):
        try:
            import accounting.signals  # noqa
        except ImportError:
            pass
