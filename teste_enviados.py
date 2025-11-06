from django.core.mail import EmailMessage
from perfil.models import ConfiguracaoEmail
from quoteflow.utils import salvar_email_enviado

def teste_enviados():
    print("=== TESTE DE ENVIADOS ===")
    
    try:
        # 1. Obter configuração
        config = ConfiguracaoEmail.objects.first()
        if not config:
            print("ERRO: Nenhuma configuração de email encontrada")
            return False
        
        print(f"Usando conta: {config.email}")
        print(f"Servidor IMAP: {config.servidor_imap}:{config.porta_imap}")
        
        # 2. Criar mensagem de teste
        msg = EmailMessage(
            subject="TESTE - Salvamento em Enviados",
            body="Este é um teste de salvamento na pasta Enviados",
            from_email=config.email,
            to=[config.email]  # Enviar para si mesmo
        )
        
        # 3. Executar teste
        print("Executando teste...")
        resultado = salvar_email_enviado(config, msg)
        
        # 4. Resultado
        print("\n=== RESULTADO ===")
        print("Sucesso!" if resultado else "Falha!")
        return resultado
        
    except Exception as e:
        print(f"ERRO NO TESTE: {str(e)}")
        return False

if __name__ == '__main__':
    teste_enviados()
