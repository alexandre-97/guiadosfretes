import requests
import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib import messages
from .forms import PerfilForm
from django.views.generic import View
from django.contrib.auth import authenticate, login, logout
import copy
from django.urls import reverse
from django.http import JsonResponse, HttpResponseRedirect
from .forms import MeusDadosForm, PerfilForm
from quoteflow.utils import WhatsAppInstanceDisconnectedException, WhatsAppNumberInvalidException # Importar exceções
import time
# REMOVIDO: from quoteflow.utils import get_whatsapp_api_status
logger = logging.getLogger(__name__)

class Login(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'perfil/login.html')
        
    def post(self, request, *args, **kwargs):
        # ... (seu código de autenticação) ...
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not username or not password:
            messages.error(request, 'Usuário ou senha inválidos.')
            return redirect('perfil:login')
        usuario = authenticate(request, username=username, password=password)
        if not usuario:
            messages.error(request, 'Usuário ou senha inválidos.')
            return redirect('perfil:login')
        
        login(request, usuario)
        messages.success(request, 'Você fez login no sistema.')
        
        response = HttpResponseRedirect(reverse('quoteflow:cotacao_list'))
        # DEFINE o cookie como 'true' para garantir que o usuário vá para a V2.0 (app_preciflow)
        response.set_cookie('use_preciflow', 'true', max_age=2592000, path='/')
        return response

class Logout(View):
    def get(self, request, *args, **kwargs):
        # ... (seu código de logout, sem alterações) ...
        carrinho = copy.deepcopy(request.session.get('carrinho'))
        logout(request)
        request.session['carrinho'] = carrinho
        request.session.save()
        return redirect('perfil:login')


def _get_api_qrcode(perfil):
    """
    Despachante: Obtém o Base64 do QR Code (SELF_HOSTED) ou tenta obter (MEGA API).
    Remove a lógica de start/logout, que falha no Mega API.
    """
    if perfil.api_provider == 'MEGAAPI':
        credentials = perfil.api_credentials
        instance_key = credentials.get('instance_key')
        token = credentials.get('token')
        if not instance_key or not token:
            raise Exception('Credenciais MegaAPI incompletas.')
            
        # Tenta o endpoint de QR CODE
        api_url = f"https://apistart03.megaapi.com.br/rest/instance/qrcode_base64/{instance_key}"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            response = requests.get(api_url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            qr_code_base64 = data.get('qrcode')
            
            if not qr_code_base64:
                # Se o 200 veio, mas sem QR Code (instância offline, mas URL correta)
                raise Exception('A instância está offline no provedor. Por favor, inicie-a no Painel do Mega API.')
            
            # Se o Base64 for válido, retorna
            if not qr_code_base64.startswith('data:image'):
                 qr_code_base64 = f"data:image/png;base64,{qr_code_base64}"
                 
            return qr_code_base64

        except requests.exceptions.HTTPError as e:
            error_text = e.response.text.lower()
            
            if 'instance already active' in error_text or 'already connected' in error_text:
                raise Exception('A instância já está conectada. Nenhuma ação é necessária.')
            
            # Se falhou com 404/400/403, a instância não está pronta/existe.
            raise Exception(f'Falha ao obter QR Code (Código {e.response.status_code}). Tente iniciar no painel da Mega API.')
        
    elif perfil.api_provider == 'SELF_HOSTED':
        # --- Lógica CORRIGIDA para SELF_HOSTED ---
        data = perfil.get_self_hosted_api_data() # MODIFICADO
        qr_base64 = data.get('qrCodeBase64')
        
        # 🟢 1. Se estiver CONNECTED, levanta uma exceção INFORMATIVA
        if data.get('status') == 'CONNECTED':
            # Usamos o prefixo 'CONECTADO:' para que a view trate como sucesso.
            raise Exception('CONECTADO: A instância do WhatsApp já está conectada e pronta para uso.')
            
        # 🟢 2. Se não houver QR code nem conexão (falha de inicialização)
        if not qr_base64:
            # Usamos o prefixo 'FALHA_API:' para diferenciar de outros erros
            raise Exception('FALHA_API: A API não forneceu um QR Code. Tente reiniciar a instância no PM2.')
            
        # 🚨 CORREÇÃO CRÍTICA: Garantir o prefixo Base64 para o navegador
        if not qr_base64.startswith('data:image'):
             qr_base64 = f"data:image/png;base64,{qr_base64}"

        return qr_base64
        
    else:
        raise Exception('Provedor de API não configurado ou inválido.')
    
# View da página "Meus Dados"
@login_required
def meus_dados_view(request):
    perfil = request.user.perfil

    if request.method == 'POST':
        form = MeusDadosForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, 'Seus dados foram atualizados com sucesso!')
            return redirect('perfil:meus_dados')
        else:
            messages.error(request, 'Não foi possível salvar. Verifique os erros abaixo.')
    
    else:
        form = MeusDadosForm(instance=perfil)

    qr_code_base64 = request.session.pop('qr_code_base64', None)
    
    context = {
        'form': form,
        'tem_api_configurada': perfil.tem_api_whatsapp(),
        'qr_code_base64': qr_code_base64,
    }
    return render(request, 'perfil/meus_dados.html', context)

