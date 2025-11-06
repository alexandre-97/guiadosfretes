import re
from bs4 import BeautifulSoup
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'loja.settings')  # ajuste aqui seu módulo settings
django.setup()

from django.contrib.auth.models import User
from perfil.models import ConfiguracaoEmail, Perfil

def main():
    # Tenta buscar o usuário 'eduardo'
    try:
        usuario = User.objects.get(username='eduardo')
    except User.DoesNotExist:
        print("Usuário 'eduardo' não encontrado.")
        return

    # Busca o perfil do usuário
    try:
        perfil = Perfil.objects.get(usuario=usuario)
    except Perfil.DoesNotExist:
        print(f"Perfil para o usuário 'eduardo' não encontrado.")
        return

    empresa = perfil.empresa
    if not empresa:
        print(f"Usuário 'eduardo' não está associado a nenhuma empresa.")
        return

    # Busca a configuração de email da empresa do 'eduardo'
    try:
        config = ConfiguracaoEmail.objects.get(empresa=empresa)
    except ConfiguracaoEmail.DoesNotExist:
        print(f"Nenhuma configuração de email encontrada para a empresa {empresa.nome}.")
        return

    # Exibe os dados da configuração
    print(f"Configuração de email para a empresa {empresa.nome}:")
    print(f"Email de envio: {config.email}")
    print(f"Servidor IMAP: {config.servidor_imap}:{config.porta_imap}")
    print(f"Pasta IMAP: {config.pasta_imap}")
    print(f"Usar SSL IMAP: {config.usar_ssl_imap}")
    print(f"Servidor SMTP: {config.servidor_smtp}:{config.porta_smtp}")

if __name__ == "__main__":
    main()

from perfil.models import ConfiguracaoEmail
def limpar_html_e_normalizar(texto):
    soup = BeautifulSoup(texto, "html.parser")
    texto_limpo = soup.get_text(separator="\n")
    return texto_limpo.strip()

def normaliza_valor(valor_str):
    valor_str = valor_str.replace('.', '').replace(',', '.')
    try:
        return float(valor_str)
    except ValueError:
        return 0.0

def normaliza_numero(num_str):
    num_str = num_str.replace('.', '').replace(',', '.')
    try:
        return float(num_str)
    except ValueError:
        return 0.0

def parse_guia(texto):
    print("== Texto original ==\n", texto[:500], "\n---")
    texto = limpar_html_e_normalizar(texto)
    print("== Texto limpo ==\n", texto[:500], "\n---")

    origem = re.search(r'(?i)Origem:\s*([^\n\r]+)', texto)
    destino = re.search(r'(?i)Destino:\s*([^\n\r]+)', texto)
    valor = re.search(r'(?i)Valor(?: da nota)?:\s*R\$\s*([\d.,]+)', texto)
    quantidade = re.search(r'(?i)Quantidade:\s*(\d+)', texto)
    peso = re.search(r'(?i)Peso:\s*([\d.,]+)', texto)
    
    descricao_match = re.search(
        r'(?i)(Segue abaixo os dados da carga:|Descri[çc][ãa]o:|Dados da carga:)\s*(.*?)\s*(?:Atenciosamente|Contato:|$)', 
        texto, 
        re.DOTALL
    )
    
    contato_match = re.search(
        r'(?i)(?:Atenciosamente,|De|Remetente:)\s*(.*?)(?:\s*<|\n|$)', 
        texto
    )
    
    email_match = re.search(
        r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', 
        texto
    )
    
    telefone_patterns = [
        r'(?i)(?:Telefone:|Tel\.|Fone:|Celular:|WhatsApp:|Contato:)\s*([+\d\s().-]{8,})',
        r'(\+?\d{2}\s?\(?\d{2}\)?\s?\d{4,5}[-.\s]?\d{4})',
        r'(\(\d{2}\)\s?\d{4,5}-\d{4})'
    ]
    
    telefone = ""
    for pattern in telefone_patterns:
        telefone_match = re.search(pattern, texto)
        if telefone_match:
            telefone = telefone_match.group(1).strip()
            break

    descricao = descricao_match.group(2).strip() if descricao_match else ""
    contato = contato_match.group(1).strip() if contato_match else ""
    email = email_match.group(1).strip() if email_match else ""

    descricao = ' '.join(descricao.split())
    contato = contato.split('<')[0].strip()
    telefone = re.sub(r'[^\d+]', '', telefone)

    resultado = {
        'origem': origem.group(1).strip() if origem else '',
        'destino': destino.group(1).strip() if destino else '',
        'volumes': int(quantidade.group(1)) if quantidade else 0,
        'peso': normaliza_numero(peso.group(1)) if peso else 0.0,
        'valor_mercadoria': normaliza_valor(valor.group(1)) if valor else 0.0,
        'observacao': descricao,
        'contato': contato,
        'telefone': telefone,
        'email': email
    }

    print("== Resultado do parse_guia ==\n", resultado)
    return resultado


def parse_cotefrete(texto):
    texto = limpar_html_e_normalizar(texto)

    origem = re.search(r'(?i)Origem:\s*([^\n\r]+)', texto)
    destino = re.search(r'(?i)Destino:\s*([^\n\r]+)', texto)
    quantidade = re.search(r'Quantidade:\s*(\d+)', texto)
    peso = re.search(r'Peso:\s*([\d,.]+)', texto)
    valor = re.search(r'Valor:\s*R\$ ?([\d,.]+)', texto)
    info_adicionais = re.search(r'Informações adicionais:\s*(.*?)(?:Dados de contato:|$)', texto, re.DOTALL)
    contato = re.search(r'Dados de contato:\s*Nome:\s*(.*)', texto)
    telefone = re.search(r'Telefone:\s*\+?[\d\s()-]+', texto)
    email_cliente = re.search(r'Email:\s*([^\s]+@[^\s]+)', texto)

    resultado = {
        'origem': origem.group(1).strip() if origem else '',
        'destino': destino.group(1).strip() if destino else '',
        'volumes': int(quantidade.group(1)) if quantidade else 0,
        'peso': normaliza_numero(peso.group(1)) if peso else 0.0,
        'valor_mercadoria': normaliza_valor(valor.group(1)) if valor else 0.0,
        'observacao': info_adicionais.group(1).strip() if info_adicionais else '',
        'contato': contato.group(1).strip() if contato else '',
        'telefone': telefone.group(0).replace('Telefone:', '').strip() if telefone else '',
        'email': email_cliente.group(1).strip() if email_cliente else ''
    }

    print("== Resultado do parse_cotefrete ==\n", resultado)
    return resultado


if __name__ == "__main__":
    # Cole aqui o corpo do email para teste, com ou sem HTML
    texto_exemplo = """
    Cole o corpo do email aqui para testar
    """

    print("Testando parse_guia...\n")
    parse_guia(texto_exemplo)

    print("\nTestando parse_cotefrete...\n")
    parse_cotefrete(texto_exemplo)

