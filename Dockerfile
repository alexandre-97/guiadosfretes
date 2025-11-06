# Arquivo: /web/mudancasja/Dockerfile

# 1. Base: Use uma imagem oficial do Python 3.12
FROM python:3.12-slim-bookworm

# 2. Variáveis de Ambiente:
ENV PYTHONDONTWRITEBYTECODE 1  # Impede o Python de criar arquivos .pyc
ENV PYTHONUNBUFFERED 1         # Garante que os logs saiam direto, sem buffer

# 3. Diretório de Trabalho: Crie e defina o diretório de trabalho dentro do container
WORKDIR /app

# 4. Instale Dependências do Sistema (se houver, ex: para converter DOCX para PDF)
# Você pode precisar de 'libreoffice' ou 'unoconv' aqui se fizer conversão de DOCX
# Por enquanto, vamos manter simples.

# 5. Instale Dependências do Python
# Copie SÓ o requirements.txt primeiro para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copie o Código do Aplicativo
# Copia todo o resto do seu projeto para dentro do container
COPY . .

# 7. Crie o usuário 'appuser'
# Rodar como 'root' em containers não é seguro.
# O usuário 'www-data' (ID 33) já é usado pelo Nginx, então vamos usá-lo.
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
# 8. Exponha a Porta
# Gunicorn rodará na porta 8000 (apenas dentro da rede do Docker)
EXPOSE 8000

# 9. Comando de Execução (baseado no seu .service)
# O Gunicorn agora se liga a uma porta TCP, não a um socket.
CMD ["gunicorn", "loja.wsgi:application", "--workers", "5", "--bind", "0.0.0.0:8000", "--timeout", "90"]
