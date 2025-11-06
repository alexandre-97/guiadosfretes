# quoteflow/models.py

from django.db import models, transaction
from django.conf import settings
from perfil.models import User
import logging
from django.utils import timezone

# Configura o logger para registrar informações importantes
logger = logging.getLogger(__name__)

class Cotacao(models.Model):
    # --- SEUS CHOICES (STATUS_COTACAO, STATUS_ENVIO, etc.) CONTINUAM AQUI ---
    STATUS_COTACAO_CHOICES = [
        ('Em Negociação', 'Em Negociação'),
        ('Aprovada', 'Aprovada'),
        ('Finalizada', 'Finalizada'),
        ('Cancelada', 'Cancelada'),
        ('Reprovada', 'Reprovada'),
    ]

    STATUS_ENVIO_CHOICES = [
        ('Duplicada','Duplicada'),
        ('Rejeitada','Rejeitada'),
        ('Falta Cubagem','Falta Cubagem'),
        ('Falta Preço','Falta Preço'),
        ('Enviado Whats + Email','Enviado Whats + Email'),
        ('Enviado Whats','Enviado Whats'),
        ('Enviado Email','Enviado Email'),
        ('Envio Negado','Envio Negado'),
        ('Faltam Medidas','Faltam Medidas'),
        ('Não Enviado','Não Enviado'),
        ('Aguardando Coleta','Aguardando Coleta'),
        ('Aguardando Pagamento','Aguardando Pagamento'),
    ]

    RASTREIO_CHOICES = [
        ('Cargas','Cargas'),
        ('CoteFrete','CoteFrete'),
        ('CoteTransporte','CoteTransporte'),
        ('Outros','Outros'),
        ('Email','Email'),
        ('Google','Google'),
        ('Guia','Guia'),
        ('GuiaMudanca', 'GuiaMudanca'),
        ('Indicação','Indicação'),
        ('PortalDosFretes','PortalDosFretes'),
        ('Transvias','Transvias'),
        ('WhatsApp','WhatsApp'),
        ('Site','Site'),
        ('Telefone','Telefone'),
    ]
    TIPO_FRETE_CHOICES = [
        ('Transporte de Cargas','Transporte de Cargas'),
        ('Mudanças','Mudanças'),
        ('Material Sem Nota','Material Sem Nota'),
        ('Moto','Moto'),
        ('Carga em Geral','Carga em Geral'),
        ('Máquina','Máquina'),
        ('Veículos','Veículos'),
        ('Não especificado','Não especificado'),
    ]

    # --- SEUS CAMPOS EXISTENTES CONTINUAM AQUI ---
    contato = models.CharField(max_length=100, blank=True)
    telefone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True)
    origem = models.CharField(max_length=100)
    destino = models.CharField(max_length=100)
    prazo_coleta = models.CharField(max_length=50)
    prazo_entrega = models.CharField(max_length=50)
    tipo_frete = models.CharField(
        max_length=100,
        choices=TIPO_FRETE_CHOICES,
        default='Transporte de Cargas'
        )   
    rastreio = models.CharField(
        max_length=50,
        choices=RASTREIO_CHOICES,
        blank=True,
    )
    status_cotacao = models.CharField(
        max_length=50,
        choices=STATUS_COTACAO_CHOICES,
        default='Em Negociação'
    )
    status_envio = models.CharField(
        max_length=50,
        choices=STATUS_ENVIO_CHOICES,
        default='Não Enviado',
    )
    volumes = models.IntegerField(blank=True, null=True)
    cubagem = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    peso = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valor_mercadoria = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valor_proposta = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    observacao = models.TextField(blank=True)
    data_recebimento = models.DateTimeField(auto_now_add=True)
    responsavel = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cotacoes_responsaveis'
    )
    empresa = models.ForeignKey(
        'perfil.Empresa', 
        on_delete=models.CASCADE, 
        related_name='cotacoes',
        null=True,
        blank=True
    )
    proposta_gerada = models.FileField(upload_to='propostas/', null=True, blank=True)
    email_message_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text='Message-ID do email para evitar duplicação'
    )
    numero_sequencial_empresa = models.PositiveIntegerField(
        editable=False,
        null=True,
        blank=True,
        help_text="Número sequencial único por empresa, usado para gerar o número da proposta."
    )
    visivel = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Visível",
        help_text="Indica se a cotação está ativa e visível para os usuários."
    )

    # =========================================================================
    # NOVOS CAMPOS PARA GRÁFICOS E RASTREAMENTO DE ATIVIDADE
    # =========================================================================
    data_ultima_modificacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Modificação",
        help_text="Data e hora da última atualização da cotação."
    )
    data_finalizacao = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Data de Finalização",
        help_text="Data em que a cotação mudou para um status final (Finalizada, Aprovada, etc.)."
    )
    # =========================================================================

    class Meta:
        # Garante que a combinação de empresa e número sequencial seja sempre única.
        unique_together = ('empresa', 'numero_sequencial_empresa')

    def save(self, *args, **kwargs):
        # Define os status que consideramos como "finais"
        STATUS_FINAIS = ['Aprovada', 'Finalizada', 'Cancelada', 'Reprovada']

        # --- LÓGICA PARA ATUALIZAR A DATA DE FINALIZAÇÃO ---
        # Verifica se o objeto já existe no banco (tem uma chave primária)
        if self.pk is not None:
            try:
                # Pega a versão original do objeto do banco de dados
                original = Cotacao.objects.get(pk=self.pk)
                
                # Compara o status antigo com o novo
                if original.status_cotacao != self.status_cotacao:
                    # Se o novo status é um dos finais E a data de finalização ainda não foi definida
                    if self.status_cotacao in STATUS_FINAIS and self.data_finalizacao is None:
                        self.data_finalizacao = timezone.now()
            except Cotacao.DoesNotExist:
                pass 
        
        # --- LÓGICAS EXISTENTES ---

        # 1. Lógica para gerar o número sequencial (APENAS NA CRIAÇÃO)
        if self.pk is None and self.empresa and self.numero_sequencial_empresa is None:
            with transaction.atomic():
                ultima_cotacao = Cotacao.objects.filter(
                    empresa=self.empresa
                ).select_for_update().order_by('-numero_sequencial_empresa').first()
                
                if ultima_cotacao and ultima_cotacao.numero_sequencial_empresa:
                    self.numero_sequencial_empresa = ultima_cotacao.numero_sequencial_empresa + 1
                else:
                    self.numero_sequencial_empresa = 1
        
        # 2. Lógica existente para definir o rastreio
        if not self.rastreio:
            origem_lower = self.origem.lower()
            if 'cotefrete' in origem_lower:
                self.rastreio = 'CoteFrete'
            elif 'guia' in origem_lower:
                self.rastreio = 'Guia'
            elif 'indicacao' in origem_lower:
                self.rastreio = 'Indicação'

        # 3. Chama o método save original UMA VEZ no final para salvar o objeto no banco.
        super().save(*args, **kwargs)
    
    # --- SEUS MÉTODOS @property e __str__ CONTINUAM AQUI ---
    @property
    def valor_mercadoria_formatado(self):
        return f"R$ {float(self.valor_mercadoria):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if self.valor_mercadoria else 'R$ 0,00'

    @property
    def valor_proposta_formatado(self):
        return f"R$ {float(self.valor_proposta):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if self.valor_proposta else 'R$ 0,00'

    def is_enviado(self):
        return any(x in self.status_envio for x in ['Enviado Whats', 'Enviado Email'])
    
    @property
    def proposta_id_url(self):
        """
        Gera o identificador único usado na URL, como 'EXI123QF'.
        """
        if self.empresa and self.numero_sequencial_empresa:
            nome_empresa = ''.join(filter(str.isalnum, self.empresa.nome))[:3].upper()
            return f"{nome_empresa}{self.numero_sequencial_empresa}QF"
        return str(self.id)

    def __str__(self):
        # Usa o ID da proposta (EX: 'EXI123QF') que é mais amigável ao usuário
        return f'Cotação {self.proposta_id_url} ({self.origem} -> {self.destino})'

