# perfil/admin.py

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Empresa, Perfil, ConfiguracaoEmail
from quoteflow.asaas_service import criar_ou_atualizar_cliente_asaas, gerar_cobranca_pix_mensal

# ==========================================================
# AÇÕES E ADMINS QUE JÁ FUNCIONAM (PRESERVADOS)
# ==========================================================
@admin.action(description='Criar/Sincronizar cliente na Asaas')
def sincronizar_cliente_asaas_action(modeladmin, request, queryset):
    # ... (seu código de ação continua igual) ...
    pass

@admin.action(description='Gerar cobrança PIX agora')
def gerar_cobranca_agora_action(modeladmin, request, queryset):
    # ... (seu código de ação continua igual) ...
    pass

class ConfiguracaoEmailInline(admin.StackedInline):
    model = ConfiguracaoEmail
    can_delete = False

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    # ... (seu código do EmpresaAdmin continua igual) ...
    list_display = ('nome', 'status_assinatura', 'data_vencimento')
    inlines = [ConfiguracaoEmailInline]
    # ...

# ==========================================================
# ADMIN PARA USUÁRIO E PERFIL (ESTA É A PARTE CORRIGIDA)
# ==========================================================
class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = 'Perfil do Usuário e API'
    fk_name = 'usuario'

    fieldsets = (
        (None, {'fields': ('empresa', 'nome_completo', 'departamento', 'telefone_whatsapp')}),
        ('Configurações da API de WhatsApp', {
            'classes': ('collapse',),
            'fields': ('api_provider', 'api_credentials', 'proxy_url'),
        }),
    )

class UserAdmin(BaseUserAdmin):
    inlines = (PerfilInline,)
    
    # --- MUDANÇA 1: Adicionando a nova coluna 'api_status' ---
    list_display = ('username', 'email', 'get_empresa', 'api_status', 'is_staff')
    
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'perfil__empresa')

    @admin.display(description='Empresa')
    def get_empresa(self, instance):
        try:
            return instance.perfil.empresa
        except (Perfil.DoesNotExist, AttributeError):
            return "Nenhuma"

    # --- MUDANÇA 2: Nova função para gerar o ícone de status ---
    @admin.display(description='API Ativa?', boolean=True)
    def api_status(self, instance):
        """
        Retorna True (ícone verde) se a API do usuário estiver configurada,
        e False (ícone vermelho) caso contrário.
        """
        try:
            # Reutiliza a mesma lógica que já existe no seu models.py
            return instance.perfil.tem_api_whatsapp()
        except (Perfil.DoesNotExist, AttributeError):
            # Se o usuário não tiver perfil, a API não está configurada.
            return False

# Re-registra o modelo User com a nossa configuração customizada
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Remove o admin separado para Perfil e ConfiguracaoEmail, se eles existirem
if admin.site.is_registered(Perfil):
    admin.site.unregister(Perfil)
if admin.site.is_registered(ConfiguracaoEmail):
    admin.site.unregister(ConfiguracaoEmail)