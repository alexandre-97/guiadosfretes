from django import forms
from django.contrib.auth.models import User
from . import models


class PerfilForm(forms.ModelForm):
    class Meta:
        model = models.Perfil
        fields = '__all__'
        exclude = ('usuario',)

# --- GARANTA QUE ESTA CLASSE ESTEJA NO ARQUIVO ---
class MeusDadosForm(forms.ModelForm):
    """
    Um formulário específico para a página 'Meus Dados', 
    contendo apenas os campos que o usuário pode editar.
    """
    class Meta:
        model = models.Perfil
        # Especificamos apenas os campos que queremos no formulário.
        fields = ['nome_completo', 'telefone_whatsapp']
        widgets = {
            'nome_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone_whatsapp': forms.TextInput(attrs={'class': 'form-control'}),
        }
