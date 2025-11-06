import sys
import json
import os
import time
import logging
import imaplib
import email
from email.header import decode_header
from datetime import timedelta
from urllib.parse import quote, unquote

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, ExpressionWrapper, F, fields, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import Http404, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
import smtplib
import ssl
from perfil.models import ConfiguracaoEmail, Perfil, Empresa
from django.core.mail import send_mail, EmailMultiAlternatives
from django.core import mail
from .forms import CotacaoForm, FAQForm, PerfilForm, UpdatePostForm, CadastroForm
from .models import Cotacao, FAQ, UpdatePost, UserUpdateStatus
from .services import (determinar_rastreio, extrair_dominio_email,
                       inferir_tipo_frete, limpar_html_e_normalizar,
                       parse_cotefrete, parse_guia, parse_transvias_email,
                       parse_guiamudanca, parse_cargas)
from .tasks import enviar_apenas_email_task, enviar_apenas_whatsapp_task
from .utils import (WhatsAppInstanceDisconnectedException,
                    WhatsAppNumberInvalidException, criar_replacements,
                    enviar_email_proposta, enviar_email_simples,
                    enviar_proposta_sincrono, enviar_whatsapp,
                    enviar_whatsapp_com_pdf, gerar_html_formulario_coleta,
                    gerar_html_solicitacao_medidas,
                    gerar_html_solicitacao_pagamento,
                    gerar_mensagem_coleta_whatsapp, gerar_mensagem_pagamento,
                    gerar_mensagem_solicitacao_medidas, gerar_mensagem_whatsapp,
                    gerar_numero_proposta, gerar_proposta_word, log_action,
                    obter_assinatura_digital)
from .asaas_service import _get_headers
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse


logger = logging.getLogger(__name__)

# ==============================================================================
# FUNÇÕES AUXILIARES PRINCIPAIS
# ==============================================================================

def get_cotacao_queryset(request):
    """Função auxiliar para obter o queryset base filtrado por empresa."""
    try:
        if hasattr(request.user, 'perfil') and request.user.perfil and request.user.perfil.empresa:
            empresa_usuario = request.user.perfil.empresa
        else:
            empresa_usuario = None
    except Exception:
        empresa_usuario = None
    
    if request.user.is_superuser:
        return Cotacao.objects.all()
    elif empresa_usuario:
        return Cotacao.objects.filter(empresa=empresa_usuario)
    else:
        return Cotacao.objects.none()

def get_cotacao_by_proposta_id(request, proposta_id):
    """
    Busca uma cotação pelo ID da proposta (ex: 'EXI123QF') e garante
    que o usuário logado tenha permissão para vê-la.
    """
    try:
        empresa_prefixo = proposta_id[:3].upper()
        sequencial_str = proposta_id[3:-2]
        sequencial = int(sequencial_str)
    except (ValueError, IndexError):
        raise Http404("Formato do ID da proposta é inválido.")

    queryset = get_cotacao_queryset(request)
    cotacao = get_object_or_404(
        queryset,
        empresa__nome__istartswith=empresa_prefixo,
        numero_sequencial_empresa=sequencial
    )
    return cotacao

# ==============================================================================
# VIEWS PRINCIPAIS (ADAPTADAS)
# ==============================================================================

def home_redirect(request):
    if request.user.is_authenticated:
        return redirect('quoteflow:cotacao_list')
    return redirect('perfil:login')

@login_required
def cotacao_list(request):

    usuarios_empresa = []
    if hasattr(request.user, 'perfil') and request.user.perfil.empresa:
        usuarios_empresa = User.objects.filter(
            perfil__empresa=request.user.perfil.empresa
        ).select_related('perfil').order_by('first_name', 'last_name')

    # 1. Busca os dados na ordem correta: mais recentes primeiro.
    cotacoes_list = get_cotacao_queryset(request).order_by('-data_recebimento', '-id')
    paginator = Paginator(cotacoes_list, 10)

    # 2. Pega o número da página que o USUÁRIO VÊ na URL.
    #    O padrão é a última página (ex: 5 de 5).
    try:
        display_page_num = int(request.GET.get('page', paginator.num_pages))
    except (ValueError, TypeError):
        display_page_num = paginator.num_pages

    # 3. TRADUÇÃO: Calcula a página REAL que o Paginator precisa buscar.
    #    Se o usuário pede a página 5 (de 5), a página real de dados é a 1.
    #    Se o usuário pede a página 4, a página real é a 2. E assim por diante.
    real_page_num = (paginator.num_pages - display_page_num) + 1

    # 4. Busca o objeto da página usando o número REAL.
    page_obj = paginator.get_page(real_page_num)


    # 5. Prepara o contexto para o template.
    context = {
        'cotacoes': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        # Envia os números de página já na ordem invertida para o loop.
        'page_range_reversed': range(paginator.num_pages, 0, -1),
        # Envia o número da página que o usuário está vendo.
        'current_page_num': display_page_num,
        # Envia o número da última página para a lógica dos botões.
        'last_page_num': paginator.num_pages,
        'usuarios_empresa': usuarios_empresa,
    }
    
    return render(request, 'cotacoes/lista.html', context)
@login_required
@require_POST
def designar_responsavel_ajax(request):
    try:
        data = json.loads(request.body)
        cotacao_id = data.get('cotacao_id')
        novo_responsavel_id = data.get('responsavel_id')

        # Validações de segurança
        cotacao = get_object_or_404(Cotacao, id=cotacao_id, empresa=request.user.perfil.empresa)
        novo_responsavel = get_object_or_404(User, id=novo_responsavel_id, perfil__empresa=request.user.perfil.empresa)

        cotacao.responsavel = novo_responsavel
        cotacao.save(update_fields=['responsavel'])
        
        nome_responsavel = novo_responsavel.perfil.nome_completo or novo_responsavel.username
        return JsonResponse({'success': True, 'message': 'Responsável atualizado!', 'novo_responsavel_nome': nome_responsavel})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_POST
