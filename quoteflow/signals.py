# quoteflow/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UpdatePost, UserUpdateStatus

@receiver(post_save, sender=UpdatePost)
def create_user_update_statuses(sender, instance, created, **kwargs):
    """
    Quando um novo UpdatePost é criado (e está publicado),
    cria um status de 'não lido' para todos os usuários ativos.
    """
    # A lógica só roda se o post for NOVO ('created') e estiver marcado como 'is_published'
    if created and instance.is_published:
        users = User.objects.filter(is_active=True)
        
        # Cria os objetos de status em lote para ser mais eficiente
        statuses_to_create = [
            UserUpdateStatus(user=user, post=instance, has_read=False)
            for user in users
        ]
        
        UserUpdateStatus.objects.bulk_create(statuses_to_create, ignore_conflicts=True)
        print(f"Notificações criadas para {len(users)} usuários para o post '{instance.title}'")