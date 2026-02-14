# 🚀 ПОЛНОЕ РУКОВОДСТВО ПО ЗАПУСКУ

## 🎯 Обзор новой архитектуры

Этот проект теперь поддерживает:

### ✅ **PostgreSQL Multi-tenant**
- Одна БД для всех клиентов
- Изоляция через PostgreSQL схемы (`client_001`, `client_002`...)
- Connection pooling для производительности
- Поддержка **1000+ клиентов** на одном сервере

### ✅ **Redis Key Prefix Isolation**
- Все клиенты используют Redis DB 0
- Изоляция через префиксы ключей (`client_001:`, `client_002:`...)
- **Неограниченное** количество клиентов (вместо 16)
- Лучшая производительность

### ✅ **YooKassa Webhook**
- Автоматическая обработка платежей
- Проверка подписи (безопасность)
- Интеграция с Master Bot API
- Мгновенные уведомления пользователям

---

## 💻 Требования

### Минимальные:
- **Python:** 3.11+
- **Docker & Docker Compose:** Последние версии
- **RAM:** 2GB (для разработки)

### Recommended (Production):
- **CPU:** 4 ядра
- **RAM:** 16GB
- **SSD:** 50GB+
- **ОС:** Ubuntu 22.04 LTS

---

## ⚡ Быстрый старт (Development)

### Шаг 1: Клонирование репозитория

```bash
git clone https://github.com/balzampsilo-sys/new12_02.git
cd new12_02
```

### Шаг 2: Создать .env

```bash
cp .env.example .env
nano .env
```

**Обязательно указать:**

```bash
# Telegram Bot
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz  # От @BotFather
ADMIN_IDS=123456789  # Ваш Telegram ID от @userinfobot

# PostgreSQL (multi-tenant)
DB_TYPE=postgresql
DATABASE_URL=postgresql://booking_user:SecurePass2026!@postgres:5432/booking_saas
PG_SCHEMA=client_001  # Уникальный для каждого клиента

# Redis (key prefix isolation)
REDIS_ENABLED=True
REDIS_HOST=redis-shared
REDIS_DB=0  # Все клиенты используют DB 0
CLIENT_ID=client_001
REDIS_KEY_PREFIX=client_001:

# Business
COMPANY_NAME="Салон красоты"
SERVICE_LOCATION="Москва, ул. Примерная, 1"
```

### Шаг 3: Запустить Docker Compose

```bash
# Запустить PostgreSQL + Redis
make setup

# Или вручную:
docker-compose up -d postgres redis-shared

# Проверить статус
docker-compose ps
```

### Шаг 4: Инициализировать БД

```bash
# Подключиться к PostgreSQL
make psql

# Внутри psql:
CREATE DATABASE booking_saas;
\c booking_saas

# Создать схему для первого клиента
CREATE SCHEMA IF NOT EXISTS client_001;
SET search_path TO client_001;

# Применить миграции
\i database/migrations/postgres/01_init_schema.sql
\i database/migrations/postgres/02_seed_data.sql

\q
```

### Шаг 5: Запустить бота

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить
python3 main.py
```

**Готово!** Откройте своего бота в Telegram и нажмите `/start`

---

## 🔧 Добавление новых клиентов

### Вариант 1: Вручную

```bash
# 1. Создать схему в PostgreSQL
make psql

CREATE SCHEMA IF NOT EXISTS client_002;
SET search_path TO client_002;
\i database/migrations/postgres/01_init_schema.sql
\i database/migrations/postgres/02_seed_data.sql
\q

# 2. Создать .env для нового клиента
cp .env .env.client_002
nano .env.client_002

# Изменить:
BOT_TOKEN=...  # Новый токен от @BotFather
ADMIN_IDS=...  # Telegram ID клиента
PG_SCHEMA=client_002  # ✅ Важно!
CLIENT_ID=client_002
REDIS_KEY_PREFIX=client_002:
COMPANY_NAME="Новый салон"

# 3. Запустить бота
python3 main.py --env .env.client_002
```

### Вариант 2: Через Master Bot (рекомендуется)

```bash
# Запустить Master Bot
cd master_bot
python3 master_bot.py

# Использовать Telegram интерфейс для создания клиентов
```

---

## 🔐 Настройка YooKassa Webhook

### Шаг 1: Получить ключи YooKassa

1. Зарегистрируйтесь на [yookassa.ru](https://yookassa.ru)
2. Получите:
   - `shopId` (Идентификатор магазина)
   - `secretKey` (Секретный ключ)

### Шаг 2: Настроить sales_bot/.env

```bash
cd sales_bot
cp .env.example .env
nano .env
```

```bash
# YooKassa
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Sales Bot
SALES_BOT_TOKEN=your_sales_bot_token

# Master Bot API
MASTER_BOT_API_URL=http://localhost:8000
MASTER_API_TOKEN=super_secret_token_123456

# Webhook
WEBHOOK_PORT=8001
WEBHOOK_URL=https://yourdomain.com  # Ваш домен

