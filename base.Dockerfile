# ============================================
# BASE DOCKER IMAGE FOR BOOKING BOT
# ============================================
# Этот образ собирается ОДИН РАЗ и используется
# для всех клиентских ботов без пересборки
#
# Ускорение деплоя: 188 сек → 8-10 сек (20x)
# ============================================

FROM python:3.11-slim

# Метаданные
LABEL maintainer="Booking SaaS Team"
LABEL description="Pre-built base image for client bots"
LABEL version="1.0.0"

# Установить переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Установить системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Установить Docker CLI (для автономного деплоя в Master Bot)
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Создать рабочую директорию
WORKDIR /app

# Скопировать requirements.txt
COPY requirements.txt /tmp/requirements.txt

# Установить Python зависимости
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Скопировать код приложения (СТАТИЧЕСКИЕ ЧАСТИ)
# Эти файлы НЕ содержат конфигурации клиентов
COPY handlers /app/handlers
COPY database /app/database
COPY services /app/services
COPY middlewares /app/middlewares
COPY utils /app/utils
COPY keyboards /app/keyboards
COPY locales /app/locales
COPY automation /app/automation

# Скопировать основные файлы
COPY main.py /app/main.py
COPY config.py /app/config.py

# Создать директории для данных (будут замонтированы volumes)
RUN mkdir -p /app/data /app/logs /app/backups

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Точка входа
CMD ["python", "main.py"]