def designar_responsavel_massa_ajax(request):
    try:
        data = json.loads(request.body)
        cotacao_ids = data.get('cotacao_ids', [])
        novo_responsavel_id = data.get('responsavel_id')

        if not cotacao_ids:
            return JsonResponse({'success': False, 'error': 'Nenhuma cotação selecionada.'}, status=400)

        # Validações de segurança
        novo_responsavel = get_object_or_404(User, id=novo_responsavel_id, perfil__empresa=request.user.perfil.empresa)
        
        with transaction.atomic():
            cotacoes_a_alterar = Cotacao.objects.filter(
                id__in=cotacao_ids,
                empresa=request.user.perfil.empresa
            )
            
            # Conta quantas cotações realmente foram alteradas
            num_alteradas = cotacoes_a_alterar.update(responsavel=novo_responsavel)

        return JsonResponse({'success': True, 'message': f'{num_alteradas} cotações atualizadas com sucesso!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def cotacao_create(request):
    user = request.user
    try:
        empresa_usuario = user.perfil.empresa
    except AttributeError:
        messages.error(request, 'Seu usuário não está associado a uma empresa válida.')
        return redirect('quoteflow:cotacao_list')

    if request.method == 'POST':
        form = CotacaoForm(request.POST, request.FILES, user=user)
        if form.is_valid():
            try:
                cotacao = form.save(commit=False)
                cotacao.responsavel = user
                cotacao.empresa = empresa_usuario
                cotacao.save()
                
                messages.success(request, f'Cotação #{cotacao.proposta_id_url} criada! Agora você já pode executar as ações.')
                
                return redirect('quoteflow:cotacao_edit', proposta_id=cotacao.proposta_id_url)
            except Exception as e:
                messages.error(request, f'Erro ao criar cotação: {str(e)}')
    else:
        form = CotacaoForm(user=user)

    return render(request, 'cotacoes/cotacao_form.html', {
        'form': form,
        'titulo': 'Nova Cotação'
    })

@login_required
def cotacao_edit(request, proposta_id):
    try:
        cotacao = get_cotacao_by_proposta_id(request, proposta_id)
    except Http404:
        messages.error(request, "Cotação não encontrada ou você não tem permissão para acessá-la.")
        return redirect('quoteflow:cotacao_list')

    user = request.user
    decoded_filtrar_status = request.GET.get('filtrar_status')

    if request.method == 'POST':
        form = CotacaoForm(request.POST, request.FILES, instance=cotacao, user=user)
        if form.is_valid():
            try:
                cotacao_instance = form.save(commit=False)
                cotacao_instance.responsavel = user
                cotacao_instance.save()
                
                messages.success(request, 'Cotação atualizada com sucesso!')
                
                redirect_url = reverse('quoteflow:cotacao_edit', kwargs={'proposta_id': cotacao.proposta_id_url})
                if decoded_filtrar_status:
                    return redirect(f"{redirect_url}?filtrar_status={quote(decoded_filtrar_status)}")
                return redirect(redirect_url)
            except Exception as e:
                 messages.error(request, f'Erro ao salvar: {str(e)}')
        else:
            messages.error(request, 'Erro ao salvar. Verifique os dados.')
    else:
        form = CotacaoForm(instance=cotacao, user=user)

    base_queryset = get_cotacao_queryset(request)
    if decoded_filtrar_status:
        base_queryset = base_queryset.filter(status_envio__iexact=decoded_filtrar_status)

    anterior = base_queryset.filter(pk__lt=cotacao.pk).order_by('-pk').first()
    proxima = base_queryset.filter(pk__gt=cotacao.pk).order_by('pk').first()

    # --- LÓGICA ADICIONADA PARA POPULAR O MODAL DE PAGAMENTO ---
    empresa = cotacao.empresa
    
    # Calcula o valor de 50%
    valor_proposta_decimal = cotacao.valor_proposta or 0
    valor_50_percento = valor_proposta_decimal / 2
    
    # Monta o dicionário com os dados bancários da empresa
    dados_bancarios = {
        'banco': empresa.banco if empresa else "Não informado",
        'agencia_conta': empresa.agencia_conta if empresa else "Não informado",
        'pix': empresa.pix if empresa else "Não informado",
        'razao_social': (empresa.razao_social or empresa.nome_full or empresa.nome) if empresa else "Não informado"
    }
    
    # Adiciona os novos dados ao contexto que será enviado para o template
    context = {
        'form': form,
        'cotacao': cotacao,
        'anterior': anterior,
        'proxima': proxima,
        'filtrar_status': decoded_filtrar_status,
        'dados_bancarios': dados_bancarios,
        'valor_50_percento': valor_50_percento,
    }
    
    return render(request, 'cotacoes/editar.html', context)


# ==============================================================================
# VIEWS DE AÇÃO (ADAPTADAS)
# ==============================================================================

@login_required
def enviar_cotacao(request, proposta_id):
    try:
        cotacao = get_cotacao_by_proposta_id(request, proposta_id)
        log_action(logger, 'info', request.user, "Iniciou o envio de proposta (e-mail e/ou WhatsApp).", cotacao)
        resultado = enviar_proposta_sincrono(cotacao.id, request.user.id)
        
        # --- LÓGICA DE MENSAGEM APRIMORADA ---
        if resultado.get('sucesso_geral'):
            canais_sucesso = []
            if resultado.get('enviado_email'):
                canais_sucesso.append('E-mail')
            if resultado.get('enviado_whatsapp'):
                canais_sucesso.append('WhatsApp')
            
            # Constrói a mensagem de sucesso dinamicamente
            if canais_sucesso:
                mensagem_sucesso = f"Proposta enviada por {' e '.join(canais_sucesso)}."
                messages.success(request, mensagem_sucesso)

            # Mantém a exibição de erros parciais, caso um dos canais tenha falhado
            if resultado.get('erros'):
                messages.warning(request, f"Ocorreram falhas: {'; '.join(resultado['erros'])}")
        else:
            # Se nenhum canal teve sucesso, exibe a mensagem de erro principal
            messages.error(request, f"Falha ao enviar proposta: {', '.join(resultado.get('erros', ['Erro desconhecido']))}")
            
    except Http404:
        messages.error(request, "Cotação não encontrada.")
        return redirect('quoteflow:cotacao_list')
    except Exception as e:
        messages.error(request, f'Um erro inesperado ocorreu: {str(e)}')
    
    return redirect('quoteflow:cotacao_edit', proposta_id=proposta_id)

@login_required
def solicitar_medidas(request, proposta_id):
    try:
        cotacao = get_cotacao_by_proposta_id(request, proposta_id)
        log_action(logger, 'info', request.user, "Iniciou a solicitação de medidas.", cotacao)
        user = request.user
        empresa = cotacao.empresa
        numero_proposta = gerar_numero_proposta(cotacao)
        canais_enviados = []

        # --- Envio por WhatsApp (Usa a função antiga que agora tem negrito) ---
        if cotacao.telefone and len(cotacao.telefone.strip()) >= 8:
            try:
                mensagem_whatsapp = gerar_mensagem_solicitacao_medidas(cotacao, user)
                enviar_whatsapp(request, cotacao, mensagem=mensagem_whatsapp)
                canais_enviados.append('WhatsApp')
            except Exception as e:
                messages.warning(request, f'Falha ao enviar WhatsApp: {str(e)}')
        
        # --- Envio por Email (Usa a NOVA função e o NOVO template) ---
        if cotacao.email and '@' in cotacao.email:
            try:
                config_email = ConfiguracaoEmail.objects.get(empresa=empresa)
                assunto = f"Solicitação de Medidas - Cotação {numero_proposta}"
                
                # Gera a assinatura e o HTML separadamente
                assinatura_digital = obter_assinatura_digital(user, empresa)
                mensagem_html = gerar_html_solicitacao_medidas(cotacao, numero_proposta, empresa, assinatura_digital)
                
                # Envia o e-mail já formatado em HTML
                enviar_email_simples(config_email, cotacao, assunto, mensagem_html, user, is_html=True)
                canais_enviados.append('Email')
            except Exception as e:
                messages.warning(request, f'Falha ao enviar email: {str(e)}')

        if canais_enviados:
            cotacao.status_envio = 'Faltam Medidas'
            cotacao.save()
            messages.success(request, f'Solicitação de medidas enviada por {", ".join(canais_enviados)}.')
        else:
            messages.warning(request, 'Nenhum canal conseguiu enviar a solicitação.')

    except Http404:
        messages.error(request, "Cotação não encontrada.")
        return redirect('quoteflow:cotacao_list')
    except Exception as e:
        messages.error(request, f'Erro ao enviar solicitação: {str(e)}')

    return redirect('quoteflow:cotacao_edit', proposta_id=proposta_id)

@login_required
def enviar_whatsapp_view(request, proposta_id):
    try:
        cotacao = get_cotacao_by_proposta_id(request, proposta_id)
        user = request.user
        empresa_usuario = user.perfil.empresa

        if not cotacao.telefone:
            raise Exception('Número de WhatsApp não cadastrado para esta cotação')

        numero_proposta = gerar_numero_proposta(cotacao)
        mensagem = gerar_mensagem_whatsapp(cotacao, empresa_usuario, user, numero_proposta)
        resultado = enviar_whatsapp(request, cotacao, mensagem)

        if 'redirect' in resultado:
            return redirect(resultado['redirect'])

        if 'Enviado Whats' not in (cotacao.status_envio or ''):
            if cotacao.status_envio and 'Enviado Email' in cotacao.status_envio:
                cotacao.status_envio = 'Enviado Whats + Email'
            else:
                cotacao.status_envio = 'Enviado Whats'
            cotacao.save()
        messages.success(request, f'Proposta {numero_proposta} enviada por WhatsApp com sucesso!')
    except Http404:
        messages.error(request, "Cotação não encontrada.")
        return redirect('quoteflow:cotacao_list')
    except Exception as e:
        messages.error(request, f'Erro ao enviar WhatsApp: {str(e)}')
    
    return redirect('quoteflow:cotacao_edit', proposta_id=proposta_id)

@login_required
def enviar_apenas_whatsapp(request, proposta_id):
    try:
        cotacao = get_cotacao_by_proposta_id(request, proposta_id)
        log_action(logger, 'info', request.user, "Iniciou o envio de proposta APENAS por WhatsApp.", cotacao)
        user = request.user
        empresa_usuario = user.perfil.empresa

        if not cotacao.telefone:
            raise Exception('Número de WhatsApp não cadastrado')

        numero_proposta = gerar_numero_proposta(cotacao)
        template_path = empresa_usuario.template_proposta.path
        caminho_pdf, nome_arquivo_pdf, _ = gerar_proposta_word(
            cotacao=cotacao,
            replacements=criar_replacements(cotacao, numero_proposta, user),
            empresa_usuario=empresa_usuario,
            template_path=template_path,
            user=user
        )
        legenda = gerar_mensagem_whatsapp(cotacao, empresa_usuario, user, numero_proposta)
        
        # Chamada direta para a função síncrona com tratamento de erro
        resultado = enviar_whatsapp_com_pdf(request, cotacao, caminho_pdf, nome_arquivo_pdf, legenda)

        # Atualização de status
        cotacao.refresh_from_db()
        status_atual = cotacao.status_envio or ''
        if 'Enviado Whats' not in status_atual:
            cotacao.status_envio = 'Enviado Whats + Email' if 'Enviado Email' in status_atual else 'Enviado Whats'
        cotacao.proposta_gerada = os.path.join('propostas', nome_arquivo_pdf)
        cotacao.save()

        if 'redirect' in resultado:
            return redirect(resultado['redirect'])
        
        messages.success(request, f'Proposta {numero_proposta} enviada por WhatsApp!')

    except Http404:
        messages.error(request, "Cotação não encontrada.")
        return redirect('quoteflow:cotacao_list')

    # --- BLOCO DE EXCEÇÕES CORRIGIDO ---
    except WhatsAppInstanceDisconnectedException as e:
        messages.error(request, f'Falha no envio: {str(e)}')
    except WhatsAppNumberInvalidException as e:
        messages.error(request, f"Falha no envio: {str(e)} Por favor, corrija o número e tente novamente.")
    except Exception as e:
        logger.error(f"Erro na view enviar_apenas_whatsapp para cotação {proposta_id}: {e}", exc_info=True)
        messages.error(request, f'Erro ao preparar envio WhatsApp: {str(e)}')
    
    return redirect('quoteflow:cotacao_edit', proposta_id=proposta_id)


@login_required
def enviar_solicitacao_coleta(request, proposta_id):
    try:
        cotacao = get_cotacao_by_proposta_id(request, proposta_id)
        log_action(logger, 'info', request.user, "Iniciou a solicitação de coleta.", cotacao)
        user = request.user
        empresa = cotacao.empresa
        numero_proposta = gerar_numero_proposta(cotacao)
        
        canais_enviados = []

        # --- Envio por WhatsApp ---
        if cotacao.telefone and len(cotacao.telefone.strip()) >= 8:
            try:
                mensagem_whatsapp = gerar_mensagem_coleta_whatsapp(cotacao, numero_proposta)
                enviar_whatsapp(request, cotacao, mensagem=mensagem_whatsapp)
                canais_enviados.append('WhatsApp')
            except Exception as e:
                messages.warning(request, f'Falha ao enviar por WhatsApp: {str(e)}')

        # --- Envio por Email ---
        if cotacao.email and '@' in cotacao.email:
            try:
                config_email = ConfiguracaoEmail.objects.get(empresa=empresa)
                assunto = f"FORMULÁRIO DE COLETA: Proposta {numero_proposta}"

                # ===== PONTO DA CORREÇÃO AQUI =====
                # 1. A assinatura digital precisa ser gerada ANTES de chamar a função do e-mail.
                assinatura_digital = obter_assinatura_digital(user, empresa)
                
                # 2. Agora passamos os 4 argumentos que a função espera: cotacao, numero_proposta, empresa e assinatura_digital.
                mensagem_html = gerar_html_formulario_coleta(cotacao, numero_proposta, empresa, assinatura_digital)
                # ==================================
                
                enviar_email_simples(config_email, cotacao, assunto, mensagem_html, user, is_html=True)
                canais_enviados.append('Email')
            except ConfiguracaoEmail.DoesNotExist:
                messages.warning(request, f"Não foi possível enviar por Email: As configurações de e-mail para '{empresa.nome}' não foram encontradas.")
            except Exception as e:
                # O erro que você viu será capturado aqui e exibido de forma amigável
                messages.warning(request, f'Falha ao enviar por Email: {str(e)}')

        # --- Feedback Final ---
        if canais_enviados:
            # Atualiza o status apenas se pelo menos um canal teve sucesso
            if 'Email' in canais_enviados:
                cotacao.status_cotacao = 'Coleta Solicitada'
                cotacao.save()
            messages.success(request, f'Solicitação de coleta enviada com sucesso por: {", ".join(canais_enviados)}.')
        else:
            messages.error(request, 'Falha no envio. Verifique os dados de contato (email e telefone) da cotação e tente novamente.')

    except Http404:
        messages.error(request, "Cotação não encontrada.")
        return redirect('quoteflow:cotacao_list')
    except Exception as e:
        logger.error(f"Erro inesperado ao processar solicitação de coleta para cotação {proposta_id}: {e}", exc_info=True)
        messages.error(request, f"Ocorreu um erro inesperado: {str(e)}")
    
    return redirect('quoteflow:cotacao_edit', proposta_id=proposta_id)


@login_required
def solicitar_pagamento(request, proposta_id):
    try:
        cotacao = get_cotacao_by_proposta_id(request, proposta_id)
        user = request.user
        empresa = cotacao.empresa

        if request.method == 'POST':
            log_action(logger, 'info', request.user, "Iniciou a solicitação de pagamento.", cotacao)
            status_mercadoria = request.POST.get('status_mercadoria')
            percentual_str = request.POST.get('percentual')
            mensagem_adicional = request.POST.get('mensagem_adicional', '')

            if not status_mercadoria or not percentual_str:
                messages.error(request, 'Por favor, selecione o status da mercadoria e o percentual.')
                return redirect('quoteflow:solicitar_pagamento', proposta_id=proposta_id)

            percentual = int(percentual_str)

            dados_mensagem = gerar_mensagem_pagamento(
                cotacao=cotacao,
                empresa=empresa,
                user=user,
                percentual=percentual,
                status_mercadoria=status_mercadoria,
                mensagem_adicional=mensagem_adicional
            )
            
            mensagem_whatsapp = dados_mensagem['mensagem_whatsapp']
            numero_proposta = dados_mensagem['numero_proposta']
            canais_enviados = []

            # Envia por WhatsApp
            if cotacao.telefone and len(cotacao.telefone.strip()) >= 8:
                try:
                    enviar_whatsapp(request, cotacao, mensagem=mensagem_whatsapp)
                    canais_enviados.append('WhatsApp')
                except Exception as e:
                    messages.warning(request, f'Falha ao enviar por WhatsApp: {str(e)}')

            # Envia por Email
            if cotacao.email and '@' in cotacao.email:
                try:
                    config_email = ConfiguracaoEmail.objects.get(empresa=empresa)
                    assunto = f"Solicitação de Pagamento - Cotação {numero_proposta}"
                    
                    assinatura_digital = obter_assinatura_digital(user, empresa)
                    mensagem_html = gerar_html_solicitacao_pagamento(
                        cotacao, 
                        numero_proposta, 
                        empresa, 
                        assinatura_digital, 
                        dados_mensagem
                    )
                    
                    enviar_email_simples(config_email, cotacao, assunto, mensagem_html, user, is_html=True)
                    canais_enviados.append('Email')
                except Exception as e:
                    messages.warning(request, f'Falha ao enviar por email: {str(e)}')
            
            if canais_enviados:
                cotacao.status_envio = 'Aguardando Pagamento'
                cotacao.save()
                messages.success(request, f'Solicitação de pagamento enviada por {", ".join(canais_enviados)}.')
            else:
                messages.error(request, 'Não foi possível enviar a solicitação. Verifique o contato do cliente.')
            
            return redirect('quoteflow:cotacao_edit', proposta_id=proposta_id)

        # A lógica do GET (carregamento da página) continua a mesma
        else:
            valor_proposta_decimal = cotacao.valor_proposta or 0
            valor_50_percento = valor_proposta_decimal / 2
            dados_bancarios = {
                'banco': empresa.banco or "Não informado",
                'agencia_conta': empresa.agencia_conta or "Não informado",
                'pix': empresa.pix or "Não informado",
                'razao_social': empresa.razao_social or empresa.nome_full or empresa.nome
            }
            context = {
                'cotacao': cotacao,
                'dados_bancarios': dados_bancarios,
                'valor_50_percento': valor_50_percento,
            }
            return render(request, 'cotacoes/solicitar_pagamento.html', context)

    # ... (bloco de except continua o mesmo)
    except Http404:
        messages.error(request, "Cotação não encontrada ou você não tem permissão para acessá-la.")
        return redirect('quoteflow:cotacao_list')
    except Exception as e:
        logger.error(f"Erro inesperado em solicitar_pagamento: {str(e)}", exc_info=True)
        messages.error(request, f"Ocorreu um erro inesperado no servidor: {str(e)}")
        if 'proposta_id' in locals():
            return redirect('quoteflow:cotacao_edit', proposta_id=proposta_id)
        return redirect('quoteflow:cotacao_list')


@login_required
def enviar_apenas_email(request, proposta_id):
    try:
        cotacao = get_cotacao_by_proposta_id(request, proposta_id)
        log_action(logger, 'info', request.user, "Iniciou o envio de proposta APENAS por e-mail.", cotacao)
        user = request.user
        empresa_usuario = user.perfil.empresa
        
        if not cotacao.email:
            raise Exception('Email não cadastrado para esta cotação')

        numero_proposta = gerar_numero_proposta(cotacao)
        template_path = empresa_usuario.template_proposta.path
        output_pdf_path, output_pdf_filename, _ = gerar_proposta_word(
            cotacao=cotacao,
            replacements=criar_replacements(cotacao, numero_proposta, user),
            empresa_usuario=empresa_usuario,
            template_path=template_path,
            user=user
        )
        config_email = ConfiguracaoEmail.objects.get(empresa=empresa_usuario)
        enviar_email_proposta(config_email, cotacao, output_pdf_path, output_pdf_filename, numero_proposta, empresa_usuario, user)

        if 'Enviado Email' not in (cotacao.status_envio or ''):
            cotacao.status_envio = 'Enviado Whats + Email' if 'Enviado Whats' in (cotacao.status_envio or '') else 'Enviado Email'
        cotacao.proposta_gerada = os.path.join('propostas', output_pdf_filename)
        cotacao.save()
        messages.success(request, f'Proposta {numero_proposta} enviada por email com sucesso!')
    except Http404:
        messages.error(request, "Cotação não encontrada.")
        return redirect('quoteflow:cotacao_list')
    except Exception as e:
        messages.error(request, f'Erro ao enviar email: {str(e)}')
    
    return redirect('quoteflow:cotacao_edit', proposta_id=proposta_id)

# ==============================================================================
# VIEWS DE BUSCA E OUTRAS (ADAPTADAS)
# ==============================================================================

@login_required
def buscar_por_id(request):
    id_numerico = request.GET.get('id')
    if not id_numerico or not id_numerico.isdigit():
        messages.error(request, "Por favor, insira um número de cotação válido.")
        return redirect('quoteflow:cotacao_list')
        
    try:
        base_queryset = get_cotacao_queryset(request)
        cotacao = get_object_or_404(base_queryset, pk=id_numerico)
        return redirect('quoteflow:cotacao_edit', proposta_id=cotacao.proposta_id_url)
    except Http404:
        messages.error(request, "Cotação não encontrada ou você não tem permissão para acessá-la")
        return redirect('quoteflow:cotacao_list')

@login_required
def carregar_novas_cotacoes(request):
    """
    Processa os e-mails e envia atualizações em tempo real (streaming) para o navegador.
    """
    def event_stream():
        try:
            empresa = request.user.perfil.empresa
            config = ConfiguracaoEmail.objects.get(empresa=empresa)
            
            if config.usar_ssl_imap:
                mail = imaplib.IMAP4_SSL(config.servidor_imap, config.porta_imap or 993)
            else:
                mail = imaplib.IMAP4(config.servidor_imap, config.porta_imap or 143)
            mail.login(config.email, config.senha)
            
            pasta_imap_db = config.pasta_imap or 'INBOX'
            pasta_imap_servidor = None
            status, pastas_raw = mail.list()
            if status == 'OK':
                for pasta_bytes in pastas_raw:
                    nome_pasta_servidor = pasta_bytes.decode().split(' "." ')[-1].strip('"')
                    if nome_pasta_servidor.lower() == pasta_imap_db.lower():
                        pasta_imap_servidor = nome_pasta_servidor
                        break
            if not pasta_imap_servidor:
                raise Exception(f"Pasta IMAP '{pasta_imap_db}' não encontrada.")
                
            mail.select(f'"{pasta_imap_servidor}"')
            status, messages = mail.search(None, 'UNSEEN')
            
            if status != 'OK' or not messages[0]:
                yield 'data: {"status": "done", "count": 0, "message": "Nenhuma nova cotação encontrada."}\n\n'
                mail.logout()
                return

            email_ids = messages[0].split()
            total_emails = len(email_ids)
            novas_cotacoes = 0
            
            # Envia um estado inicial para o frontend já com o total de e-mails
            yield f'data: {{"status": "processing", "total": {total_emails}, "count": 0, "created": 0}}\n\n'

            for i, email_id in enumerate(email_ids):
                try:
                    status, msg_data = mail.fetch(email_id, '(RFC822)')
                    if status != 'OK': continue
                    msg = email.message_from_bytes(msg_data[0][1])
                    msg_id = msg.get('Message-ID', '').strip()
                    if not msg_id or Cotacao.objects.filter(email_message_id=msg_id).exists(): continue
                    
                    subject = ''.join(p.decode(e or 'utf-8', 'ignore') if isinstance(p, bytes) else p for p, e in decode_header(msg.get('Subject', '')))
                    html_body, plain_body = None, None
                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype, cdisp = part.get_content_type(), str(part.get('Content-Disposition'))
                            if ctype == 'text/html' and 'attachment' not in cdisp: html_body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', 'ignore')
                            if ctype == 'text/plain' and 'attachment' not in cdisp: plain_body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', 'ignore')
                    else:
                        plain_body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', 'ignore')
                    
                    body_para_parse = html_body or plain_body
                    if not body_para_parse: continue
                    
                    remetente = msg.get('From', '')
                    dominio_remetente = extrair_dominio_email(remetente)
                    texto_puro_para_analise = limpar_html_e_normalizar(body_para_parse)
                    rastreio = determinar_rastreio(dominio_remetente, texto_puro_para_analise)
                    
                    dados = {}
                    if rastreio == 'Guia': dados = parse_guia(body_para_parse, msg)
                    elif rastreio == 'CoteFrete': dados = parse_cotefrete(texto_puro_para_analise)
                    elif rastreio == 'GuiaMudanca': dados = parse_guiamudanca(body_para_parse) # <-- ADICIONE ESTA LINHA
                    elif rastreio == 'Cargas': dados = parse_cargas(body_para_parse, msg)       # <-- ADICIONE ESTA LINHA
                    elif rastreio == 'Transvias': dados = parse_transvias_email(texto_puro_para_analise)
                    else:
                        dados_fallback = parse_transvias_email(texto_puro_para_analise)
                        if dados_fallback:
                            dados = dados_fallback
                            rastreio = 'Transvias (Inferido)'
                        else:
                            continue

                    if dados.get('origem') and dados.get('destino'):
                        Cotacao.objects.create(
                            empresa=empresa, 
                            origem=dados['origem'], 
                            destino=dados['destino'], 
                            # VALORES PADRÃO CORRIGIDOS AQUI
                            prazo_coleta='Até 24 horas', 
                            prazo_entrega='1 a 3 dias úteis', 
                            # O RESTANTE CONTINUA IGUAL
                            volumes=dados.get('volumes', 0) or 0, 
                            peso=dados.get('peso', 0.0) or 0.0, 
                            valor_mercadoria=dados.get('valor_mercadoria', 0.0) or 0.0, 
                            cubagem=dados.get('cubagem', 0.0), 
                            observacao=dados.get('observacao', ''), 
                            contato=dados.get('contato', ''), 
                            telefone=dados.get('telefone', ''), 
                            email=dados.get('email', ''), 
                            email_message_id=msg_id, 
                            status_cotacao="Em Negociação", 
                            status_envio='Falta Cubagem', 
                            tipo_frete=inferir_tipo_frete(subject), 
                            rastreio=rastreio
                        )
                        novas_cotacoes += 1
                except Exception as e:
                    logger.error(f"Falha ao processar e-mail individual ID {email_id}: {e}")
                
                # Envia o progresso atualizado após cada e-mail
                yield f'data: {{"status": "processing", "count": {i + 1}, "created": {novas_cotacoes}, "total": {total_emails}}}\n\n'
                
                # Adiciona uma pequena pausa para forçar o envio da resposta (flush),
                # melhorando a fluidez da atualização em tempo real.
                time.sleep(0.1)

            mail.logout()
            
            # --- LÓGICA DA MENSAGEM FINAL CORRIGIDA ---
            # Define a mensagem com base no número de cotações criadas.
            if novas_cotacoes == 1:
                final_message = "1 nova cotação foi carregada com sucesso!"
            elif novas_cotacoes > 1:
                final_message = f"{novas_cotacoes} novas cotações foram carregadas com sucesso!"
            else:  # Se novas_cotacoes for 0
                final_message = "Nenhuma nova cotação encontrada."

            yield f'data: {{"status": "done", "count": {novas_cotacoes}, "message": "{final_message}"}}\n\n'

        except Exception as e:
            logger.error(f"Erro no stream de carregamento: {e}", exc_info=True)
            yield f'data: {{"status": "error", "message": "Erro ao carregar cotações: {str(e)}"}}\n\n'

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response


class BuscaCotacoes(ListView):
    model = Cotacao
    template_name = 'cotacoes/busca_resultados.html'
    context_object_name = 'cotacoes'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        """
        Verifica se é uma nova busca e redireciona para a última página.
        """
        # Se o parâmetro 'termo' está na URL, mas 'page' não está...
        if 'termo' in request.GET and 'page' not in request.GET:
            
            # Executa a mesma lógica da busca para obter o queryset de resultados
            queryset = self.get_queryset(*args, **kwargs)
            
            # Se a busca retornou algum resultado...
            if queryset.exists():
                # Cria um paginador para descobrir o número da última página
                paginator = Paginator(queryset, self.paginate_by)
                last_page_num = paginator.num_pages

                # Se houver mais de uma página, redireciona
                if last_page_num > 0:
                    # Copia os parâmetros da URL atual (o 'termo')
                    query_params = request.GET.copy()
                    # Adiciona o parâmetro da última página
                    query_params['page'] = last_page_num
                    # Redireciona para a URL com a página correta
                    return redirect(f'{request.path}?{query_params.urlencode()}')

        # Se não for uma nova busca (ou se a página já estiver na URL), continua normalmente
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self, *args, **kwargs):
        # ... este método continua exatamente igual, sem alterações ...
        termo = self.request.GET.get('termo') or self.request.session.get('termo')
        qs = get_cotacao_queryset(self.request)
        if not termo:
            return qs.none()
        self.request.session['termo'] = termo
        termo_str = str(termo).strip()
        filtros = (
            Q(origem__icontains=termo_str) |
            Q(destino__icontains=termo_str) |
            Q(status_cotacao__icontains=termo_str) |
            Q(status_envio__icontains=termo_str) |
            Q(responsavel__username__icontains=termo_str) |
            Q(contato__icontains=termo_str)
        )
        try:
            if len(termo_str) > 5 and termo_str[-2:].upper() == 'QF':
                prefixo = termo_str[:3].upper()
                sequencial_str = termo_str[3:-2]
                sequencial = int(sequencial_str)
                filtros |= (
                    Q(empresa__nome__istartswith=prefixo) & 
                    Q(numero_sequencial_empresa=sequencial)
                )
        except (ValueError, IndexError):
            pass
        if termo_str.isdigit():
            numero = int(termo_str)
            filtros |= Q(id=numero)
            filtros |= Q(numero_sequencial_empresa=numero)
        return qs.filter(filtros).distinct()

    def get_context_data(self, **kwargs):
        # ... este método continua exatamente igual, sem alterações ...
        context = super().get_context_data(**kwargs)
        context['termo_busca'] = self.request.GET.get('termo', '')
        if context.get('is_paginated'):
            page_obj = context['page_obj']
            context['current_page_num'] = page_obj.number
            context['last_page_num'] = page_obj.paginator.num_pages
            context['page_range_reversed'] = range(page_obj.paginator.num_pages, 0, -1)
        return context
# ==============================================================================
# VIEWS DE API PARA ENVIO EM MASSA (CÓDIGO RESTAURADO E CORRIGIDO)
# ==============================================================================

@login_required
@require_GET
def carregar_cotacoes_envio_massa(request):
    """
    Carrega cotações para envio em massa, filtrando Corretamente
    pelo USUÁRIO RESPONSÁVEL, e não apenas pela empresa.
    """
    try:
        user = request.user
        if not hasattr(user, 'perfil') or not user.perfil.empresa:
            return JsonResponse({'error': 'Usuário ou empresa não configurado.', 'cotacoes': []}, status=400)
        
        # --- CORREÇÃO DE PERMISSÃO ---
        # Adicionado o filtro 'responsavel=user' para carregar apenas as cotações do usuário logado.
        cotacoes_qs = Cotacao.objects.filter(
            empresa=user.perfil.empresa,
            responsavel=user,  # <-- FILTRO ESSENCIAL ADICIONADO
            status_cotacao='Em Negociação',
        ).filter(
            Q(status_envio='Não Enviado') |
            Q(status_envio='Nao Enviado') |
            Q(status_envio__isnull=True)
        ).order_by('id')[:100]

        cotacoes_list = []
        for cotacao in cotacoes_qs:
            cotacoes_list.append({
                'id': cotacao.id,
                'proposta_id_url': cotacao.proposta_id_url,
                'origem': cotacao.origem,
                'destino': cotacao.destino,
                'contato': cotacao.contato,
            })

        return JsonResponse({
            'success': True,
            'cotacoes': cotacoes_list,
            'empresa': user.perfil.empresa.nome,
            'total': len(cotacoes_list)
        })
    except Exception as e:
        logger.error(f"Erro em carregar_cotacoes_envio_massa: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Erro interno ao carregar cotações'}, status=500)

@login_required
@require_POST
def enviar_cotacoes_massa(request):
    """
    (VERSÃO CORRIGIDA COM INTERVALO ALEATÓRIO)
    Enfileira cotações para envio em massa com um intervalo randomizado entre cada tarefa.
    """
    try:
        user = request.user
        if not hasattr(user, 'perfil') or not user.perfil.empresa:
            return JsonResponse({'error': 'Empresa não vinculada'}, status=400)

        cotacoes_para_enviar = Cotacao.objects.filter(
            empresa=user.perfil.empresa,
            responsavel=user,
            status_cotacao='Em Negociação',
        ).filter(
            Q(status_envio='Não Enviado') |
            Q(status_envio='Nao Enviado') |
            Q(status_envio__isnull=True)
        )[:50]

        total_enfileirado = cotacoes_para_enviar.count()

        if total_enfileirado == 0:
            return JsonResponse({'success': True, 'message': 'Nenhuma cotação sua para enviar.', 'total_enfileirado': 0})

        # --- INÍCIO DA IMPLEMENTAÇÃO DO INTERVALO ALEATÓRIO ---
        
        # Define um tempo de espera inicial (pode ser 0 para a primeira mensagem)
        delay_seconds = 0
        
        # Define o intervalo mínimo e máximo (em segundos) entre cada mensagem
        # DADO OS BANIMENTOS RECENTES, VAMOS USAR UM INTERVALO BEM CONSERVADOR
        intervalo_minimo = 3  # segundos
        intervalo_maximo = 8  # segundos
        
        for cotacao in cotacoes_para_enviar:
            # Enfileira a task de e-mail (e-mails não precisam de intervalo)
            if cotacao.email and '@' in cotacao.email:
                enviar_apenas_email_task.delay(cotacao.id, user.id)
            
            # Enfileira a task de WhatsApp com um agendamento (countdown)
            if cotacao.telefone and hasattr(user, 'perfil') and user.perfil.tem_api_whatsapp():
                
                # Usa .apply_async para agendar a tarefa para o futuro
                enviar_apenas_whatsapp_task.apply_async(
                    args=[cotacao.id, user.id],
                    countdown=delay_seconds
                )

                # Incrementa o tempo de espera para a PRÓXIMA mensagem com um valor aleatório
                delay_seconds += random.uniform(intervalo_minimo, intervalo_maximo)
        
        # --- FIM DA IMPLEMENTAÇÃO ---

        return JsonResponse({
            'success': True,
            'message': f'{total_enfileirado} cotações foram agendadas para envio em segundo plano.',
            'total_enfileirado': total_enfileirado
        })
    except Exception as e:
        logger.error(f"Erro ao AGENDAR cotações em massa: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Erro ao iniciar o processo de envio em massa'}, status=500)

@login_required
@require_POST
def enviar_cotacao_individual_api(request):
    """
    API para envio SÍNCRONO de uma cotação individual, usada pelo loop do front-end
    para fornecer feedback em tempo real.
    """
    try:
        data = json.loads(request.body)
        cotacao_id = data.get('id')
        if not cotacao_id:
            return JsonResponse({'success': False, 'error': 'ID da cotação não fornecido.'}, status=400)

        user = request.user
        
        # Garante que o usuário só possa enviar uma cotação da sua empresa e que seja seu responsável.
        cotacao = get_object_or_404(Cotacao, pk=cotacao_id, empresa=user.perfil.empresa, responsavel=user)
        
        # --- LÓGICA DE ENVIO ALTERADA ---
        # Em vez de enfileirar com .delay(), chamamos a função síncrona.
        # Ela executa todo o processo (gerar PDF, enviar e-mail/whats) e espera a conclusão.
        resultado_sincrono = enviar_proposta_sincrono(cotacao.id, user.id)

        # Prepara a resposta JSON para o JavaScript com base no resultado detalhado
        resposta_json = {
            'id': cotacao.proposta_id_url,
            'contato': cotacao.contato,
            'success': resultado_sincrono.get('sucesso_geral', False),
            'enviado_email': resultado_sincrono.get('enviado_email', False),
            'enviado_whatsapp': resultado_sincrono.get('enviado_whatsapp', False),
            'status_final': resultado_sincrono.get('status_final', 'Erro'),
            'erros': resultado_sincrono.get('erros', [])
        }

        # Se não houve sucesso geral, retorna uma resposta de erro HTTP
        if not resposta_json['success']:
            # Concatena os erros em uma única string para o campo 'error'
            resposta_json['error'] = '; '.join(resposta_json['erros']) if resposta_json['erros'] else 'ERRO: Verifique os dados da cotação.'
            return JsonResponse(resposta_json, status=400)

        return JsonResponse(resposta_json)

    except Cotacao.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Cotação não encontrada ou você não tem permissão.'}, status=404)
    except Exception as e:
        logger.error(f"Erro crítico na API de envio individual síncrono: {str(e)}", exc_info=True)
        if 'Instance not found' in str(e) or '404 Client Error' in str(e):
            erro_amigavel = 'Falha no envio: A conexão com o WhatsApp (Instância) não caiu ou foi encontrada. Verifique suas credenciais da API.'
            return JsonResponse({'success': False, 'error': erro_amigavel}, status=400)
               
@login_required
def duplicar_cotacao(request, proposta_id):
    """
    Cria uma duplicata de uma cotação existente, resetando os campos
    relevantes e redirecionando para a tela de edição da nova cotação.
    """
    try:
        # Busca a cotação original que será duplicada
        cotacao_original = get_cotacao_by_proposta_id(request, proposta_id)
        log_action(logger, 'info', request.user, f"Iniciou a duplicação da cotação.", cotacao_original)     

        # --- CORREÇÃO AQUI ---
        # 1. Guarda o ID original em uma variável ANTES de qualquer modificação.
        id_original_str = cotacao_original.proposta_id_url

        # Cria uma cópia em memória da cotação
        nova_cotacao = cotacao_original

        # Anula a chave primária. Isso sinaliza ao Django para criar um NOVO registro no banco
        nova_cotacao.pk = None
        nova_cotacao.id = None

        # Atualiza/Reseta campos para a nova cotação
        nova_cotacao.data_recebimento = timezone.now()
        nova_cotacao.responsavel = request.user
        nova_cotacao.status_cotacao = 'Em Negociação'
        nova_cotacao.status_envio = 'Não Enviado'
        nova_cotacao.proposta_gerada = None  # Limpa o link para o PDF antigo
        nova_cotacao.numero_sequencial_empresa = None  # O modelo irá gerar um novo ao salvar
        nova_cotacao.email_message_id = None

        # Salva a nova cotação. O método .save() do modelo cuidará de gerar o novo número sequencial
        nova_cotacao.save()

        # 2. Usa o ID original que foi guardado e o novo ID da cotação duplicada.
        messages.success(request, f"Cotação #{id_original_str} duplicada. Você está na nova cotação #{nova_cotacao.proposta_id_url}!")
        
        # Redireciona o usuário para a página de edição da cotação recém-criada
        return redirect('quoteflow:cotacao_edit', proposta_id=nova_cotacao.proposta_id_url)

    except Http404:
        messages.error(request, "A cotação que você tentou duplicar não foi encontrada.")
        return redirect('quoteflow:cotacao_list')
    except Exception as e:
        logger.error(f"Erro ao duplicar cotação {proposta_id}: {e}", exc_info=True)
        messages.error(request, f"Ocorreu um erro inesperado ao duplicar a cotação: {e}")
        # Redireciona de volta para a cotação original em caso de erro
        return redirect('quoteflow:cotacao_edit', proposta_id=proposta_id)
    
@login_required
def sugerir_preco_view(request, proposta_id):
    try:
        cotacao = get_cotacao_by_proposta_id(request, proposta_id)
        empresa = request.user.perfil.empresa
        log_action(logger, 'info', request.user, "Solicitou sugestão de preço da IA.", cotacao)
    except Http404:
        return JsonResponse({'erro': 'Cotação não encontrada ou permissão negada.'}, status=404)
    except AttributeError:
         return JsonResponse({'erro': 'Usuário ou empresa não configurado corretamente.'}, status=400)

    if not empresa or not empresa.usa_ia_precificacao:
        return JsonResponse({'erro': 'Recurso de precificação por IA não está ativo para sua empresa.'}, status=403)

    api_url = 'http://147.79.81.52:8010/prever' 
    
    dados_para_api = {
        "origem": cotacao.origem,
        "destino": cotacao.destino,
        "peso": float(cotacao.peso or 0),
        "volumes": int(cotacao.volumes or 0),
        "valor_mercadoria": float(cotacao.valor_mercadoria or 0),
        "tipo_frete": cotacao.tipo_frete,
        "observacao": cotacao.observacao
    }

    # --- BLOCO TRY...EXCEPT MELHORADO PARA DEPURAR ---
    try:
        response = requests.post(api_url, json=dados_para_api, timeout=20)
        response.raise_for_status()
        api_data = response.json()
        
        if 'valor_sugerido' in api_data:
            return JsonResponse({'valor_sugerido': api_data['valor_sugerido']})
        else:
            erro_api = api_data.get('erro', 'A API retornou uma resposta inesperada.')
            return JsonResponse({'erro': erro_api}, status=500)

    except requests.exceptions.RequestException as e:
        # Se for um erro HTTP (como 422), a API respondeu, mas com um erro.
        if e.response is not None:
            print("\n--- ERRO DETALHADO DA API DE IA ---")
            print(f"Status Code: {e.response.status_code}")
            try:
                # O corpo do erro 422 do FastAPI é um JSON com detalhes
                print(f"Corpo da Resposta: {e.response.json()}")
            except ValueError:
                print(f"Corpo da Resposta (não-JSON): {e.response.text}")
            print("----------------------------------\n")
            
            # Mensagem para o usuário final
            return JsonResponse({'erro': 'Os dados da cotação são inválidos para a precificação. Verifique os logs do servidor Django para mais detalhes.'}, status=400)
        
        # Se for um erro de conexão, a API não respondeu.
        else:
            print(f"Erro de CONEXÃO ao chamar a API de IA: {e}")
            return JsonResponse({'erro': 'Não foi possível conectar ao serviço de precificação. Tente novamente mais tarde.'}, status=503)

def get_cotacao_queryset(request):
    """Função auxiliar para obter o queryset base filtrado por empresa E VISIBILIDADE."""
    try:
        if hasattr(request.user, 'perfil') and request.user.perfil and request.user.perfil.empresa:
            empresa_usuario = request.user.perfil.empresa
        else:
            empresa_usuario = None
    except Exception:
        empresa_usuario = None
    
    base_queryset = Cotacao.objects.none()
    if request.user.is_superuser:
        base_queryset = Cotacao.objects.all()
    elif empresa_usuario:
        base_queryset = Cotacao.objects.filter(empresa=empresa_usuario)

    # ===== MODIFICAÇÃO PRINCIPAL AQUI =====
    # Adicionamos o filtro para retornar apenas cotações visíveis.
    # Superusuários podem ver tudo, se desejado, removendo a condição do if.
    if not request.user.is_superuser:
        return base_queryset.filter(visivel=True)
    
    return base_queryset
def planos_view(request):
    # Você pode adicionar lógica aqui para buscar os planos do banco de dados no futuro
    context = {}
    return render(request, 'cotacoes/planos.html', context)

@login_required
@permission_required('perfil.pode_ver_dashboard', raise_exception=True)
def dashboard_view(request):
    """
    View para processar e exibir os dados do dashboard com gráficos.
    AGORA COM LÓGICA DE PERMISSÃO POR GRUPO.
    """
    empresa_usuario = request.user.perfil.empresa
    
    user_is_admin_empresa = request.user.groups.filter(name='adminempresa').exists()

    if user_is_admin_empresa:
        # Admin vê todas as cotações da empresa
        queryset = Cotacao.objects.filter(empresa=empresa_usuario)
    else:
        # Usuário 'comercial' vê apenas as suas próprias cotações
        queryset = Cotacao.objects.filter(empresa=empresa_usuario, responsavel=request.user)

    # Lógica do período dinâmico (continua igual)
    dias_para_visualizar = 180
    titulo_periodo = "Últimos 6 Meses"
    if empresa_usuario and empresa_usuario.dias_expiracao_visualizacao and empresa_usuario.dias_expiracao_visualizacao > 0:
        dias_para_visualizar = empresa_usuario.dias_expiracao_visualizacao
        titulo_periodo = f"Últimos {dias_para_visualizar} Dias"
    data_limite = timezone.now() - timedelta(days=dias_para_visualizar)

    # ==========================================================================
    # KPIs Principais (Widgets)
    # ==========================================================================
    total_cotacoes = queryset.count()
    queryset_aprovadas = queryset.filter(status_cotacao='Aprovada')
    total_aprovadas = queryset_aprovadas.count()
    total_em_negociacao = queryset.filter(status_cotacao='Em Negociação').count()
    total_finalizadas = queryset.filter(status_cotacao='Finalizada').count()

    soma_aprovado = queryset_aprovadas.aggregate(total=Sum('valor_proposta'))['total'] or 0
    valor_total_aprovado = soma_aprovado
    taxa_conversao = (total_aprovadas / total_cotacoes * 100) if total_cotacoes > 0 else 0
    valor_medio_aprovado = valor_total_aprovado / total_aprovadas if total_aprovadas > 0 else 0

    # ==========================================================================
    # Dados para Gráficos
    # ==========================================================================
    status_counts = queryset.values('status_cotacao').annotate(count=Count('id')).order_by('-count')
    rastreio_counts = queryset.exclude(rastreio__isnull=True).exclude(rastreio='')\
        .values('rastreio').annotate(count=Count('id')).order_by('-count')[:10]
        
    recebidas_por_mes = queryset.filter(data_recebimento__gte=data_limite)\
        .annotate(month=TruncMonth('data_recebimento'))\
        .values('month').annotate(count=Count('id')).order_by('month')
        
    aprovadas_por_mes = queryset_aprovadas.filter(data_finalizacao__gte=data_limite)\
        .annotate(month=TruncMonth('data_finalizacao'))\
        .values('month').annotate(count=Count('id')).order_by('month')

    finalizadas_por_mes = queryset.filter(status_cotacao='Finalizada', data_finalizacao__gte=data_limite)\
        .annotate(month=TruncMonth('data_finalizacao'))\
        .values('month').annotate(count=Count('id')).order_by('month')
        
    valor_aprovado_por_mes = queryset_aprovadas.filter(data_finalizacao__gte=data_limite)\
        .annotate(month=TruncMonth('data_finalizacao'))\
        .values('month').annotate(total_valor=Sum('valor_proposta')).order_by('month')
        
    top_origens = queryset.exclude(origem__isnull=True).exclude(origem='')\
        .values('origem').annotate(count=Count('id')).order_by('-count')[:10]
        
    top_destinos = queryset.exclude(destino__isnull=True).exclude(destino='')\
        .values('destino').annotate(count=Count('id')).order_by('-count')[:10]

    responsaveis_counts = None
    responsaveis_valor = None
    if user_is_admin_empresa:
        queryset_empresa_completa = Cotacao.objects.filter(empresa=empresa_usuario)
        responsaveis_counts = queryset_empresa_completa.filter(responsavel__username__isnull=False)\
            .values('responsavel__username').annotate(count=Count('id'))\
            .order_by('-count')[:10]
        responsaveis_valor = queryset_empresa_completa.filter(status_cotacao='Aprovada', responsavel__username__isnull=False)\
            .values('responsavel__username').annotate(total_valor=Sum('valor_proposta'))\
            .order_by('-total_valor')[:10]

    context = {
        'total_cotacoes': total_cotacoes,
        'total_aprovadas': total_aprovadas,
        'total_em_negociacao': total_em_negociacao,
        'total_finalizadas': total_finalizadas,
        'valor_total_aprovado': valor_total_aprovado,
        'taxa_conversao': taxa_conversao,
        'valor_medio_aprovado': valor_medio_aprovado,
        'titulo_periodo_grafico': titulo_periodo,
        
        'status_counts': list(status_counts),
        'rastreio_counts': list(rastreio_counts),
        'recebidas_por_mes': list(recebidas_por_mes),
        'aprovadas_por_mes': list(aprovadas_por_mes),
        'finalizadas_por_mes': list(finalizadas_por_mes),
        'valor_aprovado_por_mes': list(valor_aprovado_por_mes),
        'top_origens': list(top_origens),
        'top_destinos': list(top_destinos),
        'responsaveis_counts': list(responsaveis_counts) if responsaveis_counts else None,
        'responsaveis_valor': list(responsaveis_valor) if responsaveis_valor else None,
    }
    
    return render(request, 'dashboard/dashboard.html', context)

def switch_to_preciflow(request):
    """Muda para a versão 2.0 (Nova)."""
    response = HttpResponseRedirect(reverse('quoteflow:cotacao_list'))
    # Define o cookie como 'true' para Nginx usar a 'app_preciflow'
    response.set_cookie('use_preciflow', 'true', max_age=2592000, path='/')
    messages.info(request, 'Você está na Versão 2.0!')
    return response

def switch_to_mudancasja(request):
    """Muda para a versão 1.0 (Clássica)."""
    response = HttpResponseRedirect(reverse('quoteflow:cotacao_list'))
    # Define o cookie como 'false' para Nginx usar a 'app_mudancasja'
    response.set_cookie('use_preciflow', 'false', max_age=2592000, path='/')
    messages.info(request, 'Você voltou para a versão clássica.')
    return response

def switch_to_mudancasja(request):
    """Muda para a versão 1.0 (Clássica)."""
    # Prepara para redirecionar o usuário
    response = HttpResponseRedirect(reverse('quoteflow:cotacao_list'))
    
    # A LINHA MAIS IMPORTANTE: Define o cookie como 'false'.
    # O Nginx vai ler esse valor e direcionar para a v1.0.
    response.set_cookie('use_preciflow', 'false', max_age=2592000, path='/') # max_age para 30 dias
    
    messages.info(request, 'Você voltou para a versão clássica.')
    return response




@login_required
def updates_list_view(request):
    """
    Exibe a lista de posts de atualizações recentes.
    """
    updates = UpdatePost.objects.filter(is_published=True).order_by('-publication_date')
    context = {
        'updates': updates
    }
    return render(request, 'cotacoes/updates_list.html', context)

@login_required
@permission_required('quoteflow.pode_gerenciar_updates', raise_exception=True)
def update_post_create(request):
    if request.method == 'POST':
        form = UpdatePostForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Nova atualização criada com sucesso!')
            return redirect('quoteflow:updates_list')
    else:
        form = UpdatePostForm()
    
    context = {
        'form': form,
        'titulo_pagina': 'Criar Nova Atualização'
    }
    return render(request, 'cotacoes/update_form.html', context)

@login_required
@permission_required('quoteflow.pode_gerenciar_updates', raise_exception=True)
def update_post_edit(request, pk):
    post = get_object_or_404(UpdatePost, pk=pk)
    if request.method == 'POST':
        form = UpdatePostForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, 'Atualização salva com sucesso!')
            return redirect('quoteflow:updates_list')
    else:
        form = UpdatePostForm(instance=post)
    
    context = {
        'form': form,
        'titulo_pagina': 'Editar Atualização'
    }
    return render(request, 'cotacoes/update_form.html', context)

@login_required
@permission_required('quoteflow.pode_gerenciar_updates', raise_exception=True)
def update_post_delete(request, pk):
    post = get_object_or_404(UpdatePost, pk=pk)
    if request.method == 'POST':
        post.delete()
        messages.success(request, 'Atualização excluída com sucesso!')
        return redirect('quoteflow:updates_list')
    
    return render(request, 'cotacoes/update_confirm_delete.html', {'post': post})


@login_required
def faq_list(request):
    """
    View para listar as perguntas do FAQ, agrupadas por categoria.
    """
    faqs_por_categoria = {}
    # Use o model FAQ diretamente para pegar as choices
    categorias = FAQ._meta.get_field('categoria').choices
    
    for categoria_id, nome_categoria in categorias:
        faqs = FAQ.objects.filter(categoria=categoria_id, ativo=True).order_by('ordem')
        if faqs.exists():
            faqs_por_categoria[nome_categoria] = faqs
            
    context = {
        'faqs_por_categoria': faqs_por_categoria,
    }
    return render(request, 'cotacoes/faq.html', context)

# Views baseadas em classe para o CRUD do FAQ
class FAQCreateView(PermissionRequiredMixin, CreateView):
    model = FAQ
    form_class = FAQForm
    template_name = 'cotacoes/faq_form.html'
    success_url = reverse_lazy('quoteflow:faq_list')
    permission_required = 'quoteflow.add_faq' # Garante que só usuários com permissão possam criar

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Adicionar Pergunta ao FAQ'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Pergunta adicionada com sucesso!')
        return super().form_valid(form)

class FAQUpdateView(PermissionRequiredMixin, UpdateView):
    model = FAQ
    form_class = FAQForm
    template_name = 'cotacoes/faq_form.html'
    success_url = reverse_lazy('quoteflow:faq_list')
    permission_required = 'quoteflow.change_faq'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Editar Pergunta do FAQ'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Pergunta atualizada com sucesso!')
        return super().form_valid(form)