# ... (O resto do seu models.py, como TemplateProposta e EmailEnviado, continua aqui sem alterações)
class TemplateProposta(models.Model):
    nome = models.CharField(max_length=100)
    arquivo = models.FileField(upload_to='templates_propostas/')
    mensagem_padrao = models.TextField()
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome
    

class EmailEnviado(models.Model):
    cotacao = models.ForeignKey('quoteflow.Cotacao', on_delete=models.CASCADE, related_name='emails_enviados')
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    destinatario = models.EmailField()
    assunto = models.CharField(max_length=255)
    corpo = models.TextField()
    anexo = models.FileField(upload_to='emails_anexos/', null=True, blank=True)
    data_envio = models.DateTimeField(auto_now_add=True)
    enviado_com_sucesso = models.BooleanField(default=False)
    erro = models.TextField(blank=True)

    def __str__(self):
        return f"E-mail para {self.destinatario} (Cotação #{self.cotacao.id})"
    
class UpdatePost(models.Model):
    title = models.CharField(max_length=200, verbose_name="Título")
    content = models.TextField(verbose_name="Conteúdo")
    publication_date = models.DateTimeField(auto_now_add=True, verbose_name="Data de Publicação")
    is_published = models.BooleanField(default=True, verbose_name="Publicado")

    class Meta:
        verbose_name = "Post de Atualização"
        verbose_name_plural = "Posts de Atualizações"
        ordering = ['-publication_date']
        # ADICIONE ESTA LINHA DE PERMISSÃO
        permissions = [
            ("pode_gerenciar_updates", "Pode gerenciar atualizações"),
        ]

    def __str__(self):
        return self.title
    

class FAQ(models.Model):
    CATEGORIA_CHOICES = [
        ('GERAL', 'Geral'),
        ('LISTA', 'Página Principal (Lista de Cotações)'),
        ('EDICAO', 'Página de Edição de Cotação'),
    ]

    pergunta = models.CharField(max_length=255, verbose_name="Pergunta")
    resposta = models.TextField(verbose_name="Resposta", help_text="Você pode usar tags HTML básicas como <ul>, <li>, <strong>, etc.")
    categoria = models.CharField(max_length=50, choices=CATEGORIA_CHOICES, default='GERAL', verbose_name="Categoria")
    ordem = models.PositiveIntegerField(default=0, help_text="Itens com número menor aparecem primeiro.", verbose_name="Ordem de Exibição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        verbose_name = "Pergunta Frequente (FAQ)"
        verbose_name_plural = "Perguntas Frequentes (FAQ)"
        ordering = ['categoria', 'ordem', 'pergunta']

    def __str__(self):
        return self.pergunta
    
class UserUpdateStatus(models.Model):
    """
    Modelo 'through' para rastrear o status de leitura de cada post
    de atualização para cada usuário.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='update_statuses')
    post = models.ForeignKey(UpdatePost, on_delete=models.CASCADE, related_name='read_statuses')
    has_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Status de Leitura de Atualização"
        verbose_name_plural = "Status de Leitura de Atualizações"
        # Garante que não haja entradas duplicadas para o mesmo usuário e post
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} - {self.post.title} (Lido: {self.has_read})"
