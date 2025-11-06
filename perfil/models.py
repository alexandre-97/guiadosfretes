from django.db import models
from django.contrib.auth.models import User
from django_cryptography.fields import encrypt
import requests
import logging

logger = logging.getLogger(__name__)


class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Usuário')
    empresa = models.ForeignKey('Empresa', on_delete=models.CASCADE, related_name='perfis', verbose_name='Empresa', null=True)

    nome_completo = models.CharField(max_length=100, verbose_name="Nome Completo", null=True)
    departamento = models.CharField(max_length=100, verbose_name="Departamento", null=True)
    telefone_whatsapp = models.CharField(max_length=20, verbose_name="WhatsApp", blank=True, null=True)
    
    # --- INÍCIO DA ADAPTAÇÃO ---
    
    API_PROVIDER_CHOICES = [
        ('MEGAAPI', 'Mega API'),
        ('SELF_HOSTED', 'API Própria (Preciflow)'),
    ]
    api_provider = models.CharField(
        max_length=20,
        choices=API_PROVIDER_CHOICES,
        default='MEGAAPI',
        verbose_name="Provedor da API de WhatsApp"
    )

    api_credentials = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name="Credenciais da API",
        help_text='MegaAPI: {"instance_key": "...", "token": "..."} | API Própria: {"instance_name": "...", "port": "..."}'
    )
    
    proxy_url = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="URL do Proxy",
        help_text="Formato: http://usuario:senha@host:porta"
    )
    # --- FIM DA ADAPTAÇÃO ---

    def assinatura_digital(self):
        telefone_empresa = self.empresa.telefone if self.empresa and self.empresa.telefone else '-'
        site = self.empresa.site if self.empresa and self.empresa.site else '-'
        return f"""{self.nome_completo or ''}
{self.departamento or ''}
Email: {self.usuario.email}
Tel: {telefone_empresa} | {self.telefone_whatsapp or '-'}
Site: {site}"""

    def tem_api_whatsapp(self):
        """Verifica se o provedor e as credenciais mínimas estão configurados."""
        if not self.api_provider or not self.api_credentials:
            return False
            
        if self.api_provider == 'MEGAAPI':
            return 'instance_key' in self.api_credentials and 'token' in self.api_credentials
        elif self.api_provider == 'SELF_HOSTED':
            return 'instance_name' in self.api_credentials and 'port' in self.api_credentials
        return False

    # --- INÍCIO DA ADIÇÃO: Lógica de Status Centralizada ---
    # Métodos movidos de views.py para cá para validação centralizada

    def get_self_hosted_api_data(self):
        """Consulta o endpoint /status da API Própria (Preciflow)."""
        credentials = self.api_credentials
        port = credentials.get('port')
        instance_name = credentials.get('instance_name')
        
        if not port or not instance_name:
            raise Exception('Credenciais da API incompletas: porta ou nome da instância faltando.')
            
        api_url = f"http://127.0.0.1:{port}/status"
        
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Falha ao consultar API na porta {port}: {e}")
            return {'status': 'API_ERROR', 'qrCodeBase64': None, 'error_detail': str(e)}

    def get_api_status(self):
        """Despachante: Verifica o status da conexão do WhatsApp (MegaAPI ou Self-Hosted)."""
        
        if self.api_provider == 'MEGAAPI':
            credentials = self.api_credentials
            instance_key = credentials.get('instance_key')
            token = credentials.get('token')
            if not instance_key or not token:
                return {'status': 'NO_CREDENTIALS'}
                
            api_url = f"https://apistart03.megaapi.com.br/rest/instance/{instance_key}"
            headers = {"Authorization": f"Bearer {token}"}

            try:
                response = requests.get(api_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                try:
                    data = response.json()
                except requests.exceptions.JSONDecodeError:
                    logger.warning(f"MegaAPI retornou 200, mas corpo vazio/inválido. Assumindo OFFLINE.")
                    return {'status': 'DISCONNECTED'}
                
                connection_status = data.get('instance', {}).get('status', 'UNKNOWN').upper()
                return {'status': connection_status}
            
            except requests.exceptions.RequestException:
                return {'status': 'API_ERROR'}
                        
        elif self.api_provider == 'SELF_HOSTED':
            try:
                data = self.get_self_hosted_api_data()
            except Exception:
                return {'status': 'API_ERROR'}

            node_status = data.get('status', 'UNKNOWN').upper()
            
            if node_status == 'CONNECTED':
                return {'status': 'CONNECTED'}
            elif node_status == 'PENDING':
                 return {'status': 'PENDING_QR'}
            elif node_status == 'DISCONNECTED':
                 return {'status': 'DISCONNECTED'}
            else:
                 return {'status': 'UNKNOWN'}
               
        return {'status': 'NO_CONFIG'}

    # --- FIM DA ADIÇÃO ---

    class Meta:
        permissions = [
            ("pode_ver_dashboard", "Pode ver o dashboard analítico"),
        ]

    def __str__(self):
        return f'{self.nome_completo or self.usuario.username}'

class Empresa(models.Model):
    # --- SEUS CAMPOS EXISTENTES ---
    nome = models.CharField(max_length=100, unique=True)
    nome_full = models.CharField(max_length=100, unique=False, null=True, blank=True)
    razao_social = models.CharField(max_length=150, null=True, blank=True, verbose_name="Razão Social")
    cpf_cnpj = models.CharField(max_length=18, blank=True, null=True, verbose_name="CPF/CNPJ")
    banco = models.CharField(max_length=100, null=True, blank=True, verbose_name="Banco")
    agencia_conta = models.CharField(max_length=50, null=True, blank=True, verbose_name="Agência/Conta")
    pix = models.CharField(max_length=100, null=True, blank=True, verbose_name="Pix")
    logo = models.ImageField(upload_to='empresa/logo/', blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    site = models.URLField(blank=True, null=True)
    slogan = models.CharField(max_length=255, blank=True, null=True)
    template_proposta = models.FileField(
        upload_to='templates_propostas_empresas/',
        blank=True, null=True, help_text='Template .docx específico para essa empresa.'
    )
    usa_ia_precificacao = models.BooleanField(
        default=False, verbose_name="Usa IA para Precificação?",
        help_text="Marque esta opção para permitir que usuários desta empresa usem a sugestão de preço da IA."
    )
    dias_expiracao_visualizacao = models.IntegerField(
        null=True, blank=True, verbose_name="Tempo para Ocultar Cotações (dias)",
        help_text="Após este período, as cotações não aparecerão nas listas e buscas. Deixe em branco para nunca ocultar."
    )
    dias_expiracao_dados = models.IntegerField(
        null=True, blank=True, verbose_name="Tempo para Apagar Cotações (dias)",
        help_text="CUIDADO: Após este período, os dados da cotação serão permanentemente apagados. Deixe em branco para nunca apagar."
    )

    # ==========================================================
    # CAMPOS DE ASSINATURA (AJUSTADOS PARA ASAAS/PIX)
    # ==========================================================
    STATUS_ASSINATURA_CHOICES = [
        ('TESTE', 'Período de Teste'),
        ('ATIVA', 'Ativa'),
        ('PENDENTE', 'Pagamento Pendente'),
        ('VENCIDA', 'Vencida'),
        ('CANCELADA', 'Cancelada'),
    ]

    status_assinatura = models.CharField(
        max_length=20, choices=STATUS_ASSINATURA_CHOICES, default='TESTE',
        verbose_name="Status da Assinatura"
    )
    data_vencimento = models.DateField(null=True, blank=True, verbose_name="Próximo Vencimento")
    valor_mensalidade = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Valor da Mensalidade (R$)"
    )
    asaas_customer_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True,
        verbose_name="ID do Cliente (Asaas)"
    )
    asaas_ultima_cobranca_id = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="ID da Última Cobrança PIX (Asaas)"
    )
    # ==========================================================

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'

