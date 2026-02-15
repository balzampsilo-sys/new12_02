# 🚀 DEPLOYMENT GUIDE: Multi-Bot Architecture

Этот проект поддерживает **масштабируемую архитектуру** с полной изоляцией данных между клиентами.

**Важное ограничение:** PostgreSQL schema-per-tenant подход масштабируется до ~1000 клиентов. Для большего количества потребуется миграция на row-level tenant isolation.

---

## 🎯 АРХИТЕКТУРА

```
┌──────────────────────────────────────────────────────┐
│          MULTI-BOT ARCHITECTURE                      │
└──────────────────────────────────────────────────────┘

   Master Bot              Sales Bot             Client Bot
   (master_bot)           (sales_bot)           (client_xxx)
        │                      │                      │
        │                      │                      │
        └──────────┬───────────┘                      │
                   │                                  │
                   v                                  v
        ┌────────────────────────────────────────────────┐
        │     PostgreSQL (booking_saas)                  │
        │                                                │
        │  ┌──────────────────────────────────────────┐ │
        │  │ Schema: master_bot                       │ │
        │  │ - bookings, services, users...          │ │
        │  └──────────────────────────────────────────┘ │
        │                                                │
        │  ┌──────────────────────────────────────────┐ │
        │  │ Schema: sales_bot                        │ │
        │  │ - bookings, services, users...          │ │
        │  └──────────────────────────────────────────┘ │
        │                                                │
        │  ┌──────────────────────────────────────────┐ │
        │  │ Schema: client_xxx (auto-created)        │ │
        │  │ - bookings, services, users...          │ │
        │  └──────────────────────────────────────────┘ │
        └────────────────────────────────────────────────┘

        ┌────────────────────────────────────────────────┐
        │     Redis (FSM States)                         │
        │                                                │
        │  Keys: master_bot:user:123:state               │
        │  Keys: sales_bot:user:456:state                │
        │  Keys: client_xxx:user:789:state               │
        └────────────────────────────────────────────────┘
```

**Ключевые особенности:**
- ✅ **Полная изоляция** данных через PostgreSQL schemas
- ✅ **Масштабирование до ~1000 ботов** (PostgreSQL schema limit)
- ✅ **Автоматическое создание** schemas при запуске
- ⚠️ **Для 1000+ клиентов** требуется row-level isolation (tenant_id column)

---

## 🚀 БЫСТРЫЙ СТАРТ

### Шаг 1: Клонировать репозиторий
```bash
git clone https://github.com/balzampsilo-sys/new12_02.git
cd new12_02
```

### Шаг 2: Настроить .env
```bash
cp .env.example .env
nano .env  # или notepad .env на Windows
```

**Обязательно укажите:**
```env
# ========================================
# MASTER BOT (управление подписками)
# ========================================
BOT_TOKEN_MASTER=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS_MASTER=123456789,987654321

# ========================================
# SALES BOT (продажи через YooKassa)
# ========================================
BOT_TOKEN_SALES=0987654321:ZYXwvuTSRqponMLKjiHGFedcba
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
WEBHOOK_URL=https://yourdomain.com
SUPPORT_USERNAME=YourSupport

# ========================================
# DATABASE
# ========================================
POSTGRES_PASSWORD=YourSecurePassword123!

# ========================================
# MONITORING (Optional)
# ========================================
SENTRY_ENABLED=false
```

**⚠️ ВАЖНО о переменных окружения:**

В `.env` файле переменные называются `BOT_TOKEN_MASTER` и `BOT_TOKEN_SALES`, но в `docker-compose.yml` они передаются в контейнеры как:
- Master Bot: `MASTER_BOT_TOKEN` (для master_bot/master_bot.py)
- Sales Bot: `SALES_BOT_TOKEN` (для sales_bot/sales_bot_yookassa.py)
- Client Bots: `BOT_TOKEN` (для main.py)

