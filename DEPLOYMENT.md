# 🚀 DEPLOYMENT GUIDE: Multi-Bot Architecture

Этот проект поддерживает **неограниченное количество ботов** с полной изоляцией данных.

---

## 🎯 АРХИТЕКТУРА

```
┌──────────────────────────────────────────────────────┐
│          MULTI-BOT ARCHITECTURE                      │
└──────────────────────────────────────────────────────┘

   Master Bot              Sales Bot             Future Bot
   (master_bot)           (sales_bot)           (new_bot)
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
        │  │ Schema: new_bot (future)                 │ │
        │  │ - bookings, services, users...          │ │
        │  └──────────────────────────────────────────┘ │
        └────────────────────────────────────────────────┘

        ┌────────────────────────────────────────────────┐
        │     Redis (FSM States)                         │
        │                                                │
        │  Keys: master_bot:user:123:state               │
        │  Keys: sales_bot:user:456:state                │
        │  Keys: new_bot:user:789:state (future)         │
        └────────────────────────────────────────────────┘
```

**Ключевые особенности:**
- ✅ **Полная изоляция** данных через PostgreSQL schemas
- ✅ **Неограниченное количество ботов** (не 16 DB, а key prefixes)
- ✅ **Автоматическое создание** schemas при запуске

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
nano .env
```

**Обязательно укажите:**
```env
# Master Bot
BOT_TOKEN_MASTER=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS_MASTER=123456789,987654321

# Sales Bot
BOT_TOKEN_SALES=0987654321:ZYXwvuTSRqponMLKjiHGFedcba
ADMIN_IDS_SALES=111111111,222222222

# Database
POSTGRES_PASSWORD=YourSecurePassword123!
```

### Шаг 3: Запустить все сервисы
```bash
docker-compose up -d
```

**Это запустит:**
- ✅ PostgreSQL (booking_saas)
- ✅ Redis (FSM states)
- ✅ Master Bot (master_bot schema)
- ✅ Sales Bot (sales_bot schema)

### Шаг 4: Проверить статус
```bash
docker-compose ps

# Должны увидеть:
# booking-postgres    Up (healthy)
# booking-redis       Up (healthy)
# booking-bot-master  Up
# booking-bot-sales   Up
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
#   ✅ Created 12 tables
#   ✅ Created 16 indexes
# ✅ Bot started successfully
```

---

## ✅ ПРОВЕРКА ИЗОЛЯЦИИ

### Проверить PostgreSQL schemas:
```bash
docker-compose exec postgres psql -U booking_user -d booking_saas

# Проверить schemas
SELECT schema_name FROM information_schema.schemata 
WHERE schema_name LIKE '%_bot';

# Результат:
#  schema_name  
# --------------
#  master_bot
#  sales_bot

# Проверить таблицы master_bot
SET search_path TO master_bot;
\dt

# Должны увидеть 12 таблиц

# Проверить таблицы sales_bot
SET search_path TO sales_bot;
\dt

# Должны увидеть 12 таблиц
```

### Проверить Redis key prefixes:
```bash
docker-compose exec redis redis-cli

# Посмотреть все ключи
KEYS *

# Должны увидеть:
# 1) "master_bot:user:123456789:state"
# 2) "sales_bot:user:111111111:state"

# Полная изоляция!
```

---

## ➕ ДОБАВЛЕНИЕ НОВОГО БОТА

### Шаг 1: Добавьте сервис в docker-compose.yml
```yaml
  # ✅ NEW BOT
  bot-newbot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: booking-bot-newbot
    environment:
      BOT_TOKEN: ${BOT_TOKEN_NEWBOT}
      ADMIN_IDS: ${ADMIN_IDS_NEWBOT}
      CLIENT_ID: newbot
      DB_TYPE: postgresql
      DATABASE_URL: postgresql://booking_user:${POSTGRES_PASSWORD}@postgres:5432/booking_saas
      PG_SCHEMA: newbot  # ✅ Уникальная schema
      REDIS_ENABLED: "true"
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_DB: 0
      REDIS_KEY_PREFIX: "newbot:"  # ✅ Уникальный prefix
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - booking-network
```

### Шаг 2: Добавьте в .env
```env
BOT_TOKEN_NEWBOT=your_new_bot_token
ADMIN_IDS_NEWBOT=333333333,444444444
```

### Шаг 3: Запустите
```bash
docker-compose up -d bot-newbot

# Schema "newbot" будет создана автоматически!
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
```

### Просмотр логов
```bash
# Все боты
docker-compose logs -f

# Конкретный бот
docker-compose logs -f bot-master
```

### Обновить код
```bash
git pull
docker-compose build
docker-compose up -d
```

---

## 📊 МОНИТОРИНГ

### Статус контейнеров
```bash
docker-compose ps
```

### Ресурсы
```bash
docker stats
```

### PostgreSQL коннекты
```bash
docker-compose exec postgres psql -U booking_user -d booking_saas -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname='booking_saas';"
```

### Redis память
```bash
docker-compose exec redis redis-cli INFO memory | grep used_memory_human
```

---

## 🔒 БЕЗОПАСНОСТЬ

### Рекомендации:

1. **Измените пароль PostgreSQL**
   ```env
   POSTGRES_PASSWORD=YourVerySecurePassword123!
   ```

2. **Не публикуйте .env**
   ```bash
   # Уже добавлено в .gitignore
   .env
   ```

3. **Используйте Docker secrets** (для production)
   - Docker Swarm secrets
   - Kubernetes secrets

4. **Настройте firewall**
   ```bash
   # Закрыть порты 5432 и 6379 извне
   ```

---

## 💾 БЭКАПЫ

### PostgreSQL бэкап
```bash
# Все schemas
docker-compose exec postgres pg_dump -U booking_user booking_saas > backup.sql

# Конкретная schema
docker-compose exec postgres pg_dump -U booking_user -n master_bot booking_saas > master_bot_backup.sql
```

### Восстановление
```bash
docker-compose exec -T postgres psql -U booking_user booking_saas < backup.sql
```

### Автоматические бэкапы
Добавьте в cron:
```bash
0 2 * * * docker-compose exec postgres pg_dump -U booking_user booking_saas > /backups/booking_$(date +\%Y\%m\%d).sql
```

---

## 🐛 TROUBLESHOOTING

### Бот не запускается
```bash
# Проверить логи
docker-compose logs bot-master

# Типичные причины:
# 1. Неверный BOT_TOKEN
# 2. PostgreSQL недоступен (проверить: docker-compose ps)
# 3. Redis недоступен
```

### Schema не создается
```bash
# Проверить права
docker-compose exec postgres psql -U booking_user -d booking_saas

# Выполнить вручную:
GRANT ALL ON SCHEMA public TO booking_user;
```

### Бот не отвечает
```bash
# Проверить health
docker-compose ps

# Перезапустить
docker-compose restart bot-master
```

---

## ✅ РЕЗЮМЕ

✅ **Master Bot и Sales Bot запускаются автоматически**  
✅ **Полная изоляция данных**  
✅ **Неограниченное количество ботов**  
✅ **Production-ready**  

🚀 **Проект готов к развертыванию!**
