#!/bin/bash

# Script para re-treinamento diário do modelo de IA (versão corrigida)

echo "======================================================"
echo "Iniciando tarefa de re-treinamento da IA em $(date)"
echo "======================================================"

# --- Etapa 1: Gerar o dataset atualizado (no ambiente Django) ---
echo "\n[ETAPA 1/3] Gerando dataset a partir do banco de dados do QuoteFlow..."

# Muda para o diretório do projeto Django
cd /web/mudancasja/

PYTHON_DJANGO="/web/mudancasja/venv/bin/python3"
SCRIPT_GERADOR="/web/mudancasja/gerar_dataset_avancado.py"
$PYTHON_DJANGO $SCRIPT_GERADOR


# --- Etapa 2: Treinar o novo modelo (no ambiente da API) ---
echo "\n[ETAPA 2/3] Treinando o novo modelo com os dados atualizados..."

# Muda para o diretório do projeto da API
cd /web/modelo_api/

PYTHON_API="/web/modelo_api/venv/bin/python3"
SCRIPT_TREINADOR="/web/modelo_api/treinar_modelo.py"
$PYTHON_API $SCRIPT_TREINADOR


# --- Etapa 3: Reiniciar a API para carregar o novo modelo ---
# Verifica se a Etapa 2 foi bem-sucedida antes de reiniciar
if [ $? -eq 0 ]; then
    echo "\n[ETAPA 3/3] Treinamento bem-sucedido. Reiniciando o serviço da API..."
    sudo systemctl restart api_ia.service

    echo "\nVerificando status do serviço da API após reinício:"
    sleep 5 
    sudo systemctl status api_ia.service --no-pager
else
    echo "\n[ETAPA 3/3] FALHA NA ETAPA DE TREINAMENTO. A API não foi reiniciada para manter a versão estável anterior."
fi


echo "\n======================================================"
echo "Tarefa de re-treinamento da IA finalizada em $(date)"
echo "======================================================"