Это сделано для совместимости разных entry points.

### Шаг 3: Запустить все сервисы
```bash
# Полная пересборка с нуля (рекомендуется при первом запуске)
docker-compose build --no-cache
docker-compose up -d
```

**Это запустит:**
- ✅ PostgreSQL 16 (booking_saas database)
- ✅ Redis 7 (FSM states)
- ✅ Master Bot (schema: master_bot)
- ✅ Sales Bot (schema: sales_bot)

### Шаг 4: Проверить статус
```bash
docker-compose ps

# Должны увидеть:
# NAME                  STATUS
# booking-postgres      Up (healthy)
# booking-redis         Up (healthy)
# booking-bot-master    Up
# booking-bot-sales     Up
```

### Шаг 5: Просмотреть логи
```bash
# Master Bot
docker-compose logs -f bot-master

# Должны увидеть:
# 📦 Initializing schema: master_bot
#   ✅ Schema created: master_bot
#   ✅ Created 12 tables
#   ✅ Created 16 indexes
# ✅ Bot started successfully

# Sales Bot
docker-compose logs -f bot-sales

# Должны увидеть:
# 📦 Initializing schema: sales_bot
#   ✅ Schema created: sales_bot
#   ✅ Created tables for payments, subscriptions...
# ✅ Sales Bot started with YooKassa integration
```

---

## ✅ ПРОВЕРКА ИЗОЛЯЦИИ

### Проверить PostgreSQL schemas:
```bash
docker-compose exec postgres psql -U booking_user -d booking_saas

# Проверить schemas
SELECT schema_name FROM information_schema.schemata 
WHERE schema_name LIKE '%_bot' OR schema_name LIKE 'client_%';

# Результат:
#  schema_name  
# --------------
#  master_bot
#  sales_bot
#  client_001  (если добавляли)

# Проверить таблицы master_bot
SET search_path TO master_bot;
\dt

# Должны увидеть 12 таблиц:
# - admins
# - admin_actions  (audit log)
# - bookings
# - booking_history
# - services
# - users
# - blocked_slots
# - text_templates  (i18n)
# - settings
# - ... и другие

# Проверить таблицы sales_bot
SET search_path TO sales_bot;
\dt

# Должны увидеть таблицы для платежей и подписок
```

### Проверить Redis key prefixes:
```bash
docker-compose exec redis redis-cli

# Посмотреть все ключи
KEYS *

# Должны увидеть (если пользователи взаимодействовали с ботами):
# 1) "master_bot:user:123456789:state"
# 2) "sales_bot:user:111111111:state"
# 3) "client_001:user:222222222:state"  (если есть клиентские боты)

# Полная изоляция FSM state между ботами!
```

---

## ➕ ДОБАВЛЕНИЕ НОВОГО КЛИЕНТСКОГО БОТА

### Шаг 1: Добавьте сервис в docker-compose.yml
```yaml
  # ✅ NEW CLIENT BOT
  bot-client-001:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: booking-bot-client-001
    command: python main.py  # ⚠️ Важно: main.py для клиентских ботов
    environment:
      BOT_TOKEN: ${BOT_TOKEN_CLIENT_001}  # ⚠️ Важно: BOT_TOKEN (не CLIENT_BOT_TOKEN)
      ADMIN_IDS: ${ADMIN_IDS_CLIENT_001}
      CLIENT_ID: client_001
      
      # Database
      DB_TYPE: postgresql
      DATABASE_URL: postgresql://booking_user:${POSTGRES_PASSWORD:-SecurePass2026!}@postgres:5432/booking_saas
      PG_SCHEMA: client_001  # ✅ Уникальная schema
      
      # Redis
      REDIS_ENABLED: "true"
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_DB: 0
      REDIS_KEY_PREFIX: "client_001:"  # ✅ Уникальный prefix
      
      # Business Logic
      WORK_HOURS_START: 9
      WORK_HOURS_END: 18
      MAX_BOOKINGS_PER_USER: 3
      CANCELLATION_HOURS: 24
      
      # Monitoring (optional)
      SENTRY_ENABLED: ${SENTRY_ENABLED:-false}
      SENTRY_DSN: ${SENTRY_DSN_CLIENT_001:-}
      SENTRY_ENVIRONMENT: production-client-001
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - booking-network
    volumes:
      - ./logs:/app/logs
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Шаг 2: Добавьте в .env
```env
BOT_TOKEN_CLIENT_001=your_new_bot_token
ADMIN_IDS_CLIENT_001=333333333,444444444
```

### Шаг 3: Запустите
```bash
docker-compose up -d bot-client-001

