# teste_imap.py

import os
import django

# Inicializa o Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "loja.settings")  # ajuste o nome se não for esse
django.setup()

import imaplib
from perfil.models import ConfiguracaoEmail

def listar_pastas_imap(config_email):
    imap = imaplib.IMAP4_SSL(config_email.servidor_imap, config_email.porta_imap or 993)
    imap.login(config_email.email, config_email.senha)
    status, pastas = imap.list()
    imap.logout()

    print(f"\n📂 Pastas encontradas para {config_email.email}:\n")
    for p in pastas:
        print(p.decode())

# Exemplo para a primeira configuração de email (ou filtre pela empresa)
config = ConfiguracaoEmail.objects.get(empresa__nome='dihtransportes')
listar_pastas_imap(config)

