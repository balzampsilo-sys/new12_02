# Multi-stage build для оптимизации размера образа
FROM python:3.11-slim as builder

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка пакетов ГЛОБАЛЬНО
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Копирование установленных пакетов из builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копирование кода приложения
COPY . .

# Создание директорий
RUN mkdir -p /app/logs /app/data

# Непривилегированный пользователь
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

# Запуск бота
CMD ["python", "main.py"]
