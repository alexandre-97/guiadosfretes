from django.contrib import admin
# Adicionei MensagemPersonalizada, FAQ e TemplateProposta na importação
from .models import Cotacao, EmailEnviado, UpdatePost, MensagemPersonalizada, FAQ, TemplateProposta
from .forms import CotacaoForm

@admin.register(Cotacao)
class CotacaoAdmin(admin.ModelAdmin):
    form = CotacaoForm
    
    # --- Colunas na lista principal ---
    list_display = (
        'proposta_id_url', 
        'empresa', 
        'origem', 
        'destino', 
        'status_cotacao',
        'status_envio', 
        'responsavel',
        'data_ultima_modificacao',
        'data_finalizacao',
    )
    
    # --- Filtros na barra lateral ---
    list_filter = (
        'status_cotacao',
        'status_envio',
        'empresa',
        'responsavel',
        'data_ultima_modificacao',
        'data_finalizacao',
    )
    
    # --- Campos de busca ---
    search_fields = (
        'proposta_id_url', 
        'origem', 
        'destino', 
        'contato', 
        'responsavel__username'
    )

    # --- Campos somente leitura ---
    readonly_fields = (
        'proposta_id_url',
        'data_recebimento',
        'data_finalizacao',
        'data_ultima_modificacao',
    )

    # --- Organização da página de edição ---
    fieldsets = (
        ('Informações da Cotação (Preciflow 2.0)', {
            'description': 'Gerenciamento de cotações da nova versão do sistema.',
            'fields': (
                ('proposta_id_url', 'empresa'), 
                ('contato', 'telefone', 'email'), 
                ('origem', 'destino')
            )
        }),
        ('Detalhes do Frete', {
            'fields': (
                'tipo_frete', 
                ('prazo_coleta', 'prazo_entrega'), 
                'observacao'
            )
        }),
        ('Valores e Medidas', {
            'fields': (
                ('volumes', 'cubagem', 'peso'), 
                ('valor_mercadoria', 'valor_proposta')
            )
        }),
        ('Status e Controle Interno', {
            'fields': (
                'status_cotacao', 
                'status_envio', 
                'rastreio', 
                'responsavel'
            )
        }),
        ('Datas de Rastreamento', {
            'classes': ('collapse',), 
            'fields': (
                'data_recebimento', 
                'data_ultima_modificacao',
                'data_finalizacao'
            )
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.user = request.user
        return form
    
    def save_model(self, request, obj, form, change):
        if not obj.empresa_id and hasattr(request.user, 'perfil'):
            obj.empresa = request.user.perfil.empresa
        if not obj.responsavel_id:
            obj.responsavel = request.user
        super().save_model(request, obj, form, change)

@admin.register(EmailEnviado)
class EmailEnviadoAdmin(admin.ModelAdmin):
    list_display = ('cotacao', 'destinatario', 'assunto', 'enviado_por', 'enviado_com_sucesso', 'data_envio')
    list_filter = ('enviado_com_sucesso', 'data_envio')
    search_fields = ('destinatario', 'assunto', 'cotacao__id', 'cotacao__origem', 'cotacao__destino')
    readonly_fields = ('data_envio',)
    list_select_related = ('cotacao', 'cotacao__empresa', 'enviado_por')
    autocomplete_fields = ['cotacao', 'enviado_por']

@admin.register(UpdatePost)
class UpdatePostAdmin(admin.ModelAdmin):
    list_display = ('title', 'publication_date', 'is_published')
    list_filter = ('is_published', 'publication_date')
    search_fields = ('title', 'content')
    list_per_page = 20

# --- NOVOS MODELOS ADICIONADOS ---

@admin.register(MensagemPersonalizada)
class MensagemPersonalizadaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'empresa', 'ativo')
    list_filter = ('empresa', 'ativo')
    search_fields = ('titulo', 'conteudo')

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('pergunta', 'categoria', 'ordem', 'ativo')
    list_filter = ('categoria', 'ativo')
    search_fields = ('pergunta', 'resposta')
    ordering = ('categoria', 'ordem')

@admin.register(TemplateProposta)
class TemplatePropostaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo')
    search_fields = ('nome',)