from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Perfil

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    # Esta função está CORRETA e deve ser mantida.
    # Ela cria perfis para novos usuários, ignorando o loaddata.
    if created and not kwargs.get('raw', False):
        Perfil.objects.create(usuario=instance)

# @receiver(post_save, sender=User)
# def save_user_profile(sender, instance, **kwargs):
#     # Esta função está causando o erro durante o loaddata e é provavelmente desnecessária.
#     # Vamos desativá-la comentando as linhas para a migração funcionar.
#     instance.perfil.save()