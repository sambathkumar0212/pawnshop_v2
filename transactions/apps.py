import os
import sys
from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transactions'
    
    def ready(self):
        """Perform initialization tasks when the app is ready"""
        try:
            import transactions.templatetags.loan_tags
        except Exception:
            pass

        # Auto-start Autopilot daemon if enabled and running within server process
        is_server_cmd = any(cmd in sys.argv for cmd in ['runserver', 'gunicorn', 'uvicorn', 'daphne'])
        if is_server_cmd or os.environ.get('RUN_MAIN') == 'true':
            if os.environ.get('RUN_MAIN') == 'true' or ('runserver' not in sys.argv):
                try:
                    from transactions.services_autopilot import get_or_create_autopilot_config, start_autopilot_daemon
                    config = get_or_create_autopilot_config()
                    if config and config.is_enabled:
                        start_autopilot_daemon()
                except Exception:
                    pass