# Schema "client_001" будет создана автоматически!
# ✅ 12 таблиц
# ✅ 16 индексов
# ✅ Готово к работе

# Проверить логи
docker-compose logs -f bot-client-001

# Должны увидеть:
# 📦 Initializing schema: client_001
#   ✅ Schema created: client_001
#   ✅ Created 12 tables
# 🤖 Bot started successfully
```

---

## 🛠️ УПРАВЛЕНИЕ

### Запустить все боты
```bash
docker-compose up -d
```

### Остановить все боты
```bash
docker-compose down
```

### Перезапустить конкретный бот
```bash
docker-compose restart bot-master
docker-compose restart bot-sales
docker-compose restart bot-client-001
```

### Обновить код
```bash
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Остановить бота (временная приостановка)
```bash
# Остановить (контейнер остаётся, но не работает)
docker-compose stop bot-client-001

# Возобновить
docker-compose start bot-client-001
```

### Удалить бота полностью
```bash
# 1. Остановить и удалить контейнер
docker-compose rm -sf bot-client-001

# 2. (Опционально) Удалить schema из PostgreSQL
docker-compose exec postgres psql -U booking_user -d booking_saas -c "DROP SCHEMA IF EXISTS client_001 CASCADE;"

# 3. (Опционально) Очистить Redis keys
docker-compose exec redis redis-cli KEYS "client_001:*" | xargs docker-compose exec redis redis-cli DEL

# 4. Удалить из docker-compose.yml и .env
```

---

## 📊 МОНИТОРИНГ

### Статус контейнеров
```bash
docker-compose ps

# Показывает:
# - Статус (Up / Exited)
# - Health (healthy / unhealthy / starting)
# - Порты
```

### Ресурсы (CPU, RAM, Network)
```bash
docker stats

# Показывает real-time:
# - CPU usage %
# - Memory usage / limit
# - Network I/O
# - Disk I/O
```

### PostgreSQL коннекты
```bash
# Общее количество подключений
docker-compose exec postgres psql -U booking_user -d booking_saas -c \
  "SELECT count(*) as active_connections FROM pg_stat_activity WHERE datname='booking_saas';"

# Подключения по schema (требует права на pg_stat_activity)
docker-compose exec postgres psql -U booking_user -d booking_saas -c \
  "SELECT usename, application_name, count(*) FROM pg_stat_activity WHERE datname='booking_saas' GROUP BY usename, application_name;"
```

### Redis память
```bash
# Использование памяти
docker-compose exec redis redis-cli INFO memory | grep used_memory_human

# Количество keys по префиксу
docker-compose exec redis redis-cli --scan --pattern "master_bot:*" | wc -l
docker-compose exec redis redis-cli --scan --pattern "sales_bot:*" | wc -l
```

### Логи
```bash
# Все боты (real-time)
docker-compose logs -f

# Конкретный бот
docker-compose logs -f bot-master

# Последние 100 строк
docker-compose logs --tail=100 bot-master

# Поиск по логам (например, ошибки)
docker-compose logs bot-master | grep -i "error\|exception\|critical"

# Экспорт логов в файл
docker-compose logs --no-color bot-master > master_bot_logs_$(date +%Y%m%d).txt
```

