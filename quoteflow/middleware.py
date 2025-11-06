# quoteflow/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.models import AnonymousUser
import logging

# Adiciona a capacidade de registrar logs neste arquivo
logger = logging.getLogger(__name__)

class VersionSwitchMiddleware:
    # ... (sua outra classe de middleware continua aqui sem alterações)
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        try:
            login_url = reverse('perfil:login')
            if request.user.is_authenticated and request.path == login_url:
                if isinstance(response, HttpResponseRedirect):
                    response.set_cookie('use_preciflow', 'true', max_age=2592000, path='/')
        except Exception:
            pass
        return response


class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from perfil.models import Empresa
        
        if not request.user or isinstance(request.user, AnonymousUser) or request.user.is_superuser:
            return self.get_response(request)

        allowed_urls = [
            reverse('perfil:logout'),
            reverse('quoteflow:pagina_pagamento'),
            reverse('quoteflow:webhook_asaas'),
            reverse('quoteflow:debug_path'),
        ]
        
        if request.path_info in allowed_urls:
            return self.get_response(request)

        try:
            empresa = request.user.perfil.empresa
            
            # --- LINHA DE DIAGNÓSTICO ---
            # Vamos logar exatamente o que o middleware está vendo
            logger.info(f"[SubscriptionMiddleware] Verificando usuário '{request.user.username}', Empresa '{empresa.nome}', Status '{empresa.status_assinatura}'")
            
            # A lógica de bloqueio
            if empresa.status_assinatura not in ['ATIVA', 'TESTE']:
                
                # --- LINHA DE DIAGNÓSTICO ---
                logger.warning(f"[SubscriptionMiddleware] BLOQUEANDO usuário '{request.user.username}'. Status é '{empresa.status_assinatura}'. Redirecionando...")
                return redirect('quoteflow:pagina_pagamento')
                
        except (AttributeError, Empresa.DoesNotExist) as e:
            # --- CORREÇÃO: SUBSTITUÍMOS 'pass' POR UM LOG DE AVISO ---
            # Se o usuário não tiver perfil/empresa, permite o acesso, MAS LOGA O AVISO
            logger.warning(f"[SubscriptionMiddleware] Usuário '{request.user.username}' acessou sem perfil/empresa. Deixando passar. Erro: {e}")

        return self.get_response(request)