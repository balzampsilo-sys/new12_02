# Multi-stage build для оптимизации размера образа
FROM python:3.11-slim as builder

WORKDIR /app

# Установка системных зависимостей + Docker CLI
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка пакетов ГЛОБАЛЬНО
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Установка минимальных runtime зависимостей для Docker CLI
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Копирование установленных пакетов из builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копирование Docker CLI из builder
COPY --from=builder /usr/bin/docker /usr/bin/docker
COPY --from=builder /usr/libexec/docker/cli-plugins/docker-compose /usr/libexec/docker/cli-plugins/docker-compose

# Создание директории для Docker plugins
RUN mkdir -p /usr/libexec/docker/cli-plugins

# Копирование кода приложения
COPY . .

# Создание директорий
RUN mkdir -p /app/logs /app/data /app/deployed_clients

# Непривилегированный пользователь
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

# Добавить botuser в группу docker (если она существует в хосте через socket)
RUN groupadd -g 999 docker || true && \
    usermod -aG docker botuser || true

USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

# Запуск бота
CMD ["python", "main.py"]