---

## 🔒 БЕЗОПАСНОСТЬ

### Production Checklist

**1. Измените пароли**
```env
# .env
POSTGRES_PASSWORD=UseStrongPassword123!WithSymbols
REDIS_PASSWORD=AnotherSecurePassword456!
```

**2. Настройте Redis password**
```yaml
# docker-compose.yml (redis service)
command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
```

И обновите боты:
```yaml
environment:
  REDIS_PASSWORD: ${REDIS_PASSWORD}
```

**3. Не публикуйте .env**
```bash
# Уже добавлено в .gitignore
cat .gitignore | grep .env
# .env
# .env.local
# .env.production
```

**4. Закройте порты извне (firewall)**
```bash
# Ubuntu/Debian
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (если нужно)
sudo ufw allow 443/tcp   # HTTPS (если нужно)
sudo ufw deny 5432/tcp   # PostgreSQL - ЗАКРЫТЬ извне!
sudo ufw deny 6379/tcp   # Redis - ЗАКРЫТЬ извне!
sudo ufw enable
```

**5. Используйте Sentry в production**
```env
SENTRY_ENABLED=true
SENTRY_DSN=https://your_sentry_dsn@sentry.io/project_id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% trace sampling
```

**6. Настройте SSL для PostgreSQL** (для production)
```bash
# Генерация self-signed сертификата (для теста)
docker-compose exec postgres bash
cd /var/lib/postgresql/data
openssl req -new -x509 -days 365 -nodes -text -out server.crt -keyout server.key
chmod 600 server.key
chown postgres:postgres server.key server.crt

# Добавить в postgresql.conf
echo "ssl = on" >> postgresql.conf
echo "ssl_cert_file = 'server.crt'" >> postgresql.conf
echo "ssl_key_file = 'server.key'" >> postgresql.conf

# Перезапустить
exit
docker-compose restart postgres
```

**7. Rate Limiting для production**
```env
# .env (для config.py)
RATE_LIMIT_MESSAGE=2.0   # 2 секунды между сообщениями (вместо 0.5)
RATE_LIMIT_CALLBACK=1.0  # 1 секунда между callback (вместо 0.3)
```

---

## 💾 БЭКАПЫ

### SQLite (legacy mode)

Автоматические бэкапы **уже настроены** в коде (только для SQLite mode):
```python
# config.py
BACKUP_ENABLED = True  # По умолчанию
BACKUP_INTERVAL_HOURS = 24
BACKUP_RETENTION_DAYS = 30
```

### PostgreSQL (recommended)

**⚠️ ВАЖНО:** Автоматические PostgreSQL бэкапы **НЕ настроены по умолчанию**. Необходимо настроить вручную.

**Ручной бэкап всех schemas:**
```bash
# Полный backup всей базы
docker-compose exec postgres pg_dump -U booking_user -Fc booking_saas > backups/booking_full_$(date +%Y%m%d_%H%M%S).dump

# SQL формат (текстовый)
docker-compose exec postgres pg_dump -U booking_user booking_saas > backups/booking_full_$(date +%Y%m%d).sql
```

**Бэкап конкретной schema:**
```bash
# Только master_bot schema
docker-compose exec postgres pg_dump -U booking_user -n master_bot booking_saas > backups/master_bot_$(date +%Y%m%d).sql

# Только sales_bot schema
docker-compose exec postgres pg_dump -U booking_user -n sales_bot booking_saas > backups/sales_bot_$(date +%Y%m%d).sql
```

**Восстановление:**
```bash
# Из SQL файла
docker-compose exec -T postgres psql -U booking_user booking_saas < backups/backup.sql

# Из .dump файла (compressed)
docker-compose exec -T postgres pg_restore -U booking_user -d booking_saas backups/backup.dump

# Восстановление конкретной schema
docker-compose exec -T postgres psql -U booking_user booking_saas < backups/master_bot_backup.sql
```

