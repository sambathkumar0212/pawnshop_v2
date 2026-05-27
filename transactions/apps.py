from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transactions'
    
    def ready(self):
        """Perform initialization tasks when the app is ready"""
        # This ensures template tags are loaded
        try:
            import transactions.templatetags.loan_tags
        except Exception:
            pass