class FAQDeleteView(PermissionRequiredMixin, DeleteView):
    model = FAQ
    template_name = 'cotacoes/faq_confirm_delete.html'
    success_url = reverse_lazy('quoteflow:faq_list')
    permission_required = 'quoteflow.delete_faq'

    def form_valid(self, form):
        messages.success(self.request, 'Pergunta excluída com sucesso!')
        return super().form_valid(form)


@login_required
@require_POST
def mark_update_as_read(request):
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        
        # Busca o status específico para o usuário e o post
        status = UserUpdateStatus.objects.get(user=request.user, post_id=post_id, has_read=False)
        
        # Atualiza o status
        status.has_read = True
        status.read_at = timezone.now()
        status.save()
        
        # Retorna o novo número de notificações não lidas
        new_count = UserUpdateStatus.objects.filter(user=request.user, has_read=False).count()
        
        return JsonResponse({'success': True, 'unread_count': new_count})
    except UserUpdateStatus.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notificação já lida ou não encontrada.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def webhook_asaas_view(request):
    """Recebe e processa notificações de pagamento da Asaas."""
    asaas_token = request.headers.get("Asaas-Webhook-Token")
    if not asaas_token or asaas_token != settings.ASAAS_WEBHOOK_TOKEN:
        logger.warning("Webhook Asaas recebido com token inválido ou ausente.")
        return HttpResponse(status=401)

    try:
        payload = json.loads(request.body)
        event = payload.get("event")
        payment_data = payload.get("payment")

        if event == "PAYMENT_RECEIVED":
            cobranca_id = payment_data.get("id")
            if not cobranca_id: return HttpResponse(status=200)

            try:
                empresa = Empresa.objects.get(asaas_ultima_cobranca_id=cobranca_id)
                empresa.status_assinatura = 'ATIVA'
                empresa.data_vencimento = timezone.now().date() + timedelta(days=30)
                empresa.save(update_fields=['status_assinatura', 'data_vencimento'])
                logger.info(f"Webhook Asaas: Pagamento da empresa '{empresa.nome}' (ID: {empresa.id}) confirmado.")
            except Empresa.DoesNotExist:
                logger.warning(f"Webhook Asaas: Cobrança Paga {cobranca_id} recebida, mas nenhuma empresa encontrada.")

        elif event == "PAYMENT_OVERDUE":
            cobranca_id = payment_data.get("id")
            if not cobranca_id: return HttpResponse(status=200)

            try:
                empresa = Empresa.objects.get(asaas_ultima_cobranca_id=cobranca_id)
                if empresa.status_assinatura == 'PENDENTE':
                    empresa.status_assinatura = 'VENCIDA'
                    empresa.save(update_fields=['status_assinatura'])
                    logger.warning(f"Webhook Asaas: Cobrança da empresa '{empresa.nome}' está VENCIDA.")
            except Empresa.DoesNotExist:
                pass

    except Exception as e:
        logger.error(f"Erro ao processar webhook da Asaas: {str(e)}", exc_info=True)

    return HttpResponse(status=200)