**Автоматический бэкап (cron):**
```bash
# Создать директорию для бэкапов
mkdir -p /var/backups/booking_bot

# Добавить в crontab
crontab -e

# Ежедневный backup в 2:00 AM
0 2 * * * cd /path/to/new12_02 && docker-compose exec -T postgres pg_dump -U booking_user -Fc booking_saas > /var/backups/booking_bot/booking_$(date +\%Y\%m\%d).dump

# Очистка старых бэкапов (старше 30 дней)
0 3 * * * find /var/backups/booking_bot -name "booking_*.dump" -mtime +30 -delete

# Проверка целостности бэкапа (опционально)
0 4 * * * cd /path/to/new12_02 && docker-compose exec -T postgres pg_restore --list /var/backups/booking_bot/booking_$(date +\%Y\%m\%d).dump > /dev/null 2>&1 || echo "Backup verification FAILED" | mail -s "Backup Alert" admin@example.com
```

**Проверка целостности бэкапа:**
```bash
# Проверить .dump файл
docker-compose exec postgres pg_restore --list backups/backup.dump

# Если команда выполнилась без ошибок - backup валиден
```

---

## 🐛 TROUBLESHOOTING

### Бот не запускается

```bash
# Проверить логи
docker-compose logs bot-master

# Типичные причины:
# 1. ❌ Неверный BOT_TOKEN
#    Решение: Проверить формат 123456789:ABCdef... (минимум 30 символов после :)

# 2. ❌ PostgreSQL недоступен
#    Решение: docker-compose ps postgres  # должен быть Up (healthy)

# 3. ❌ Redis недоступен
#    Решение: docker-compose ps redis  # должен быть Up (healthy)

# 4. ❌ ModuleNotFoundError: No module named 'aiogram'
#    Решение: Пересобрать образ с --no-cache
```

### ModuleNotFoundError

**Решение:** Пересобрать образы с нуля

**Windows:**
```bash
rebuild.bat
```

**Linux/Mac:**
```bash
./rebuild.sh
```

**Или вручную:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Schema не создается

```bash
# Проверить права пользователя
docker-compose exec postgres psql -U booking_user -d booking_saas

# Выполнить:
GRANT ALL ON SCHEMA public TO booking_user;
GRANT CREATE ON DATABASE booking_saas TO booking_user;

# Проверить существующие schemas
SELECT schema_name FROM information_schema.schemata;

# Если schema создалась, но таблиц нет:
SET search_path TO master_bot;
\dt

# Если таблиц нет - проверить логи бота на ошибки миграций
docker-compose logs bot-master | grep -i "migration\|table\|error"
```

### Напоминания не отправляются

```bash
# Проверить scheduler в логах
docker-compose logs bot-master | grep -i "reminder\|scheduler"

# Должны увидеть:
# ⏰ Reminder service activated
# - 24h reminders: daily at 10:00
# - 2h reminders: every 2 hours
# - 1h reminders: every hour

# Проверить APScheduler jobs
docker-compose logs bot-master | grep "job"
```

**⚠️ Известная проблема:** 24h reminder запускается **только в 10:00 ежедневно**. Если запись создана после 10:00, напоминание может не отправиться вовремя.

**Решение:** Изменить schedule в `main.py`:
```python
# Вместо cron hour=10
scheduler.add_job(
    reminder_24h_job,
    "interval",  # Изменить с 'cron'
    hours=2,     # Каждые 2 часа
    id="reminder_24h",
    replace_existing=True,
)
```

### Connection pool exhausted

```bash
# Проверить активные подключения
docker-compose exec postgres psql -U booking_user -d booking_saas -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname='booking_saas';"

# Если близко к max_connections (default 100):
```

**Решение:** Увеличить connection pool или max_connections:

```yaml
# docker-compose.yml (postgres service)
command:
  - "postgres"
  - "-c"
  - "max_connections=200"  # Увеличить с 100
  - "-c"
  - "shared_buffers=512MB"  # Тоже увеличить
```

