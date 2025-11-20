from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
app_name = 'quoteflow' 

urlpatterns = [
    path('busca/', views.BuscaCotacoes.as_view(), name="busca"),
    path('cotacoes/buscar/', views.buscar_por_id, name='buscar_por_id'),
    path('cotacoes/', views.cotacao_list, name='cotacao_list'),
    path('cotacoes/nova/', views.cotacao_create, name='cotacao_create'),
    path('carregar-cotacoes/', views.carregar_novas_cotacoes, name='carregar_novas_cotacoes'),
    path('planos/', views.planos_view, name='planos'),
    path('cadastre-se/', views.cadastro_view, name='cadastro'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # URLs do CRUD de FAQ
    path('faq/', views.faq_list, name='faq_list'),
    path('faq/nova/', views.FAQCreateView.as_view(), name='faq_create'),
    path('faq/<int:pk>/editar/', views.FAQUpdateView.as_view(), name='faq_update'),
    path('faq/<int:pk>/deletar/', views.FAQDeleteView.as_view(), name='faq_delete'),

    # Atualizações 
    path('atualizacoes/', views.updates_list_view, name='updates_list'),
    path('atualizacoes/nova/', views.update_post_create, name='update_post_create'),
    path('atualizacoes/<int:pk>/editar/', views.update_post_edit, name='update_post_edit'),
    path('atualizacoes/<int:pk>/deletar/', views.update_post_delete, name='update_post_delete'),
    path('updates/mark-as-read/', views.mark_update_as_read, name='mark_update_as_read'),
    path('apresentacao/', TemplateView.as_view(template_name='cotacoes/apresentacao.html'), name='apresentacao'),

    # URLs padronizadas com proposta_id
    path('cotacoes/<str:proposta_id>/editar/', views.cotacao_edit, name='cotacao_edit'),
    path('cotacao/<str:proposta_id>/solicitar-medidas/', views.solicitar_medidas, name='solicitar_medidas'),
    path('cotacoes/<str:proposta_id>/enviar/', views.enviar_cotacao, name='enviar_cotacao'),
    path('cotacoes/<str:proposta_id>/enviar-whatsapp/', views.enviar_whatsapp_view, name='enviar_whatsapp'),
    path('cotacoes/<str:proposta_id>/enviar-apenas-whatsapp/', views.enviar_apenas_whatsapp, name='enviar_apenas_whatsapp'),
    path('cotacoes/<str:proposta_id>/solicitar-coleta/', views.enviar_solicitacao_coleta, name='enviar_solicitacao_coleta'),
    path('cotacoes/<str:proposta_id>/solicitar-pagamento/', views.solicitar_pagamento, name='solicitar_pagamento'),
    path('cotacao/<str:proposta_id>/enviar-email/', views.enviar_apenas_email, name='enviar_apenas_email'),
    path('cotacao/duplicar/<str:proposta_id>/', views.duplicar_cotacao, name='duplicar_cotacao'),

    # APIs de envio em massa
    path('cotacoes/carregar-cotacoes-envio-massa/', views.carregar_cotacoes_envio_massa, name='carregar_cotacoes_envio_massa'),
    path('cotacoes/enviar-cotacoes-massa/', views.enviar_cotacoes_massa, name='enviar_cotacoes_massa'),
    path('cotacoes/enviar-individual-api/', views.enviar_cotacao_individual_api, name='enviar_cotacao_individual_api'),
    
    path('cotacoes/<str:proposta_id>/sugerir-preco/', views.sugerir_preco_view, name='sugerir_preco'),
    path('ajax/designar-responsavel/', views.designar_responsavel_ajax, name='designar_responsavel_ajax'),
    path('ajax/designar-responsavel-massa/', views.designar_responsavel_massa_ajax, name='designar_responsavel_massa_ajax'),

    path('switch-to-preciflow/', views.switch_to_preciflow, name='switch_to_preciflow'),
    path('switch-to-mudancasja/', views.switch_to_mudancasja, name='switch_to_mudancasja'),

    # --- NOVAS URLS PARA PAGAMENTO ASAAS ---
    path('pagamentos/webhook/asaas/', views.webhook_asaas_view, name='webhook_asaas'),
    path('pagamentos/pendente/', views.pagina_pagamento_view, name='pagina_pagamento'),
    path('debug-path/', views.debug_view, name='debug_path'),

    path('webhook/whatsapp/', views.webhook_whatsapp_view, name='webhook_whatsapp'),
    
    # CRUD de Templates de Mensagem
path('templates-msg/', views.MensagemTemplateListView.as_view(), name='template_msg_list'),
    path('templates-msg/novo/', views.MensagemTemplateCreateView.as_view(), name='template_msg_create'),
    path('templates-msg/<int:pk>/editar/', views.MensagemTemplateUpdateView.as_view(), name='template_msg_edit'),
    path('templates-msg/<int:pk>/excluir/', views.MensagemTemplateDeleteView.as_view(), name='template_msg_delete'),    # AJAX Envio
    path('ajax/enviar-whatsapp-personalizado/', views.enviar_whatsapp_personalizado_ajax, name='enviar_whatsapp_personalizado_ajax'),    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)