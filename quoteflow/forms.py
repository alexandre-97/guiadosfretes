# quoteflow/forms.py
from django import forms
from perfil.models import Perfil
from .models import FAQ, Cotacao, UpdatePost, MensagemPersonalizada

# Linha corrigida: o "class CotacaoForm" agora está na linha de baixo
class CotacaoForm(forms.ModelForm):
    class Meta:
        model = Cotacao
        fields = [
            'tipo_frete', 'status_cotacao', 'origem', 'destino', 'contato',
            'telefone', 'email', 'volumes', 'peso', 'cubagem', 'valor_mercadoria',
            'prazo_coleta', 'prazo_entrega', 'valor_proposta', 'rastreio',
            'status_envio', 'observacao'
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        self.fields['observacao'].widget.attrs.update({
            'class': 'form-control',
            'rows': '4',
            'style': 'min-height: 125px; resize: vertical;',
        })
        self.fields['tipo_frete'].widget.attrs['class'] = 'form-select'
        self.fields['status_cotacao'].widget.attrs['class'] = 'form-select'
        self.fields['status_envio'].widget.attrs['class'] = 'form-select'
        self.fields['rastreio'].widget.attrs['class'] = 'form-select'
        
        text_fields = ['origem', 'destino', 'contato', 'telefone', 'email', 'prazo_coleta', 'prazo_entrega']
        for field_name in text_fields:
            self.fields[field_name].widget.attrs['class'] = 'form-control'
            
        numeric_fields = ['volumes', 'peso', 'cubagem', 'valor_mercadoria', 'valor_proposta']
        for field_name in numeric_fields:
            if 'class' not in self.fields[field_name].widget.attrs:
                self.fields[field_name].widget.attrs['class'] = 'form-control'

class UpdatePostForm(forms.ModelForm):
    class Meta:
        model = UpdatePost
        fields = ['title', 'content', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'title': 'Título da Atualização',
            'content': 'Conteúdo',
            'is_published': 'Publicar agora?',
        }

class PerfilForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['nome_completo', 'telefone_whatsapp']
        widgets = {
            'nome_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone_whatsapp': forms.TextInput(attrs={'class': 'form-control'}),
        }

class FAQForm(forms.ModelForm):
    class Meta:
        model = FAQ
        fields = ['pergunta', 'resposta', 'categoria', 'ordem', 'ativo']
        widgets = {
            'pergunta': forms.TextInput(attrs={'class': 'form-control'}),
            'resposta': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class CadastroForm(forms.Form):
    """
    Formulário de Geração de Leads (Cadastro).
    Não salva no banco, apenas envia por e-mail.
    """
    PLANO_CHOICES = [
        ('ESSENCIAL', 'Plano Essencial (R$ 350/mês)'),
        ('PROFISSIONAL', 'Plano Profissional (R$ 700/mês)'),
        ('ENTERPRISE', 'Plano Enterprise (Sob Consulta)'),
    ]

    nome_completo = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu nome completo'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'seu@email.com'})
    )
    telefone_whatsapp = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(11) 99999-9999'})
    )
    nome_empresa = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da sua Transportadora (Opcional)'})
    )
    plano_interesse = forms.ChoiceField(
        choices=PLANO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Plano de Interesse"
    )        

class MensagemPersonalizadaForm(forms.ModelForm):
    class Meta:
        model = MensagemPersonalizada
        fields = ['titulo', 'conteudo', 'ativo']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Cobrança Amigável'}),
            'conteudo': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'id': 'txtConteudoTemplate'}), # ID importante para o JS
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }