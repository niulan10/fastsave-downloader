# 1. Usa uma versão leve do Python (Linux) para o servidor ser rápido
FROM python:3.11-slim

# 2. Instala o FFmpeg e limpa os arquivos temporários para a imagem ficar leve
# O FFmpeg é OBRIGATÓRIO para o yt-dlp baixar áudio ou converter formatos
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 3. Define a pasta de trabalho dentro do servidor
WORKDIR /app

# 4. Copia os arquivos do seu computador para o servidor
COPY . .

# 5. Instala as bibliotecas do Python (Flask, yt-dlp, gunicorn, etc)
# --no-cache-dir evita salvar cópias de instalação, economizando espaço
RUN pip install --no-cache-dir -r requirements.txt

# 6. Cria a pasta 'downloads' para garantir que ela exista antes do app rodar
# Isso evita erros de "Folder not found" quando o primeiro usuário tentar baixar
RUN mkdir -p downloads

# 7. Comando Mestre que inicia o site em modo Produção
# --bind 0.0.0.0:8000: Libera o acesso para a internet externa
# --timeout 120: Dá 2 minutos para downloads pesados antes de cancelar (importante!)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app", "--timeout", "120"]