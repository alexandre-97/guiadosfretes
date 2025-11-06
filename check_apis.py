# check_apis.py

import os
import django

# Configure o Django (ajuste 'loja.settings' se o nome do seu projeto for diferente)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'loja.settings')
django.setup()

from django.contrib.auth.models import User
from perfil.models import Perfil # Importe o modelo Perfil

def check_api_configs():
    """
    Itera por todos os usuários e imprime suas configurações de API de WhatsApp.
    """
    print("--- Verificando Configurações de API de WhatsApp ---")
    users = User.objects.all().order_by('username') # Pega todos os usuários
    count_total = users.count()
    count_checked = 0

    for user in users:
        count_checked += 1
        print(f"\n({count_checked}/{count_total}) Verificando Usuário: {user.username} ({user.email})")
        try:
            perfil = user.perfil # Acessa o perfil via related name (OneToOneField)

            provider = perfil.api_provider
            creds = perfil.api_credentials
            proxy = perfil.proxy_url

            print(f"  -> Empresa: {perfil.empresa.nome if perfil.empresa else 'Nenhuma'}")
            print(f"  -> Provedor API: {provider}")

            if provider == 'MEGAAPI':
                if creds:
                    instance_key = creds.get('instance_key', 'NÃO DEFINIDO')
                    token_presente = 'SIM' if creds.get('token') else 'NÃO'
                    print(f"     - Instance Key: {instance_key}")
                    print(f"     - Token Definido: {token_presente}")
                else:
                    print("     - Credenciais: NÃO DEFINIDAS")
            elif provider == 'SELF_HOSTED':
                if creds:
                    instance_name = creds.get('instance_name', 'NÃO DEFINIDO')
                    port = creds.get('port', 'NÃO DEFINIDO')
                    print(f"     - Instance Name: {instance_name}")
                    print(f"     - Porta: {port}") # <-- AQUI VOCÊ VERÁ A PORTA CONFIGURADA
                else:
                    print("     - Credenciais: NÃO DEFINIDAS")
            else:
                # Caso o provider seja None ou outro valor
                 print(f"     - Credenciais: {creds if creds else 'NÃO DEFINIDAS'}")


            print(f"  -> Proxy Configurado: {'SIM (' + proxy + ')' if proxy else 'NÃO'}")

        except Perfil.DoesNotExist:
            print("  -> ERRO: Usuário não possui Perfil associado.")
        except AttributeError as e:
            # Captura erros como tentar acessar .nome em perfil.empresa=None
            print(f"  -> ERRO ao acessar dados do perfil: {e}")
        except Exception as e:
            # Captura outros erros inesperados
            print(f"  -> ERRO inesperado: {e}")

    print("\n--- Verificação Concluída ---")

if __name__ == "__main__":
    check_api_configs()
