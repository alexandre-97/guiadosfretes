# Arquivo: /web/mudancasja/Dockerfile

# 1. Base: Use uma imagem oficial do Python 3.12
FROM python:3.12-slim-bookworm

# 2. Variáveis de Ambiente:
ENV PYTHONDONTWRITEBYTECODE 1  # Impede o Python de criar arquivos .pyc
ENV PYTHONUNBUFFERED 1         # Garante que os logs saiam direto, sem buffer

# 3. Diretório de Trabalho
WORKDIR /app

# 4. Crie o usuário 'www-data' (ID 33) antes de instalar pacotes (melhor prática)
RUN if ! getent group www-data; then \
        groupadd -g 33 www-data; \
    else \
        groupmod -g 33 www-data; \
    fi && \
    if ! getent passwd www-data; then \
        useradd -u 33 -g 33 -d /app -s /bin/bash www-data; \
    else \
        usermod -u 33 -g 33 www-data; \
    fi

# 5. Instale Dependências do Sistema (LibreOffice para conversão DOCX para PDF)
# Usamos pacotes 'core' e 'headless' para reduzir o tamanho e o tempo de build.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-core \
    unoconv \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# 6. Instale Dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copie o Código do Aplicativo
COPY . .

# 8. Defina o usuário de execução para segurança
USER www-data

# 9. Exponha a Porta
EXPOSE 8000

# 10. Comando de Execução
CMD ["gunicorn", "loja.wsgi:application", "--workers", "5", "--bind", "0.0.0.0:8000", "--timeout", "90"]
