# enderecos/admin.py
from django.contrib import admin
from .models import CEP

@admin.register(CEP)
class CEPAdmin(admin.ModelAdmin):
    list_display = ('cep', 'logradouro', 'bairro', 'cidade', 'uf')
    search_fields = ('cep', 'logradouro', 'cidade')
    list_filter = ('uf',)