@login_required
def pagina_pagamento_view(request):
    """Página exibida para usuários com pagamento pendente, vencido ou cancelado."""
    empresa = request.user.perfil.empresa
    dados_cobranca = None
    
    if empresa.status_assinatura in ['PENDENTE', 'VENCIDA'] and empresa.asaas_ultima_cobranca_id:
        try:
            url = f"{settings.ASAAS_API_URL}/payments/{empresa.asaas_ultima_cobranca_id}/pixQrCode"
            response = requests.get(url, headers=_get_headers())
            if response.status_code == 200:
                dados_cobranca = response.json()
        except Exception as e:
            logger.error(f"Erro ao buscar QR Code para empresa {empresa.id}: {e}")

    context = {'empresa': empresa, 'dados_cobranca': dados_cobranca}
    return render(request, 'pagamentos/pagamento_pendente.html', context)


from django.http import HttpResponse
import sys
import perfil

def debug_view(request):
    # Pega o caminho exato do arquivo 'admin.py' que o Django está usando
    try:
        from perfil import admin as perfil_admin
        caminho_admin = perfil_admin.__file__
    except Exception as e:
        caminho_admin = f"Erro ao importar admin: {e}"

    # Monta uma resposta de texto puro com as informações
    response_text = "--- DIAGNÓSTICO DO AMBIENTE DJANGO ---\n\n"
    response_text += f"Caminho do arquivo 'perfil/admin.py' carregado:\n{caminho_admin}\n\n"
    response_text += "--- Python Path (sys.path) ---\n"
    response_text += "\n".join(sys.path)
    
    return HttpResponse(response_text, content_type="text/plain")


