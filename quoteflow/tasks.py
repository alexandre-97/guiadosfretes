# /web/staging.mudancasja/quoteflow/tasks.py

import os
import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

# --- Modelos ---
from .models import Cotacao
from perfil.models import ConfiguracaoEmail, Empresa

# --- Funções Utilitárias ---
from .utils import (
    gerar_numero_proposta,
    criar_replacements,
    gerar_proposta_word,
    enviar_email_proposta,
    gerar_mensagem_whatsapp,
    enviar_whatsapp_com_pdf_task,
    # ⭐️ 1. IMPORTE AS EXCEÇÕES DE WHATSAPP DO UTILS ⭐️
    WhatsAppNumberInvalidException,
    WhatsAppInstanceDisconnectedException
)
from .services import carregar_cotacoes_email
from .asaas_service import gerar_cobranca_pix_mensal

logger = logging.getLogger(__name__)
User = get_user_model()


# ==============================================================================
# TASKS DE ENVIO PARA A FUNÇÃO DE "ENVIO EM MASSA" E SÍNCRONO
# ==============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def enviar_apenas_email_task(self, cotacao_id, user_id, output_pdf_path=None, output_pdf_filename=None):
    """
    Task Celery para gerar a proposta e enviá-la por e-mail, com retentativa.
    (Esta função permanece sem alterações)
    """
    logger.info(f"[TASK] Iniciando envio de e-mail para cotação ID: {cotacao_id}")
    try:
        user = User.objects.get(id=user_id)
        cotacao = Cotacao.objects.get(id=cotacao_id)
        
        if not hasattr(user, 'perfil') or not user.perfil.empresa:
            raise Exception('Usuário sem perfil ou empresa associada.')

        empresa_usuario = user.perfil.empresa
        
        if not cotacao.email or '@' not in cotacao.email:
            logger.warning(f"[TASK] Cotação {cotacao_id} sem e-mail válido. Pulando.")
            return

        numero_proposta = gerar_numero_proposta(cotacao)

        if not output_pdf_path or not output_pdf_filename:
            logger.warning(f"[TASK] Gerando PDF de fallback para e-mail da cotação {cotacao_id}.")
            replacements = criar_replacements(cotacao, numero_proposta, user)
            if not empresa_usuario.template_proposta:
                raise Exception(f"Template não configurado para empresa ID: {empresa_usuario.id}.")
            template_path = empresa_usuario.template_proposta.path
            output_pdf_path, output_pdf_filename, _ = gerar_proposta_word(
                cotacao=cotacao,
                replacements=replacements,
                empresa_usuario=empresa_usuario,
                template_path=template_path,
                user=user
            )

        config_email = ConfiguracaoEmail.objects.get(empresa=empresa_usuario)
        enviar_email_proposta(
            config_email, cotacao, output_pdf_path,
            output_pdf_filename, numero_proposta, empresa_usuario, user
        )

        cotacao.refresh_from_db()
        status_atual = cotacao.status_envio or ''
        if 'Enviado Email' not in status_atual:
            cotacao.status_envio = 'Enviado Whats + Email' if 'Enviado Whats' in status_atual else 'Enviado Email'
        
        cotacao.proposta_gerada = os.path.join('propostas', output_pdf_filename)
        cotacao.save()
        logger.info(f"[TASK] E-mail para cotação {cotacao_id} processado com sucesso.")

    except (Cotacao.DoesNotExist, User.DoesNotExist, ConfiguracaoEmail.DoesNotExist) as e:
        logger.error(f"[TASK] Erro de objeto não encontrado para cotação {cotacao_id}: {e}")
    except Exception as exc:
        logger.error(f"[TASK] Falha na task de e-mail para cotação {cotacao_id}: {exc}")
        self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def enviar_apenas_whatsapp_task(self, cotacao_id, user_id, caminho_pdf=None, nome_arquivo_pdf=None):
    """
    Task Celery para gerar a proposta e enviá-la por WhatsApp.
    ⭐️ MODIFICADA para capturar erros de número inválido. ⭐️
    """
    logger.info(f"[TASK] Iniciando envio de WhatsApp para cotação ID: {cotacao_id}")
    cotacao = None # Define cotacao aqui para o bloco except ter acesso
    try:
        user = User.objects.get(id=user_id)
        cotacao = Cotacao.objects.get(id=cotacao_id)

        if not (hasattr(user, 'perfil') and user.perfil.tem_api_whatsapp()):
            logger.warning(f"[TASK] Usuário {user.username} sem API de WhatsApp. Pulando cotação {cotacao_id}.")
            return

        empresa_usuario = user.perfil.empresa
        
        if not cotacao.telefone or len(str(cotacao.telefone)) < 8:
            logger.warning(f"[TASK] Cotação {cotacao_id} sem telefone válido. Atualizando status.")
            cotacao.status_envio = 'Erro: Telefone Inválido'
            cotacao.save(update_fields=['status_envio'])
            return

        numero_proposta = gerar_numero_proposta(cotacao)

        if not caminho_pdf or not nome_arquivo_pdf:
            logger.warning(f"[TASK] Gerando PDF de fallback para WhatsApp da cotação {cotacao_id}.")
            replacements = criar_replacements(cotacao, numero_proposta, user)
            if not empresa_usuario.template_proposta:
                raise Exception(f"Template não configurado para empresa ID: {empresa_usuario.id}.")
            template_path = empresa_usuario.template_proposta.path
            caminho_pdf, nome_arquivo_pdf, _ = gerar_proposta_word(
                cotacao=cotacao,
                replacements=replacements,
                empresa_usuario=empresa_usuario,
                template_path=template_path,
                user=user
            )

        legenda = gerar_mensagem_whatsapp(cotacao, empresa_usuario, user, numero_proposta)
        
        # Esta função (do utils.py) agora vai chamar _check_number_self_hosted
        # e VAI LEVANTAR a exceção se o número for inválido.
        resultado = enviar_whatsapp_com_pdf_task(
            user=user, cotacao=cotacao, caminho_pdf=caminho_pdf,
            nome_arquivo_pdf=nome_arquivo_pdf, legenda=legenda
        )

        # Se chegou aqui, o envio foi bem-sucedido
        cotacao.refresh_from_db()
        status_atual = cotacao.status_envio or ''
        if 'Enviado Whats' not in status_atual:
            cotacao.status_envio = 'Enviado Whats + Email' if 'Enviado Email' in status_atual else 'Enviado Whats'
        
        cotacao.proposta_gerada = os.path.join('propostas', nome_arquivo_pdf)
        cotacao.save()
        logger.info(f"[TASK] WhatsApp para cotação {cotacao_id} processado com sucesso.")

    except (Cotacao.DoesNotExist, User.DoesNotExist) as e:
        logger.error(f"[TASK] Erro de objeto não encontrado para cotação {cotacao_id}: {e}")
        # Não há cotação para atualizar, apenas sai.

    # ⭐️ 2. BLOCO EXCEPT ATUALIZADO ⭐️
    except (WhatsAppNumberInvalidException, WhatsAppInstanceDisconnectedException) as e_whats:
        # Captura os erros específicos que NÃO DEVEM tentar novamente.
        error_message = str(e_whats)
        logger.warning(f"[TASK] Falha permanente de WhatsApp na cotação {cotacao_id}: {error_message}")
        if cotacao:
            # Atualiza o status da cotação para o usuário ver o erro
            if "não existe" in error_message or "inválido" in error_message:
                cotacao.status_envio = "Erro: Número Inválido"
            elif "desconectada" in error_message or "offline" in error_message:
                cotacao.status_envio = "Erro: API Desconectada"
            else:
                cotacao.status_envio = "Erro no Envio"
            cotacao.save(update_fields=['status_envio'])
        # NÃO dá self.retry(exc=exc) pois o erro é permanente.

    except Exception as exc:
        # Erros genéricos (ex: falha de rede, PDF, etc.)
        logger.error(f"[TASK] Falha genérica na task de WhatsApp para cotação {cotacao_id}: {exc}", exc_info=True)
        if cotacao:
            cotacao.status_envio = "Erro: Falha na Tarefa"
            cotacao.save(update_fields=['status_envio'])
        
        # Tenta novamente, pois pode ser um erro temporário (como a lógica original)
        self.retry(exc=exc)
    # ⭐️ FIM DA CORREÇÃO ⭐️