# View para gerar o QR Code (chamada pelo link)
@login_required
@require_GET
def gerar_qrcode_view(request):
    """
    Tenta obter o QR Code da API Node.js e retorna o resultado como JSON.
    """
    perfil = request.user.perfil
    
    # 🚨 INICIALIZAÇÃO CRÍTICA
    response_json = { 
        "success": False, 
        "message": "Falha ao tentar obter o QR Code. Tente reiniciar a instância.",
        "qr_code": None
    } 

    try:
        # Tenta obter o QR Code
        qr_code_base64 = _get_api_qrcode(perfil) 

        # Caso de sucesso: sobrescreve o JSON inicial (QR Code gerado com sucesso)
        response_json = { 
            "success": True, 
            "qr_code": qr_code_base64,
            "message": "QR Code carregado com sucesso. Escaneie imediatamente!"
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter QR Code para {perfil.usuario.username}: {e}")
        
        message_text = str(e)
        
        # 🟢 CORREÇÃO NA VIEW: Trata a exceção de instância já conectada como sucesso
        if message_text.startswith('CONECTADO:'):
            # Exibe a mensagem como sucesso, remove o prefixo e força o status 'success': True
            messages.success(request, message_text.replace('CONECTADO: ', '')) 
            response_json["message"] = message_text.replace('CONECTADO: ', '') 
            response_json["success"] = True # Força sucesso para retornar HTTP 200
        else:
            # Caso de erro real: exibe como erro
            # Remove o prefixo 'FALHA_API:' se estiver presente
            cleaned_message = message_text.replace('FALHA_API: ', '')
            messages.error(request, cleaned_message)
            response_json["message"] = cleaned_message 
            # response_json["success"] permanece False
            
    # Adiciona cabeçalho de cache
    response_json["Cache-Control"] = "no-cache, no-store, must-revalidate" 

    # Status 200 se for sucesso (incluindo o status CONECTADO)
    status_code = 200 if response_json.get("success") else 400
    return JsonResponse(response_json, status=status_code)

@login_required
@require_GET
def verificar_status_whatsapp_api(request):
    """
    Endpoint AJAX para verificar o status de conexão da API de WhatsApp do Perfil.
    """
    perfil = request.user.perfil
    
    try:
        # CORREÇÃO: Agora usa a função completa que verifica TODOS os provedores
        status_data = perfil.get_api_status()
        
        # Retorna o status da API Node.js (online, disconnected, connected)
        return JsonResponse(status_data, status=200)

    except Exception as e:
        # Se houver erro de conexão ou exceção interna.
        logger.error(f"Erro ao verificar status da API para {perfil.usuario.username}: {e}")
        return JsonResponse({
            "status": "error", 
            "message": "Falha ao comunicar com a API. Verifique se a instância está rodando no PM2.",
            "error_detail": str(e)
        }, status=500)

def _restart_megaapi_instance(perfil):
    """
    Tenta encerrar a instância para forçar a geração de um novo QR Code.
    Usamos o endpoint mais comum para encerramento ou restart.
    """
    credentials = perfil.api_credentials
    instance_key = credentials.get('instance_key')
    token = credentials.get('token')
    
    # Tentativa com o endpoint de LOGOUT (o mais provável para forçar um novo QR)
    api_url = f"https://apistart03.megaapi.com.br/rest/instance/logout/{instance_key}" 
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Usa POST para encerramento (pode ser GET em algumas APIs, mas POST é mais comum)
        response = requests.post(api_url, headers=headers, timeout=10)
        
        # 200, 202 (Accepted), ou 404 (já estava offline), ou 400 (logout proibido)
        if response.status_code in [200, 202]:
             return True # Encerrou com sucesso
             
        # Se for 404 ou 400, o endpoint de logout falhou/não existe.
        if response.status_code in [404, 400]:
             logger.warning(f"Endpoint LOGOUT/START não encontrado. Tentando RESTART.")
             # Tenta a URL de restart simples (que também pode estar com problema)
             api_url_restart = f"https://apistart03.megaapi.com.br/rest/instance/restart/{instance_key}"
             response_restart = requests.post(api_url_restart, headers=headers, timeout=10)
             response_restart.raise_for_status()
             return True
             
        response.raise_for_status()
        return True
        
    except requests.exceptions.HTTPError as e:
        error_text = e.response.text.lower()
        
        if 'instance already active' in error_text or 'already connected' in error_text:
             raise Exception('A instância já está conectada. Nenhuma ação é necessária.')
             
        logger.error(f"Falha CRÍTICA (Logout/Restart): {e.response.status_code} - {e.response.text}")
        raise Exception(f"Erro ao tentar reiniciar/desconectar a API: {e.response.status_code}. Detalhes: {e.response.text}")
    except Exception as e:
        logger.error(f"Erro de conexão ao reiniciar Mega API: {e}")
        raise Exception(f"Erro de conexão crítica ao iniciar a API.")