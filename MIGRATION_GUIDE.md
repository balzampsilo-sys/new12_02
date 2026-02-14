# 🚀 MIGRATION GUIDE: PostgreSQL + Redis Key Prefix + YooKassa

**Дата:** 14 февраля 2026  
**Цель:** Масштабирование с 16 до 1000+ клиентов

---

## 📊 ПРОБЛЕМЫ И РЕШЕНИЯ

### Проблема #1: SQLite → PostgreSQL
- **Было:** SQLite файлы для каждого клиента
- **Стало:** PostgreSQL с изоляцией через schemas
- **Результат:** 1000+ клиентов, connection pooling, репликация

### Проблема #2: Redis DB 0-15 → Key Prefix
- **Было:** Лимит 16 клиентов (REDIS_DB 0-15)
- **Стало:** Неограниченное количество через префиксы ключей
- **Результат:** 1000+ клиентов на одном Redis DB 0

### Проблема #3: YooKassa Polling → Webhook
- **Было:** Пользователь вручную проверяет оплату
- **Стало:** Автоматический webhook при оплате
- **Результат:** Мгновенное создание бота

---

## 📋 PLAN МИГРАЦИИ

### ШАГ 1: PostgreSQL Setup (30 мин)
### ШАГ 2: Миграция данных SQLite → PostgreSQL (1 час)
### ШАГ 3: Redis Key Prefix (20 мин)
### ШАГ 4: YooKassa Webhook (40 мин)
### ШАГ 5: Тестирование (30 мин)

**Общее время:** ~3 часа

---

## 🐘 ШАГ 1: PostgreSQL Setup

### 1.1 Запустить PostgreSQL

```bash
# Запустить PostgreSQL контейнер
docker-compose -f docker-compose.postgres.yml up -d

# Проверить
docker ps | grep postgres
```

### 1.2 Создать базу данных

```bash
docker-compose exec postgres psql -U postgres << 'EOF'
-- Создать БД
CREATE DATABASE booking_saas;

-- Создать пользователя
CREATE USER booking_user WITH PASSWORD 'SecurePass2026!';

-- Выдать права
GRANT ALL PRIVILEGES ON DATABASE booking_saas TO booking_user;

-- Подключиться к БД
\c booking_saas

-- Выдать права на схему public
GRANT ALL ON SCHEMA public TO booking_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO booking_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO booking_user;

\q
EOF
```

### 1.3 Проверить подключение

```bash
# Проверить подключение
docker-compose exec postgres psql -U booking_user -d booking_saas -c "\dt"
```

---

## 📦 ШАГ 2: Миграция данных

### 2.1 Создать скрипт миграции

Файл уже создан: `scripts/migrate_to_postgres.py`

### 2.2 Установить зависимости

```bash
pip install asyncpg aiosqlite
```

### 2.3 Запустить миграцию

```bash
python3 scripts/migrate_to_postgres.py

# Вывод:
# ✅ Migrated client_001: 45 bookings, 5 services, 12 users
# ✅ Migrated client_002: 23 bookings, 3 services, 8 users
# ...
```

### 2.4 Проверить данные

```bash
docker-compose exec postgres psql -U booking_user -d booking_saas << 'EOF'
-- Список схем
SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'client_%';

-- Данные клиента 001
SET search_path TO client_001;
SELECT COUNT(*) FROM bookings;
SELECT COUNT(*) FROM services;
SELECT COUNT(*) FROM users;

\q
EOF
```

---

## 🔑 ШАГ 3: Redis Key Prefix

### 3.1 Создать middleware

Файл уже создан: `middlewares/redis_storage_with_prefix.py`

### 3.2 Обновить main.py

Добавить в начало файла:

```python
from middlewares.redis_storage_with_prefix import PrefixedRedisStorage

# Получить CLIENT_ID из .env
CLIENT_ID = os.getenv("CLIENT_ID", "default")
REDIS_KEY_PREFIX = f"{CLIENT_ID}:"

# Создать storage с префиксом
if REDIS_ENABLED:
    redis_client = Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,  # ✅ Все клиенты используют DB 0
        password=REDIS_PASSWORD
    )
    
    storage = PrefixedRedisStorage(
        redis=redis_client,
        key_prefix=REDIS_KEY_PREFIX  # ✅ Изоляция
    )
else:
    storage = MemoryStorage()

dp = Dispatcher(storage=storage)
```

### 3.3 Обновить .env всех клиентов

```bash
for client_dir in clients/*/; do
    client_id=$(basename "$client_dir")
    
    # Добавить CLIENT_ID
    echo "" >> "$client_dir/.env"
    echo "# Client Isolation" >> "$client_dir/.env"
    echo "CLIENT_ID=$client_id" >> "$client_dir/.env"
    echo "REDIS_KEY_PREFIX=${client_id}:" >> "$client_dir/.env"
    
    # Обновить REDIS_DB на 0
    sed -i 's/REDIS_DB=.*/REDIS_DB=0/' "$client_dir/.env"
    
    echo "✅ Updated $client_id"
done
```

### 3.4 Обновить config.py

Добавить:

```python
# Client isolation (новое)
CLIENT_ID = os.getenv("CLIENT_ID", "default")
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "")
```