class ConfiguracaoEmail(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE)
    email = models.EmailField(verbose_name="Email de Envio")
    senha = models.CharField(max_length=255, verbose_name="Senha do Email")
    
    # Configurações IMAP (para recebimento)
    servidor_imap = models.CharField(max_length=255, verbose_name="Servidor IMAP", null=True)
    porta_imap = models.IntegerField(default=993, verbose_name="Porta IMAP", null=True)
    pasta_imap = models.CharField(max_length=50, default='INBOX', verbose_name="Pasta IMAP", null=True)
    usar_ssl_imap = models.BooleanField(default=True, verbose_name="Usar SSL IMAP", null=True)
    
    # Configurações SMTP (para envio)
    servidor_smtp = models.CharField(max_length=255, verbose_name="Servidor SMTP", null=True)
    porta_smtp = models.IntegerField(default=587, verbose_name="Porta SMTP", null=True)
    usar_tls_smtp = models.BooleanField(default=True, verbose_name="Usar TLS SMTP", null=True)
    
    # Configurações adicionais
    email_resposta = models.EmailField(blank=True, null=True, verbose_name="Email de Resposta")
    limite_diario = models.IntegerField(default=100, verbose_name="Limite de Envios Diários", null=True)
    
    def __str__(self):
        return f"Configuração de Email - {self.empresa.nome}"
    
    class Meta:
        verbose_name = "Configuração de Email"
        verbose_name_plural = "Configurações de Email"