@csrf_exempt
@require_POST
def webhook_whatsapp_view(request):
    """
    Recebe o payload de mensagem do Node.js (api.js) e loga o evento.
    Aqui é onde você implementará a lógica de atendimento/salvamento.
    """
    try:
        # 1. Carregar o payload JSON
        payload = json.loads(request.body)
        
        # 2. Extrair dados cruciais para o log
        instance_name = payload.get('instance', 'N/A')
        sender_jid = payload.get('from', 'N/A')
        message_text = payload.get('message', 'N/A')
        
        # 3. Logar o recebimento com informações detalhadas
        logger.info(
            f"[WEBHOOK WHATSAPP] Instância: {instance_name} | Recebido de: {sender_jid} | Conteúdo: {message_text[:100]}..."
        )
        
        # 4. Implementação Futura: 
        # Aqui, você buscará o usuário/cliente pela 'instance_name' (ou JID do remetente)
        # e criará o registro da mensagem no seu banco de dados.
        # Exemplo: SalvarMensagemDB(instance_name, sender_jid, message_text)

        # 5. Resposta de Sucesso
        # É crucial responder com HTTP 200/JsonResponse para que a API Node não tente reenviar.
        return JsonResponse({'status': 'received', 'message': 'Payload processado com sucesso.'}, status=200)

    except json.JSONDecodeError:
        logger.error("WEBHOOK WHATSAPP: Erro ao decodificar JSON. Corpo inválido.")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Erro ao processar webhook do WhatsApp: {str(e)}", exc_info=True)
        # Resposta 500 para indicar que o Django falhou internamente
        return HttpResponse(status=500)
    