# ==============================================================================
# OUTRAS TASKS
# ==============================================================================

@shared_task(bind=True, max_retries=3, countdown=300)
def carregar_cotacoes_async(self, empresa_id):
    # ... (código mantido) ...
    try:
        empresa = Empresa.objects.get(pk=empresa_id)
        result = carregar_cotacoes_email(empresa)
        return result
    except Exception as e:
        logger.error(f"ERRO ao carregar cotações para empresa {empresa_id}: {e}", exc_info=True)
        self.retry(exc=e)


@shared_task
def gerar_cobrancas_pix_do_mes():
    # ... (código mantido) ...
    data_gatilho = timezone.now().date() + timedelta(days=7)
    empresas_para_cobrar = Empresa.objects.filter(
        status_assinatura='ATIVA',
        data_vencimento=data_gatilho
    )
    logger.info(f"Iniciando tarefa de geração de cobranças. {empresas_para_cobrar.count()} empresa(s) para processar.")
    for empresa in empresas_para_cobrar:
        try:
            dados_cobranca = gerar_cobranca_pix_mensal(empresa)
            # notificar_cliente_nova_cobranca_task.delay(empresa.id, dados_cobranca)
            logger.info(f"Cobrança para '{empresa.nome}' processada com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao gerar cobrança PIX para a empresa '{empresa.nome}' (ID: {empresa.id}): {e}")