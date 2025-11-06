import os
from celery import Celery

# Define o módulo de configurações do Django para o 'celery'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'loja.settings')

app = Celery('loja')

# Usa strings aqui para que o worker não precise serializar
# o objeto de configuração para processos filhos.
# O namespace='CELERY' significa que todas as configurações do Celery
# devem ter um prefixo `CELERY_` em settings.py.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carrega automaticamente os módulos de tasks de todos os apps registrados.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
