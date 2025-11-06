# /web/staging/mudancasja/quoteflow/services.py

from bs4 import BeautifulSoup
import logging
import socket
import imaplib
import email
from email.header import decode_header
from django.utils import timezone
import re
from .models import Cotacao
from perfil.models import ConfiguracaoEmail
import traceback
from urllib.parse import urlparse
import unicodedata
import requests # Módulo importado para acessar links

logger = logging.getLogger(__name__)
socket.setdefaulttimeout(30)

def limpar_html_e_normalizar(texto):
    soup = BeautifulSoup(texto, "html.parser")
    texto_limpo = soup.get_text(separator="\n").strip()
    texto_normalizado = unicodedata.normalize('NFKC', texto_limpo)
    return texto_normalizado

def normaliza_valor(valor_str):
    valor_str = str(valor_str).replace('.', '').replace(',', '.')
    try:
        return float(valor_str)
    except (ValueError, TypeError):
        return 0.0

def normaliza_numero(num_str):
    num_str = str(num_str).replace('.', '').replace(',', '.')
    try:
        return float(num_str)
    except (ValueError, TypeError):
        return 0.0

def extrair_dominio_email(email_str):
    if not email_str:
        return None
    match = re.search(r'[\w\.-]+@([\w\.-]+)', email_str)
    return match.group(1).lower() if match else None