### 3.5 Перезапустить клиентов

```bash
for client_dir in clients/*/; do
    cd "$client_dir"
    docker-compose restart
    cd ../..
done
```

---

## 💳 ШАГ 4: YooKassa Webhook

### 4.1 Создать webhook сервер

Файл уже создан: `sales_bot/yookassa_webhook.py`

### 4.2 Установить зависимости

```bash
cd sales_bot
pip install fastapi uvicorn yookassa
```

### 4.3 Настроить .env

```bash
cat >> sales_bot/.env << 'EOF'

# YooKassa
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Webhook
WEBHOOK_URL=https://yourdomain.com

# Master Bot API
MASTER_BOT_API_URL=http://localhost:8000
MASTER_API_TOKEN=super_secret_token_123456
EOF
```

### 4.4 Запустить webhook (development)

```bash
python3 yookassa_webhook.py

# Вывод:
# INFO:     Started server process
# INFO:     Uvicorn running on http://0.0.0.0:8001
```

### 4.5 Настроить ngrok (для тестирования)

```bash
# Установить ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar -xvzf ngrok-*.tgz

# Запустить туннель
./ngrok http 8001

# Скопировать URL: https://abc123.ngrok-free.app
```

### 4.6 Зарегистрировать webhook в YooKassa

```bash
curl -X POST https://api.yookassa.ru/v3/webhooks \
  -u YOUR_SHOP_ID:YOUR_SECRET_KEY \
  -H 'Content-Type: application/json' \
  -H 'Idempotence-Key: '$(uuidgen) \
  -d '{
    "event": "payment.succeeded",
    "url": "https://YOUR_NGROK_URL/webhook/yookassa"
  }'

# Ответ:
# {
#   "id": "wh_xxx",
#   "event": "payment.succeeded",
#   "url": "https://YOUR_NGROK_URL/webhook/yookassa"
# }
```

### 4.7 Production: Systemd service

```bash
sudo tee /etc/systemd/system/sales_webhook.service > /dev/null << 'EOF'
[Unit]
Description=Sales Bot YooKassa Webhook
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
EOF

sudo systemctl daemon-reload
sudo systemctl enable sales_webhook
sudo systemctl start sales_webhook
sudo systemctl status sales_webhook
```

---

## ✅ ШАГ 5: Тестирование

### 5.1 Тест PostgreSQL

```bash
# Создать тестовую запись
docker-compose exec postgres psql -U booking_user -d booking_saas << 'EOF'
SET search_path TO client_001;

INSERT INTO bookings (user_id, date, time, service_id, status)
VALUES (123456789, '2026-02-20', '14:00', 1, 'active');

SELECT * FROM bookings ORDER BY id DESC LIMIT 1;

\q
EOF
```

### 5.2 Тест Redis Key Prefix

```bash
# Проверить ключи в Redis
docker-compose exec redis-shared redis-cli

# Команды в redis-cli:
KEYS client_001:*
KEYS client_002:*
exit
```

### 5.3 Тест YooKassa Webhook

```bash
# Отправить тестовый webhook
curl -X POST http://localhost:8001/webhook/yookassa \
  -H 'Content-Type: application/json' \
  -H 'X-Yookassa-Signature: test' \
  -d '{
    "event": "payment.succeeded",
    "object": {
      "id": "test_payment_123",
      "amount": {
        "value": "299.00"
      },
      "metadata": {
        "user_id": "123456789",
        "company_name": "Test Company",
        "plan": "1m",
        "days": "30"
      }
    }
  }'

# Проверить логи
tail -f sales_bot/logs/webhook.log
```

---

## 📊 РЕЗУЛЬТАТЫ

### До миграции:
- ❌ Лимит: 16 клиентов (Redis DB 0-15)
- ❌ SQLite файлы для каждого клиента
- ❌ Ручная проверка оплаты

### После миграции:
- ✅ Лимит: 1000+ клиентов
- ✅ PostgreSQL с изоляцией через schemas
- ✅ Redis Key Prefix (DB 0 для всех)
- ✅ Автоматический webhook YooKassa

---

## 🔧 TROUBLESHOOTING

### PostgreSQL: Connection refused

```bash
# Проверить контейнер
docker ps | grep postgres

# Проверить логи
docker-compose logs postgres

# Перезапустить
docker-compose restart postgres
```

### Redis: Keys not isolated

```bash
# Проверить CLIENT_ID в .env
cat clients/client_001/.env | grep CLIENT_ID

# Проверить ключи
docker-compose exec redis-shared redis-cli KEYS "*"
```

### YooKassa: Webhook not working

```bash
# Проверить webhook сервер
curl http://localhost:8001/health

# Проверить ngrok
curl https://YOUR_NGROK_URL/health

# Проверить логи
tail -f sales_bot/logs/webhook.log
```

---

## 📚 СЛЕДУЮЩИЕ ШАГИ

1. ✅ Обновить документацию README.md
2. ✅ Добавить мониторинг (Prometheus)
3. ✅ Настроить автоматические бэкапы PostgreSQL
4. ✅ Настроить репликацию PostgreSQL (Master-Slave)
5. ✅ Добавить rate limiting для webhook

---

**Готово!** Система готова к масштабированию до 1000+ клиентов 🚀
