# gerar_dataset_avancado.py (Versão com memória permanente e carga incremental)

import os
import django
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time
import json
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib

print("Iniciando a geração do DATASET AVANÇADO (Modo Incremental)...")

# --- 1. SETUP DO DJANGO E CACHE ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'loja.settings') 
django.setup()
from quoteflow.models import Cotacao
print("Conexão com Django bem-sucedida!")

# ... (Todo o bloco de cache de coordenadas e a função get_coords continua igual) ...
CACHE_FILE = 'cache_coordenadas.json'
def carregar_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f: return json.load(f)
    return {}
def salvar_cache(cache):
    with open(CACHE_FILE, 'w') as f: json.dump(cache, f, indent=2)
location_cache = carregar_cache()
geolocator = Nominatim(user_agent="quoteflow_ai_trainer_v5")
def get_coords(cidade):
    if cidade in location_cache:
        return location_cache[cidade]
    try:
        print(f"  -> Buscando coordenadas para cidade NOVA: '{cidade}'...")
        location = geolocator.geocode(f"{cidade}, Brazil")
        time.sleep(1)
        coords = (location.latitude, location.longitude) if location else None
        location_cache[cidade] = coords
        return coords
    except Exception as e:
        print(f"Erro ao obter coordenadas para '{cidade}': {e}")
        return None

# --- 2. LÓGICA DE CARGA INCREMENTAL ---
caminho_api_csv = '/web/modelo_api/dados_para_treino_avancado.csv'
ultimo_id_processado = 0
df_existente = pd.DataFrame()

if os.path.exists(caminho_api_csv):
    print(f"Encontrado dataset existente em '{caminho_api_csv}'. Lendo...")
    df_existente = pd.read_csv(caminho_api_csv)
    if not df_existente.empty and 'cotacao_id' in df_existente.columns:
        ultimo_id_processado = df_existente['cotacao_id'].max()
        print(f"Última cotação processada tem o ID: {ultimo_id_processado}. Buscando novas cotações a partir deste ID.")

# --- 3. COLETA E PROCESSAMENTO DOS DADOS ---
print("\nBuscando NOVAS cotações no banco de dados...")
# Pegamos apenas cotações com ID maior que o último processado
cotacoes_novas = Cotacao.objects.filter(
    id__gt=ultimo_id_processado, # <-- A MÁGICA DA EFICIÊNCIA ESTÁ AQUI
    valor_proposta__isnull=False, peso__isnull=False,
    volumes__isnull=False, valor_mercadoria__isnull=False,
    observacao__isnull=False
).exclude(valor_proposta=0)

if not cotacoes_novas.exists():
    print("Nenhuma nova cotação para processar. O dataset está atualizado.")
    salvar_cache(location_cache) # Salva o cache caso alguma cidade nova tenha sido consultada
    exit()

print(f"Encontradas {cotacoes_novas.count()} novas cotações para processar.")

lista_de_dados_novos = []
for c in cotacoes_novas:
    # ... (o loop de processamento e engenharia de features continua o mesmo) ...
    origem_coords = get_coords(c.origem)
    destino_coords = get_coords(c.destino)
    if origem_coords and destino_coords:
        distancia = round(geodesic(origem_coords, destino_coords).km)
        lista_de_dados_novos.append({
            'cotacao_id': c.id, # <-- IMPORTANTE: Guardamos o ID original
            'distancia_km': distancia, 'peso': float(c.peso), 'volumes': int(c.volumes),
            'valor_mercadoria': float(c.valor_mercadoria), 'tipo_frete': c.tipo_frete,
            'data': c.data_recebimento, 'observacao': str(c.observacao),
            'valor_proposta': float(c.valor_proposta)
        })

df_novos = pd.DataFrame(lista_de_dados_novos)

# --- 4. ENGENHARIA DE FEATURES AVANÇADA (APENAS NOS DADOS NOVOS) ---
if not df_novos.empty:
    print(f"\nProcessando features avançadas para {len(df_novos)} novos registros...")
    # ... (a lógica de criação de features temporal, categórica, texto e interação continua a mesma) ...
    df_novos['data'] = pd.to_datetime(df_novos['data'])
    df_novos['mes'] = df_novos['data'].dt.month
    df_novos['dia_da_semana'] = df_novos['data'].dt.dayofweek
    df_novos['dia_do_ano'] = df_novos['data'].dt.dayofyear
    df_novos['semana_do_ano'] = df_novos['data'].dt.isocalendar().week.astype(int)
    df_novos = pd.get_dummies(df_novos, columns=['tipo_frete'], prefix='tipo')
    
    # Lógica de TF-IDF: carrega o vetorizador antigo ou cria um novo
    caminho_api_vectorizer = '/web/modelo_api/tfidf_vectorizer.pkl'
    if os.path.exists(caminho_api_vectorizer):
        vectorizer = joblib.load(caminho_api_vectorizer)
    else:
        vectorizer = TfidfVectorizer(max_features=100, ngram_range=(1, 2), stop_words=['de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um'])
        # Treina o vetorizador apenas na primeira vez com todos os dados históricos disponíveis
        all_text = Cotacao.objects.filter(observacao__isnull=False).values_list('observacao', flat=True)
        vectorizer.fit(all_text)

    tfidf_matrix = vectorizer.transform(df_novos['observacao'])
    df_tfidf = pd.DataFrame(tfidf_matrix.toarray(), columns=[f'txt_{name}' for name in vectorizer.get_feature_names_out()])
    df_novos = pd.concat([df_novos.reset_index(drop=True), df_tfidf], axis=1)

    df_novos['peso_x_distancia'] = df_novos['peso'] * df_novos['distancia_km']
    df_novos['valor_por_kg'] = df_novos['valor_mercadoria'] / (df_novos['peso'] + 0.01)
    
    # --- 5. JUNTA OS DADOS NOVOS COM OS ANTIGOS ---
    print("Juntando novos registros ao dataset existente...")
    df_final = pd.concat([df_existente, df_novos], ignore_index=True)
    
    # Remove colunas que não são mais necessárias para o treino
    df_final.drop(columns=['data', 'observacao'], inplace=True, errors='ignore')
    
    # Garante que não haja duplicatas pelo ID da cotação
    df_final.drop_duplicates(subset=['cotacao_id'], keep='last', inplace=True)
    
    print(f"\nDataset finalizado com {len(df_final)} registros no total.")
    
    # --- 6. SALVA TUDO ---
    # Salva o dataset combinado e o vetorizador atualizado
    df_final.to_csv(caminho_api_csv, index=False)
    joblib.dump(vectorizer, caminho_api_vectorizer)
    salvar_cache(location_cache)
    
    print(f"\n✅ Arquivo '{caminho_api_csv}' atualizado com sucesso!")
    print(f"✅ Vetorizador TF-IDF salvo/atualizado com sucesso!")
