from django.apps import AppConfig

class QuoteflowConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'quoteflow'
    def ready(self):
        import quoteflow.signals