SUPPORT_USERNAME=YourSupport
```

### Шаг 3: Запустить Webhook сервер

#### Development (через ngrok)

```bash
# Терминал 1: Запустить webhook
cd sales_bot
python3 yookassa_webhook.py

# Терминал 2: Запустить ngrok
./ngrok http 8001

# Скопировать URL: https://abc123.ngrok.io
```

### Шаг 4: Зарегистрировать webhook в YooKassa

```bash
curl -X POST https://api.yookassa.ru/v3/webhooks \
  -u SHOP_ID:SECRET_KEY \
  -H 'Content-Type: application/json' \
  -H 'Idempotence-Key: '$(uuidgen) \
  -d '{
    "event": "payment.succeeded",
    "url": "https://abc123.ngrok.io/webhook/yookassa"
  }'
```

#### Production (systemd)

```bash
# Создать systemd service
sudo nano /etc/systemd/system/yookassa-webhook.service
```

```ini
[Unit]
Description=YooKassa Webhook Server
After=network.target

[Service]
Type=simple
User=booking
WorkingDirectory=/home/booking/new12_02/sales_bot
Environment="PATH=/home/booking/venv/bin"
ExecStart=/home/booking/venv/bin/python3 yookassa_webhook.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable yookassa-webhook
sudo systemctl start yookassa-webhook
sudo systemctl status yookassa-webhook
```

---

## 📊 Мониторинг

### Проверка статуса

```bash
# Docker сервисы
docker-compose ps

# Логи бота
make logs

# Логи PostgreSQL
make logs-postgres

# Логи webhook
tail -f sales_bot/yookassa_webhook.log
```

### PostgreSQL статистика

```sql
-- Подключиться
make psql

-- Список всех схем (клиентов)
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name LIKE 'client_%';

-- Количество записей по клиентам
SELECT 
    schemaname,
    COUNT(*) as bookings_count
FROM pg_tables t
JOIN client_001.bookings b ON true
WHERE schemaname LIKE 'client_%'
GROUP BY schemaname;

-- Размер БД
SELECT 
    pg_size_pretty(pg_database_size('booking_saas')) as total_size;
```

### Redis статистика

```bash
# Подключиться
make redis-cli

# Посмотреть все ключи клиента
KEYS client_001:*

# Количество ключей по клиентам
KEYS client_*:* | wc -l

# Память
INFO memory
```

---

## 🔄 Резервное копирование

### Автоматическое

```bash
# Встроенный BackupService создает бэкапы каждые 24 часа
# Бэкапы: ./backups/backup_YYYYMMDD_HHMMSS.sql

ls -lh backups/
```

### Ручное

```bash
# Создать бэкап
make db-backup

# Или напрямую
docker-compose exec postgres pg_dump \
  -U booking_user \
  -d booking_saas \
  -F c \
  -f /backups/manual_backup_$(date +%Y%m%d).dump
```

### Восстановление

```bash
# Интерактивное
make db-restore

# Или напрямую
cat backups/backup_20260214.sql | \
  docker-compose exec -T postgres psql -U booking_user -d booking_saas
```

---

## 🛡️ Troubleshooting

### Проблема: "Connection refused" (PostgreSQL)

```bash
# Проверить
docker-compose ps postgres
make logs-postgres

# Перезапустить
make restart
```

### Проблема: "Schema does not exist"

```bash
# Создать схему
make psql
CREATE SCHEMA IF NOT EXISTS client_XXX;
SET search_path TO client_XXX;
\i database/migrations/postgres/01_init_schema.sql
```

### Проблема: Redis ключи перекрываются

```bash
# Проверить CLIENT_ID и REDIS_KEY_PREFIX в .env
grep -E "CLIENT_ID|REDIS_KEY_PREFIX" .env

# Убедитесь что они уникальные для каждого клиента
```

### Проблема: Webhook не получает уведомления

```bash
# 1. Проверить логи
tail -f sales_bot/yookassa_webhook.log

# 2. Проверить health
curl http://localhost:8001/health

# 3. Проверить регистрацию webhook в YooKassa
curl -X GET https://api.yookassa.ru/v3/webhooks \
  -u SHOP_ID:SECRET_KEY
```

---

## 📄 Документация

- [README_POSTGRES.md](README_POSTGRES.md) - PostgreSQL подробнее
- [middlewares/redis_storage_with_prefix.py](middlewares/redis_storage_with_prefix.py) - Redis key prefix
- [sales_bot/yookassa_webhook.py](sales_bot/yookassa_webhook.py) - YooKassa webhook

---

## 👥 Поддержка

Если возникли вопросы:

1. Проверьте логи: `make logs`
2. Проверьте БД: `make psql`
3. Создайте Issue в [GitHub](https://github.com/balzampsilo-sys/new12_02/issues)

---

**Версия:** 2.0.0 (PostgreSQL + Redis Key Prefix + YooKassa)  
**Дата:** 2026-02-14
