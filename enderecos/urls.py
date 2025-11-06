# enderecos/urls.py
from django.urls import path
from .views import buscar_cep_local

app_name = 'enderecos'

urlpatterns = [
    path('api/cep/<str:cep>/', buscar_cep_local, name='buscar_cep_local'),
]