def determinar_rastreio(dominio_email, corpo_email_texto_puro):
    dominio = str(dominio_email).lower()
    mapeamento = {
        'cotefrete.com.br': 'CoteFrete',
        'guiadotransporte.com.br': 'Guia',
        'guiadamudanca.com.br': 'GuiaMudanca',
        'cargas.com.br': 'Cargas',
        'portaldosfretes.com.br': 'PortalDosFretes',
    }
    if dominio in mapeamento:
        return mapeamento[dominio]
    for key, value in mapeamento.items():
        if key in dominio:
            return value

    texto_lower = corpo_email_texto_puro.lower()
    keywords_origem = ['origem', 'remetente', 'coleta']
    keywords_destino = ['destino', 'destinatário', 'entrega']
    keywords_carga = ['peso', 'kg', 'volumes', 'valor da nota', 'valor da mercadoria', 'valor nf', 'dimensões']
    
    if (any(key in texto_lower for key in keywords_origem) and
        any(key in texto_lower for key in keywords_destino) and
        sum(1 for key in keywords_carga if key in texto_lower) >= 2):
        return 'Transvias'

    return 'Outros'

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
    return {
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

def _extract_line_data(text, pattern):
    """
    Função auxiliar segura que busca um padrão em uma única linha,
    sem usar re.DOTALL para evitar comportamento 'greedy' entre linhas.
    """
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        # Tenta o grupo 1 primeiro (o conteúdo)
        try:
            return match.group(1).strip()
        except IndexError:
            # Se não houver grupo 1, retorna o match inteiro
            return match.group(0).strip()
    return None


def parse_guia(texto, msg_headers=None):
    try:
        soup = BeautifulSoup(texto, 'lxml')
    except Exception as e:
        logger.error(f"Falha ao criar o objeto BeautifulSoup com lxml: {e}. Usando html.parser como fallback.")
        soup = BeautifulSoup(texto, 'html.parser')

    dados = {
        'origem': '', 'destino': '', 'volumes': 0, 'peso': 0.0,
        'valor_mercadoria': 0.0, 'observacao': '', 'contato': '',
        'telefone': '', 'email': ''
    }
    
    # Versão atualizada para v4.6
    logger.info(f"Executando parse_guia v4.6 para email com assunto: {msg_headers.get('Subject', 'N/A')}")

    try:
        # 1. Obter o texto limpo para usar RegEx
        texto_limpo = limpar_html_e_normalizar(texto)

        # 2. Extrair dados da cotação do texto limpo
        dados['origem'] = _extract_line_data(texto_limpo, r'^Origem:?\s*(.*)') or ''
        dados['destino'] = _extract_line_data(texto_limpo, r'^Destino:?\s*(.*)') or ''
        
        valor_str = _extract_line_data(texto_limpo, r'^Valor da nota:?\s*R\$\s*([\d.,]+)')
        if valor_str:
            dados['valor_mercadoria'] = normaliza_valor(valor_str)

        qtde_str = _extract_line_data(texto_limpo, r'^Quantidade:?\s*(.*)')
        if qtde_str:
            qtde_num_match = re.search(r'(\d+)', qtde_str)
            if qtde_num_match:
                dados['volumes'] = int(qtde_num_match.group(1))

        peso_str = _extract_line_data(texto_limpo, r'^Peso:?\s*(.*)')
        if peso_str:
            peso_num_match = re.search(r'([\d.,]+)', peso_str)
            if peso_num_match:
                dados['peso'] = normaliza_numero(peso_num_match.group(1))


        # 3. Lógica da Observação (v4.5)
        field_patterns = [
            r'^Origem:?.*',
            r'^Destino:?.*',
            r'^Valor da nota:?.*',
            r'^Quantidade:?.*',
            r'^Peso:?.*'
        ]
        
        last_field_end_pos = 0
        for pattern in field_patterns:
            match = re.search(pattern, texto_limpo, re.IGNORECASE | re.MULTILINE)
            if match:
                last_field_end_pos = max(last_field_end_pos, match.end())

        atenciosamente_match = re.search(r'Atenciosamente,', texto_limpo, re.IGNORECASE)
        atenciosamente_start_pos = atenciosamente_match.start() if atenciosamente_match else -1

        if last_field_end_pos > 0 and (atenciosamente_start_pos == -1 or atenciosamente_start_pos > last_field_end_pos):
            if atenciosamente_start_pos == -1:
                obs_bloco = texto_limpo[last_field_end_pos:]
            else:
                obs_bloco = texto_limpo[last_field_end_pos:atenciosamente_start_pos]
            
            obs_bloco_limpo = re.sub(r'^\s*Cubagem:?.*', '', obs_bloco, flags=re.MULTILINE)
            obs_bloco_limpo = re.sub(r'^\s*Peso Cubado:?.*', '', obs_bloco_limpo, flags=re.MULTILINE)
            obs_bloco_limpo = re.sub(r'^\s*[\d.,]+\s*(KG|M3)\s*$', '', obs_bloco_limpo, flags=re.MULTILINE | re.IGNORECASE)
            obs_bloco_limpo = re.sub(r'^\s*Lista\s*', '', obs_bloco_limpo, flags=re.MULTILINE)
            
            linhas_limpas = [linha.strip() for linha in obs_bloco_limpo.splitlines() if linha.strip()]

            if linhas_limpas and dados['destino'] and linhas_limpas[0] == dados['destino']:
                linhas_limpas.pop(0)

            linhas_processadas = []
            i = 0
            while i < len(linhas_limpas):
                linha_atual = linhas_limpas[i]
                
                if re.fullmatch(r'\d+', linha_atual) and (i + 1) < len(linhas_limpas):
                    linha_seguinte = linhas_limpas[i+1]
                    
                    if linha_seguinte.startswith('-'):
                        linhas_processadas.append(f"{linha_atual} {linha_seguinte}")
                        i += 2 
                    else:
                        linhas_processadas.append(linha_atual)
                        i += 1
                else:
                    linhas_processadas.append(linha_atual)
                    i += 1
            
            dados['observacao'] = '\n'.join(linhas_processadas)
            
        
        # 4. Lógica de extração de Contato, Email e Telefone
        
        if msg_headers:
            reply_to_header = msg_headers.get('Reply-To')
            if reply_to_header:
                email_match = re.search(r'<(.+?)>', reply_to_header)
                if email_match:
                    dados['email'] = email_match.group(1).strip()
                else:
                    dados['email'] = reply_to_header.strip()

        atenciosamente_tag = soup.find(lambda tag: tag.name == 'p' and 'atenciosamente' in tag.get_text(strip=True).lower())
        if atenciosamente_tag:
            contato_tag = atenciosamente_tag.find_next_sibling('p')
            if contato_tag and not contato_tag.find('a'):
                dados['contato'] = contato_tag.get_text(strip=True)
        
        if not dados['contato']:
            contato_match = re.search(r'Atenciosamente,\s*([^\n]+)', texto_limpo, re.IGNORECASE)
            if contato_match:
                dados['contato'] = contato_match.group(1).strip()

        whatsapp_button_text = re.compile(r'Abrir esta cotação no WhatsApp', re.IGNORECASE)
        whatsapp_link_tag = soup.find('a', string=whatsapp_button_text)

        if whatsapp_link_tag:
            redirect_url = whatsapp_link_tag.get('href')
            logger.info(f"Encontrado link de redirecionamento do WhatsApp: {redirect_url}")
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                response = requests.get(redirect_url, allow_redirects=True, timeout=15, headers=headers) 
                final_url = response.url
                logger.info(f"URL final do WhatsApp após redirecionamento: {final_url}")

                if 'wa.me' in final_url or 'api.whatsapp.com' in final_url:
                    phone_match = re.search(r'(\d{10,})', final_url)
                    if phone_match:
                        
                        # --- INÍCIO DA CORREÇÃO v4.6 (Tratamento do 9º dígito) ---
                        numero_bruto = phone_match.group(1)
                        numero_final = numero_bruto # Default
                        
                        try:
                            # Regra para números brasileiros (55) com 11 dígitos locais (DDD + 9 + Número)
                            if len(numero_bruto) == 13 and numero_bruto.startswith('55'):
                                ddd = numero_bruto[2:4]
                                numero_local_11_digitos = numero_bruto[4:] # Ex: 995058673
                                
                                if numero_local_11_digitos.startswith('9'):
                                    primeiro_digito_do_numero = numero_local_11_digitos[1]
                                    
                                    # Regra 1: Se o número (sem o 9) começa com 2, 3, 4, ou 5,
                                    # é um fixo que teve o 9 adicionado indevidamente.
                                    if primeiro_digito_do_numero in ('2', '3', '4', '5'):
                                        numero_final = "55" + ddd + numero_local_11_digitos[1:]
                                        logger.warning(f"Número {numero_bruto} corrigido (Regra Fixo 2-5). Removido 9º dígito. Novo número: {numero_final}")
                                    
                                    # Regra 2: Exceção para DDDs do Sul (41-49) onde o fixo *também* pode começar com 9.
                                    # Ex: 554199... (Fixo) -> 55419...
                                    elif ddd.startswith('4') and primeiro_digito_do_numero == '9':
                                        numero_final = "55" + ddd + numero_local_11_digitos[1:]
                                        logger.warning(f"Número {numero_bruto} corrigido (Regra Exceção DDD {ddd}). Removido 9º dígito. Novo número: {numero_final}")
                                    
                                    # Se não caiu nas regras (ex: 98..., 97...), é um celular válido e 'numero_final' permanece 'numero_bruto'.
                                    
                        except Exception as e:
                            logger.error(f"Erro ao aplicar regra do 9º dígito: {e}. Usando número bruto {numero_bruto}")
                            numero_final = numero_bruto # Em caso de erro, usa o original
                            
                        dados['telefone'] = numero_final
                        logger.info(f"✅ Telefone extraído com sucesso: {dados['telefone']}")
                        # --- FIM DA CORREÇÃO v4.6 ---
                        
                else:
                    logger.warning(f"O link de redirecionamento não levou a um URL do WhatsApp: {final_url}")
            except requests.exceptions.Timeout:
                logger.error(f"TIMEOUT ao tentar acessar o link de redirecionamento do WhatsApp: {redirect_url}. O e-mail será processado sem o telefone.")
            except requests.exceptions.RequestException as e:
                logger.error(f"Falha de rede ao tentar acessar o link de redirecionamento do WhatsApp: {e}")
        else:
             logger.warning("Não foi encontrado o botão/link 'Abrir esta cotação no WhatsApp'.")

    except Exception as e:
        logger.error(f"ERRO CRÍTICO dentro do parse_guia v4.6: {e}\n{traceback.format_exc()}")
        
    logger.info(f"[Email ID {msg_headers.get('Message-ID', 'N/A')}] Dados extraídos via parse_guia v4.6: {dados}")
    return dados

def _extract_data(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match: return match.group(1).strip()
    return None

def parse_transvias_email(text_body):
    logger.info("Tentando aplicar o parser da Transvias...")
    dados = {
        'origem': _extract_data(text_body, r'(?:CEP Origem|ORIGEM|Endereço completo de coleta|Remetente)\s*[:\s]+(.*?)(?:\n\n|\nFilial Origem|CNPJ:|\n$)'),
        'destino': _extract_data(text_body, r'(?:CEP Destino|DESTINO|Endereço completo de entrega|Destinat[áa]rio)\s*[:\s]+(.*?)(?:\n\n|\nFilial Destino|CNPJ:|\n$)'),
        'contato': _extract_data(text_body, r'(?:Razão Social/ Nome Remetente|Nome/Razão Social:)\s*([^\n\r]+)'),
        'peso': _extract_data(text_body, r'(?:Peso Calculado|PESO)\s*[:\s]*([\d.,]+)'),
        'volumes': _extract_data(text_body, r'(?:Total Volumes|Volumes)\s*[:\s]*([\d.,]+)'),
        'valor_mercadoria': _extract_data(text_body, r'(?:Valor da Mercadoria \(R\$\)|VALOR DA NOTA FISCAL R\$|Valor da NF R\$)\s*[:\s]*([\d.,]+)')
    }
    if not dados.get('contato'):
        dados['contato'] = _extract_data(text_body, r'Destinat[áa]rio/ Pagador do Frete\s*\n\s*([^\n\r]+)')
    
    for key, value in dados.items():
        if value:
            clean_value = value.replace('\r', '').strip()
            if key in ['peso', 'volumes', 'valor_mercadoria']:
                dados[key] = normaliza_valor(clean_value) if key == 'valor_mercadoria' else normaliza_numero(clean_value)
            else:
                dados[key] = clean_value

    if dados.get('origem') and dados.get('destino'):
        logger.info(f"✅ Parser da Transvias extraiu dados com sucesso.")
        return dados
        
    logger.warning("Parser da Transvias não conseguiu extrair origem e destino.")
    return {}


def parse_guiamudanca(texto):
    """
    Parser específico para e-mails vindos do 'Guia da Mudança'.
    (v3 - Corrigida para usar a função auxiliar segura _extract_line_data)
    """
    logger.info("Executando o parser para 'Guia da Mudança' (v3)...")
    texto_limpo = limpar_html_e_normalizar(texto)
    
    dados = {
        'origem': _extract_line_data(texto_limpo, r'^Origem:\s*(.*)'),
        'destino': _extract_line_data(texto_limpo, r'^Destino:\s*(.*)'),
        'observacao': _extract_line_data(texto_limpo, r'^Descrição:\s*(.*)'),
        'contato': _extract_line_data(texto_limpo, r'^Nome:\s*(.*)'),
        'telefone': _extract_line_data(texto_limpo, r'^Telefone:\s*(.*)'),
        'email': _extract_line_data(texto_limpo, r'^E-mail:\s*(.*)'),
    }

    logger.info(f"Dados extraídos via parse_guiamudanca (v3): {dados}")
    return dados


def parse_cargas(texto, msg_headers=None):
    """
    Parser específico para e-mails vindos do 'cargas.com.br'.
    (v7 - Versão Definitiva com extração de valor aprimorada)
    """
    logger.info("Executando o parser para 'Cargas.com.br' (v7 - Definitivo)...")
    texto_limpo = limpar_html_e_normalizar(texto)

    def find_field(pattern, text):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            for group in match.groups():
                if group:
                    return group.strip().lstrip(':').strip()
        return None

    dados = {
        'origem': None, 'destino': None, 'observacao': '', 'valor_mercadoria': 0.0,
        'volumes': 0, 'peso': 0.0, 'contato': '', 'telefone': '', 'email': ''
    }

    dados['origem'] = find_field(r'Origem\s*:?\s*([^\n\r]+)', texto_limpo)
    dados['destino'] = find_field(r'Destino\s*:?\s*([^\n\r]+)', texto_limpo)
    
    obs_match = re.search(r'Observações\s*:?\s*(.*)', texto_limpo, re.IGNORECASE | re.DOTALL)
    if obs_match:
        full_obs = obs_match.group(1).strip().lstrip(':').strip()
        dados['observacao'] = full_obs.split('Atenciosamente,')[0].strip()

    if not dados['origem']:
        lines = [line.strip() for line in texto_limpo.split('\n') if line.strip()]
        if lines and not re.match(r'^(Destino|Valor|Quantidade|Peso|Observações)', lines[0], re.IGNORECASE):
            dados['origem'] = lines[0]

    # --- LINHA MODIFICADA AQUI ---
    # Agora procura por "Valor da NF", "Valor de nota" ou apenas "Valor" e torna o "R$" opcional.
    valor_str = find_field(r'(?:Valor da NF|Valor de nota|Valor)\s*:?\s*(?:R\$\s*)?([\d.,]+)', texto_limpo)
    if valor_str:
        dados['valor_mercadoria'] = normaliza_valor(valor_str)

    qtd_str = find_field(r'Quantidade\s*:?\s*([\d.,]+)', texto_limpo)
    if qtd_str: dados['volumes'] = int(normaliza_numero(qtd_str))
    
    peso_str = find_field(r'Peso\s*:?\s*([\d.,]+)', texto_limpo)
    if peso_str: dados['peso'] = normaliza_numero(peso_str)

    medidas_str = find_field(r'Medidas dos volumes\s*:?\s*(.*)', texto_limpo)
    if medidas_str:
        dados['observacao'] += f"\nMedidas: {medidas_str}"
        if dados['volumes'] == 0:
            vol_match = re.search(r'(\d+)\s*volume', medidas_str, re.IGNORECASE)
            if vol_match: dados['volumes'] = int(vol_match.group(1))
        if dados['peso'] == 0.0:
            peso_match = re.search(r'([\d.,]+)\s*(?:kilos|kg)', medidas_str, re.IGNORECASE)
            if peso_match: dados['peso'] = normaliza_numero(peso_match.group(1))

    if msg_headers:
        reply_to_header = msg_headers.get('Reply-To')
        if reply_to_header:
            email_match = re.search(r'<(.+?)>', reply_to_header)
            if email_match:
                dados['email'] = email_match.group(1).strip()
                nome_match = re.search(r'\"?(.+?)\"?\s*<', reply_to_header)
                if nome_match:
                    dados['contato'] = nome_match.group(1).strip().replace('"', '')
            else:
                dados['email'] = reply_to_header.strip()

    if not dados['contato'] or not dados['telefone']:
        bloco_atenciosamente = texto_limpo.split('Atenciosamente,')
        if len(bloco_atenciosamente) > 1:
            bloco_contato = bloco_atenciosamente[1]
            
            telefone_match = re.search(r'\(?\d{2}\)?\s*[9\s]?\s*\d{4,5}-?\d{4}', bloco_contato)
            if telefone_match:
                dados['telefone'] = telefone_match.group(0).strip()

            if not dados['email']:
                email_match = re.search(r'[\w\.-]+@[\w\.-]+', bloco_contato)
                if email_match:
                    dados['email'] = email_match.group(0).strip()
            
            if not dados['contato']:
                linhas_contato = [line.strip() for line in bloco_atenciosamente.split('\n') if line.strip() and '@' not in line]
                if linhas_contato:
                    primeira_linha = linhas_contato[0]
                    if dados['telefone'] and dados['telefone'] in primeira_linha:
                        dados['contato'] = primeira_linha.replace(dados['telefone'], '').strip()
                    elif not any(char.isdigit() for char in primeira_linha):
                         dados['contato'] = primeira_linha
                
    logger.info(f"Dados extraídos via parse_cargas (v7): {dados}")
    return dados


# --- FIM DAS NOVAS FUNÇÕES E CORREÇÕES ---


def inferir_tipo_frete(subject):
    subject = subject.lower()
    if 'mudança' in subject or 'mudanças' in subject:
        return 'Mudanças'
    elif 'carga' in subject or 'cargas' in subject:
        return 'Carga em Geral'
    elif 'máquina' in subject:
        return 'Máquina'
    elif 'moto' in subject:
        return 'Moto'
    elif 'material sem nota' in subject:
        return 'Material Sem Nota'
    elif 'veículo' in subject or 'veículos' in subject:
        return 'Veículos'
    elif 'transporte' in subject:
        return 'Transporte de Cargas'
    else:
        return 'Transporte de Cargas'

# O resto do arquivo (carregar_cotacoes_email) continua o mesmo
def carregar_cotacoes_email(empresa):
    try:
        config = ConfiguracaoEmail.objects.get(empresa=empresa)
        novas_cotacoes = 0
        logger.info(f"Iniciando conexão IMAP para empresa {empresa} no servidor {config.servidor_imap}:{config.porta_imap}")
        
        if config.usar_ssl_imap:
            mail = imaplib.IMAP4_SSL(config.servidor_imap, config.porta_imap or 993)
        else:
            mail = imaplib.IMAP4(config.servidor_imap, config.porta_imap or 143)

        mail.login(config.email, config.senha)
        
        pasta_imap_db = config.pasta_imap or 'INBOX'
        pasta_imap_servidor = None

        status, pastas_raw = mail.list()
        if status != 'OK':
            raise Exception("Não foi possível listar as pastas do servidor IMAP.")
        
        for pasta_bytes in pastas_raw:
            nome_pasta_servidor = pasta_bytes.decode().split(' "." ')[-1].strip('"')
            if nome_pasta_servidor.lower() == pasta_imap_db.lower():
                pasta_imap_servidor = nome_pasta_servidor
                logger.info(f"Pasta '{pasta_imap_db}' encontrada no servidor como '{pasta_imap_servidor}'.")
                break
        
        if not pasta_imap_servidor:
            logger.error(f"❌ A pasta IMAP '{pasta_imap_db}' não foi encontrada no servidor para a empresa {empresa}.")
            mail.logout()
            return 0

        status, _ = mail.select(f'"{pasta_imap_servidor}"')
        if status != 'OK':
            logger.error(f"❌ Falha ao selecionar a pasta '{pasta_imap_servidor}' mesmo após encontrá-la.")
            mail.logout()
            return 0
        
        status, messages = mail.search(None, 'UNSEEN')
        
        if status != 'OK' or not messages[0]:
            logger.info(f"Nenhum email novo encontrado na pasta '{pasta_imap_servidor}'.")
            mail.logout()
            return 0

        email_ids = messages[0].split()
        logger.info(f"Total de emails novos encontrados: {len(email_ids)}")

        for email_id in email_ids:
            try:
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    logger.warning(f"Falha ao buscar corpo do email {email_id.decode()}")
                    continue

                msg = email.message_from_bytes(msg_data[0][1])
                msg_id = msg.get('Message-ID', '').strip()

                if not msg_id or Cotacao.objects.filter(email_message_id=msg_id).exists():
                    logger.info(f"Email {email_id.decode()} (ID: {msg_id}) já importado ou sem Message-ID, pulando.")
                    continue

                subject = ''.join(
                    part.decode(encoding or 'utf-8', errors='ignore') if isinstance(part, bytes) else part
                    for part, encoding in decode_header(msg.get('Subject', ''))
                )

                html_body, plain_body = None, None
                if msg.is_multipart():
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        cdisp = str(part.get('Content-Disposition'))
                        if ctype == 'text/html' and 'attachment' not in cdisp:
                            html_body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                        if ctype == 'text/plain' and 'attachment' not in cdisp:
                            plain_body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                else:
                    plain_body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')

                body_para_parse = html_body if html_body else plain_body
                if not body_para_parse:
                    logger.warning(f"Email {email_id.decode()} sem corpo de texto. Pulando.")
                    continue
                
                remetente = msg.get('From', '')
                dominio_remetente = extrair_dominio_email(remetente)
                rastreio = determinar_rastreio(dominio_remetente, '') # Passar texto vazio para o segundo argumento
                
                dados = {}
                if rastreio == 'Guia':
                    dados = parse_guia(body_para_parse, msg)
                else:
                    dados = parse_cotefrete(body_para_parse)
                
                if dados.get('origem') and dados.get('destino'):
                    Cotacao.objects.create(
                        empresa=empresa,
                        origem=dados['origem'],
                        destino=dados['destino'],
                        prazo_coleta='Até 24 horas',
                        prazo_entrega='Até 24 horas',
                        volumes=dados.get('volumes', 0) or 0,
                        peso=dados.get('peso', 0.0) or 0.0,
                        valor_mercadoria=dados.get('valor_mercadoria', 0.0) or 0.0,
                        cubagem=dados.get('cubagem', 0.0),
                        observacao=dados.get('observacao', ''),
                        contato=dados.get('contato', ''),
                        telefone=dados.get('telefone', ''),
                        email=dados.get('email', ''),
                        email_message_id=msg_id,
                        status_cotacao="Em Negociação",
                        status_envio='Falta Cubagem',
                        tipo_frete=inferir_tipo_frete(subject),
                        rastreio=rastreio,
                    )
                    novas_cotacoes += 1
                    logger.info(f"✅ Cotação criada a partir do email {email_id.decode()} (Message-ID: {msg_id}) - Rastreio: {rastreio}")
                else:
                    logger.warning(f"⚠️ Email {email_id.decode()} não contém dados válidos de origem/destino. Dados extraídos: {dados}")

            except Exception as e:
                logger.warning(f"[Email ID {email_id.decode()}] Erro ao processar: {e}\n{traceback.format_exc()}")
                continue

        mail.logout()
        logger.info(f"🚀 Total de novas cotações criadas: {novas_cotacoes}")
        return novas_cotacoes

    except ConfiguracaoEmail.DoesNotExist:
        logger.error(f"❌ Configuração de email para a empresa {empresa} não encontrada.")
        return 0
    except Exception as e:
        logger.error(f"❌ Erro ao carregar cotações:\n{traceback.format_exc()}")
        raise Exception(f'Erro ao carregar cotações: {str(e)}')