def cadastro_view(request):
    """
    Página de cadastro/geração de leads.
    Envia um e-mail para o administrador e oferece link de WhatsApp.
    """
    # Formata o número de WhatsApp para o link
    whatsapp_number = "5511993485718" # Seu número
    whatsapp_message = quote("Olá! Vi o site do Preciflow e tenho interesse em me cadastrar.")
    whatsapp_url = f"https://wa.me/{whatsapp_number}?text={whatsapp_message}"

    if request.method == 'POST':
        form = CadastroForm(request.POST) # Inicia o form com os dados do POST
        if form.is_valid():
            try:
                # Coleta os dados limpos
                nome = form.cleaned_data['nome_completo']
                email = form.cleaned_data['email']
                telefone = form.cleaned_data['telefone_whatsapp']
                empresa = form.cleaned_data.get('nome_empresa', 'Não informada')
                plano = dict(form.PLANO_CHOICES).get(form.cleaned_data['plano_interesse'])

                # Monta o corpo do e-mail
                subject = f"Novo Lead (Cadastro Preciflow): {nome} - {empresa}"
                message_body = f"""
                Um novo cliente demonstrou interesse na plataforma Preciflow!

                DADOS DO LEAD:
                -------------------------------------
                Nome: {nome}
                Email: {email}
                WhatsApp: {telefone}
                Empresa: {empresa}
                Plano de Interesse: {plano}
                -------------------------------------

                Entre em contato o mais rápido possível.
                O e-mail deste lead (para resposta) é: {email}
                """
                
                # Cria a conexão SMTP
                connection = mail.get_connection(
                    backend=settings.EMAIL_BACKEND,
                    host=settings.EMAIL_HOST,
                    port=settings.EMAIL_PORT,
                    username=settings.EMAIL_HOST_USER,
                    password=settings.EMAIL_HOST_PASSWORD,
                    use_tls=settings.EMAIL_USE_TLS
                )

                # Mude o destinatário para um e-mail diferente do remetente
                destinatario_do_lead = 'alexandre97-@hotmail.com' # <--- MUDE PARA SEU EMAIL PESSOAL
                
                msg = mail.EmailMultiAlternatives(
                    subject=subject,
                    body=message_body,
                    from_email=settings.DEFAULT_FROM_EMAIL, # De: 'suporte@portaldotransporte.com.br'
                    to=[destinatario_do_lead],              # Para: O seu e-mail pessoal
                    reply_to=[email],                       # 'Responder a:' (o e-mail do cliente)
                    connection=connection
                )
                
                msg.send(fail_silently=False)
                
                messages.success(request, 'Obrigado pelo seu interesse! Entraremos em contato em breve.')
                
                # --- CORREÇÃO AQUI ---
                # 1. Limpa o formulário após o sucesso
                form = CadastroForm()
                # 2. Remove o redirecionamento (deixando o fluxo cair para o render)
                # return redirect('quoteflow:apresentacao') # <--- LINHA REMOVIDA

            except Exception as e:
                logger.error(f"Falha ao enviar e-mail de lead de cadastro: {e}", exc_info=True)
                messages.error(request, 'Ocorreu um erro ao enviar sua solicitação. Por favor, tente novamente ou nos chame no WhatsApp.')
                # Deixa o fluxo cair para o render, mantendo os dados do formulário
        
        else:
            messages.error(request, 'Formulário inválido. Por favor, verifique os campos em vermelho.')
            # Deixa o fluxo cair para o render, mantendo os dados e os erros do formulário
    
    else: # Método GET
        form = CadastroForm()

    context = {
        'form': form,
        'whatsapp_url': whatsapp_url
    }
    # Todos os caminhos (GET, POST-Sucesso, POST-Falha) agora terminam aqui
    return render(request, 'cotacoes/cadastro.html', context)