Или в `.env` (для ботов):
```env
DB_POOL_MAX_SIZE=50  # Вместо 10 (но учитывайте количество ботов!)
```

### Redis память заполнена

```bash
# Проверить использование памяти
docker-compose exec redis redis-cli INFO memory

# Если used_memory близко к maxmemory (256MB):
```

**Решение:** Увеличить maxmemory:
```yaml
# docker-compose.yml (redis service)
command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### Бот перезапускается постоянно

```bash
# Проверить статус
docker-compose ps

# Если статус "Restarting" - смотрим логи
docker-compose logs --tail=100 bot-master

# Типичные причины:
# 1. Crash при старте (исключение в main.py)
# 2. Health check fails (но в текущей конфигурации health check простой)
# 3. Недостаточно RAM (OOM killer)

# Проверить память
docker stats --no-stream
```

**Решение для OOM:**
```yaml
# docker-compose.yml (bot service)
deploy:
  resources:
    limits:
      memory: 512M  # Увеличить с default
    reservations:
      memory: 256M
```

---

## 📈 МАСШТАБИРОВАНИЕ

### Когда пора масштабировать?

**Признаки:**
- Более 50-100 ботов на одном сервере
- CPU usage постоянно > 70%
- Connection pool exhausted регулярно
- Response time > 2 секунд

### Варианты масштабирования:

**1. Вертикальное (увеличение ресурсов сервера)**
- ✅ Простота
- ✅ Не требует изменений кода
- ❌ Есть предел (~1000 ботов из-за schema limit)

**2. Horizontal scaling (несколько серверов)**
- ✅ Неограниченное масштабирование
- ❌ Требует:
  - Load balancer (nginx/HAProxy)
  - Shared PostgreSQL (отдельный сервер)
  - Shared Redis (отдельный сервер)
  - Sticky sessions или shared state

**3. Миграция на row-level tenant isolation**
- ✅ Снимает лимит 1000 schemas
- ✅ Лучшая производительность для тысяч клиентов
- ❌ Требует:
  - Рефакторинг всех SQL queries (добавить WHERE tenant_id=X)
  - Миграция данных из schemas в tenant_id column
  - Изменение connection pool strategy

### Рекомендуемая архитектура для 1000+ клиентов:

```
┌─────────────┐
│Load Balancer│ (nginx)
└──────┬──────┘
       |
   ┌───┴───┬───────┬───────┐
   │       │       │       │
┌──▼──┐ ┌──▼──┐ ┌──▼──┐ ┌──▼──┐
│Bot  │ │Bot  │ │Bot  │ │Bot  │  (Docker Swarm / K8s)
│Node1│ │Node2│ │Node3│ │Node4│
└──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘
   │       │       │       │
   └───┬───┴───┬───┴───┬───┘
       │       │       │
   ┌───▼───────▼───────▼───┐
   │ PostgreSQL Cluster    │ (Primary + Replicas)
   │ (row-level isolation) │
   └───────────────────────┘
       │
   ┌───▼───┐
   │ Redis │ (Cluster mode)
   │Cluster│
   └───────┘
```

---

## ✅ РЕЗЮМЕ

✅ **Master Bot и Sales Bot запускаются автоматически**  
✅ **Полная изоляция данных через schemas + key prefixes**  
✅ **Масштабирование до ~1000 ботов**  
✅ **Production-ready с правильной настройкой**  
⚠️ **Для 1000+ клиентов требуется архитектурная миграция**  

🚀 **Проект готов к развертыванию!**

---

## 📚 Дополнительные ресурсы

- [README.md](./README.md) - Общий обзор проекта
- [API.md](./API.md) - REST API документация
- [FEATURES.md](./FEATURES.md) - Детальное описание функций
- [CHANGELOG.md](./CHANGELOG.md) - История изменений
