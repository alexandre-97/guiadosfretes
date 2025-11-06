from django.apps import AppConfig

class PerfilConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'perfil'

    def ready(self):
        # Esta linha garante que os gatilhos em signals.py sejam registrados
        import perfil.signals