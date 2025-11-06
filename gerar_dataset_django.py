# gerar_dataset_django.py
# (Coloque este arquivo na pasta raiz do seu projeto Django: /web/mudancasja/)

import os
import django
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut
import time

print("Iniciando a conexão com o ambiente Django...")

# --- A MÁGICA PARA CARREGAR O DJANGO ---
# CORRIGIDO: Usando 'loja.settings' como você informou.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'loja.settings') 
django.setup()
# -----------------------------------------

# Agora que o Django está carregado, podemos importar os models
# O nome do seu app é 'quoteflow', então a importação está correta.
from quoteflow.models import Cotacao

print("Conexão bem-sucedida! Acessando os modelos do QuoteFlow...")

# --- Ferramentas para Cálculo de Distância ---
geolocator = Nominatim(user_agent="quoteflow_ai_trainer_v2")
location_cache = {}

def get_coords(cidade):
    if cidade in location_cache:
        return location_cache[cidade]
    try:
        # Adicionamos 'Brazil' para ajudar o geolocalizador a ser mais preciso
        location = geolocator.geocode(f"{cidade}, Brazil")
        time.sleep(1) # Respeitar os limites da API
        if location:
            coords = (location.latitude, location.longitude)
            location_cache[cidade] = coords
            return coords
        print(f"  -> Aviso: Localização para '{cidade}' não encontrada.")
        return None
    except (GeocoderUnavailable, GeocoderTimedOut):
        print(f"Serviço de geocodificação indisponível. Tentando novamente em 5s...")
        time.sleep(5)
        return get_coords(cidade)
    except Exception as e:
        print(f"Erro inesperado ao obter coordenadas para '{cidade}': {e}")
        return None

# --- Coleta e Processamento dos Dados ---
print("\nBuscando cotações no banco de dados...")
# Pegamos todas as cotações que tenham valor, peso, volumes e valor da mercadoria preenchidos
cotacoes = Cotacao.objects.filter(
    valor_proposta__isnull=False,
    peso__isnull=False,
    volumes__isnull=False,
    valor_mercadoria__isnull=False
).exclude(valor_proposta=0)

print(f"Encontradas {cotacoes.count()} cotações completas e com preço definido.")

lista_de_dados = []
total = cotacoes.count()
for i, c in enumerate(cotacoes):
    print(f"Processando Cotação {i+1}/{total} (ID: {c.id})...")
    origem_coords = get_coords(c.origem)
    destino_coords = get_coords(c.destino)
    
    if origem_coords and destino_coords:
        distancia = round(geodesic(origem_coords, destino_coords).km)
        
        lista_de_dados.append({
            'distancia_km': distancia,
            'peso': float(c.peso),
            'volumes': int(c.volumes),
            'valor_mercadoria': float(c.valor_mercadoria),
            'valor_proposta': float(c.valor_proposta)
        })
    else:
        print(f"  -> Cotação {c.id} ignorada. Coordenadas não encontradas.")

# --- Criação do DataFrame Final ---
if not lista_de_dados:
    print("\nERRO: Nenhum dado válido foi processado. Verifique se suas cotações têm todos os campos preenchidos.")
    exit()

df = pd.DataFrame(lista_de_dados)
print(f"\nForam processados {len(df)} registros válidos.")
df.dropna(inplace=True)
print(f"Restaram {len(df)} registros após a limpeza final.")

print("\nAmostra do dataset final:")
print(df.head())

# Salva o arquivo final na pasta do microsserviço da API
caminho_api = '/web/modelo_api/dados_para_treino.csv'
df.to_csv(caminho_api, index=False)
print(f"\n✅ Arquivo 'dados_para_treino.csv' criado com sucesso em '{caminho_api}'!")
