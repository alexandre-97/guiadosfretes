from django.urls import path
from . import views

app_name = 'perfil'

urlpatterns = [
    path('login/', views.Login.as_view(), name='login'),
    path('logout/', views.Logout.as_view(), name='logout'),
    path('meus-dados/', views.meus_dados_view, name='meus_dados'),
    path('gerar-qrcode/', views.gerar_qrcode_view, name='gerar_qrcode'),
    # A URL abaixo será usada no futuro para a verificação de status em tempo real
    path('api/verificar-status/', views.verificar_status_whatsapp_api, name='api_verificar_status'),
]