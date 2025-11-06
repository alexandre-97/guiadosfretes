# quoteflow/asaas_service.py
import requests
import logging
from django.conf import settings
from datetime import date, timedelta
import re
import json

logger = logging.getLogger(__name__)

def _get_headers():
    return {
        "Content-Type": "application/json",
        "access_token": settings.ASAAS_API_KEY
    }

def criar_ou_atualizar_cliente_asaas(empresa):
    """Cria um cliente na Asaas ou atualiza, com sanitização e log detalhado."""
    headers = _get_headers()

    email_cliente = None
    if empresa.perfis.exists():
        primeiro_perfil = empresa.perfis.order_by('id').first()
        if primeiro_perfil and hasattr(primeiro_perfil, 'usuario'):
            email_cliente = primeiro_perfil.usuario.email

    cpf_cnpj_limpo = re.sub(r'[^\d]', '', empresa.cpf_cnpj or '')

    payload = {
        "name": empresa.nome,
        "company": empresa.razao_social or empresa.nome,
        "email": email_cliente,
        "phone": empresa.telefone,
        "externalReference": str(empresa.id),
        "cpfCnpj": cpf_cnpj_limpo
    }

    print("\n--- INICIANDO CRIAÇÃO/ATUALIZAÇÃO DE CLIENTE ASAAS ---")
    print(f"PAYLOAD ENVIADO PARA ASAAS: {json.dumps(payload, indent=2)}")

    if empresa.asaas_customer_id:
        url = f"{settings.ASAAS_API_URL}/customers/{empresa.asaas_customer_id}"
        response = requests.post(url, json=payload, headers=headers)
    else:
        url = f"{settings.ASAAS_API_URL}/customers"
        response = requests.post(url, json=payload, headers=headers)

    print(f"RESPOSTA DA ASAAS (Cliente): Status={response.status_code}, Corpo={response.text}")
    print("---------------------------------------------------\n")

    if response.status_code in [200, 201]:
        customer_data = response.json()
        if not empresa.asaas_customer_id:
            empresa.asaas_customer_id = customer_data['id']
            empresa.save(update_fields=['asaas_customer_id'])
        logger.info(f"Cliente '{empresa.nome}' criado/atualizado na Asaas com ID: {empresa.asaas_customer_id}")
        return empresa.asaas_customer_id
    else:
        logger.error(f"Erro ao criar/atualizar cliente Asaas para '{empresa.nome}': {response.text}")
        raise Exception(f"Falha ao criar/atualizar cliente na Asaas: {response.text}")

def gerar_cobranca_pix_mensal(empresa):
    """Gera uma nova cobrança PIX para o próximo mês da empresa."""
    logger.info(f"Forçando a atualização dos dados do cliente '{empresa.nome}' na Asaas...")
    customer_id = criar_ou_atualizar_cliente_asaas(empresa)
    if not customer_id:
        raise Exception(f"Não foi possível criar ou ATUALIZAR o cliente '{empresa.nome}' na Asaas.")

    if not empresa.valor_mensalidade or empresa.valor_mensalidade <= 0:
        raise ValueError("Empresa sem valor de mensalidade definido.")

    headers = _get_headers()
    url = f"{settings.ASAAS_API_URL}/payments"
    due_date = date.today() + timedelta(days=7)

    payload = {
        "customer": customer_id,
        "billingType": "PIX",
        "value": float(empresa.valor_mensalidade),
        "dueDate": due_date.strftime("%Y-%m-%d"),
        "description": f"Mensalidade PreciFlow - Referente a {due_date.strftime('%m/%Y')}"
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        payment_data = response.json()
        empresa.asaas_ultima_cobranca_id = payment_data['id']
        empresa.status_assinatura = 'PENDENTE'
        empresa.save(update_fields=['asaas_ultima_cobranca_id', 'status_assinatura'])
        logger.info(f"Cobrança PIX {payment_data['id']} gerada para a empresa '{empresa.nome}'.")
        return payment_data
    else:
        logger.error(f"Erro ao gerar cobrança PIX para '{empresa.nome}': {response.text}")
        raise Exception(f"Erro na API Asaas: {response.text}")