# 🐘 PostgreSQL Setup Guide

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/balzampsilo-sys/new12_02.git
cd new12_02
```

### 2. Настройка окружения

```bash
# Создать .env из примера
cp .env.example .env

# Отредактировать .env и добавить:
# - BOT_TOKEN (получить у @BotFather)
# - ADMIN_IDS (ваш Telegram ID от @userinfobot)
nano .env
```

### 3. Запуск PostgreSQL

```bash
# Инициализация (создаёт БД, Redis)
make setup

# Запуск всех сервисов
make start

# Проверка логов
make logs
```

### 4. Проверка работы

```bash
# Подключиться к PostgreSQL
make psql

# Внутри psql:
\dt                          # Список таблиц
SELECT * FROM services;     # Проверить данные
SELECT * FROM settings;     # Проверить настройки
\q                          # Выход
```

---

## Структура проекта

```
new12_02/
├── database/
│   ├── db_adapter.py              # ✅ Unified PostgreSQL/SQLite adapter
│   ├── queries.py                 # Database facade
│   ├── repositories/              # Repository pattern
│   └── migrations/
│       └── postgres/
│           ├── 01_init_schema.sql # Схема БД
│           └── 02_seed_data.sql   # Начальные данные
├── docker-compose.yml             # ✅ PostgreSQL + Redis + Bot
├── Dockerfile                     # ✅ С поддержкой PostgreSQL
├── .env.example                   # ✅ Обновлённая конфигурация
├── Makefile                       # ✅ Команды управления
└── main.py                        # Entry point
```

---

## Команды Makefile

| Команда | Описание |
|---------|----------|
| `make help` | Показать все команды |
| `make setup` | Первоначальная настройка |
| `make start` | Запустить все сервисы |
| `make stop` | Остановить все сервисы |
| `make restart` | Перезапустить сервисы |
| `make logs` | Показать логи бота |
| `make logs-postgres` | Показать логи PostgreSQL |
| `make psql` | Подключиться к PostgreSQL |
| `make redis-cli` | Подключиться к Redis |
| `make clean` | Удалить все данные (⚠️) |
| `make db-backup` | Создать резервную копию БД |

---

## Конфигурация PostgreSQL

### Основные параметры в .env:

```bash
# Тип БД (postgresql или sqlite)
DB_TYPE=postgresql

# PostgreSQL Connection String
DATABASE_URL=postgresql://booking_user:SecurePass2026!@postgres:5432/booking_db

# Connection Pool
DB_POOL_MIN_SIZE=5          # Минимум соединений
DB_POOL_MAX_SIZE=20         # Максимум соединений
DB_POOL_TIMEOUT=30.0        # Таймаут получения соединения
DB_COMMAND_TIMEOUT=60.0     # Таймаут выполнения запроса
```

### Для production на внешнем сервере:

```bash
# Замените localhost на IP сервера
DATABASE_URL=postgresql://user:pass@your-server-ip:5432/booking_db

# Если PostgreSQL на облаке (AWS RDS, Google Cloud SQL, etc.)
DATABASE_URL=postgresql://user:pass@your-cloud-db.amazonaws.com:5432/booking_db
```

---

## Преимущества PostgreSQL vs SQLite

| Параметр | SQLite | PostgreSQL |
|----------|--------|------------|
| **Concurrency** | 1 writer | 100+ concurrent connections |
| **Transactions** | Блокирует всю БД | MVCC (readers не блокируют writers) |
| **Max DB Size** | 281 TB (теоретически) | Unlimited |
| **ACID** | Да | Да |
| **JSON Support** | Ограниченный | Native JSONB с индексами |
| **Full-Text Search** | FTS5 | Native + tsvector |
| **Replication** | Нет | Streaming replication |
| **Backup** | `cp file.db` | `pg_dump` + PITR |
| **Performance** | Отлично для <100k записей | Отлично для миллионов |
| **Production Ready** | Малые проекты | Enterprise |

---

## Мониторинг

### Проверка статуса сервисов:

```bash
docker-compose ps
```

### Статистика использования ресурсов:

```bash
make stats
```

### Проверка активных соединений PostgreSQL:

```sql
-- Подключиться: make psql

SELECT 
    count(*) as total_connections,
    sum(case when state = 'active' then 1 else 0 end) as active,
    sum(case when state = 'idle' then 1 else 0 end) as idle
FROM pg_stat_activity
WHERE datname = 'booking_db';
```

### Проверка размера БД:

```sql
SELECT 
    pg_size_pretty(pg_database_size('booking_db')) as db_size,
    pg_size_pretty(pg_total_relation_size('bookings')) as bookings_size;
```

---

## Резервное копирование

### Автоматическое (встроенное):

В проекте настроен `BackupService`, который создаёт резервные копии каждые 24 часа:

```bash
# Бэкапы сохраняются в:
./backups/backup_YYYYMMDD_HHMMSS.sql
```

### Ручное:

```bash
# Создать бэкап
make db-backup

# Или напрямую через pg_dump
docker-compose exec postgres pg_dump -U booking_user -d booking_db > backup.sql
```

### Восстановление:

```bash
# Интерактивное восстановление
make db-restore

# Или напрямую
cat backup.sql | docker-compose exec -T postgres psql -U booking_user -d booking_db
```

---

## Миграции

### Применение изменений схемы:

1. Создайте новый файл в `database/migrations/postgres/`:
   ```bash
   03_add_new_feature.sql
   ```

2. Напишите SQL:
   ```sql
   BEGIN;
   
   ALTER TABLE bookings ADD COLUMN notes TEXT;
   CREATE INDEX idx_bookings_notes ON bookings(notes);
   
   COMMIT;
   ```

3. Примените миграцию:
   ```bash
   cat database/migrations/postgres/03_add_new_feature.sql | \
       docker-compose exec -T postgres psql -U booking_user -d booking_db
   ```

---

## Troubleshooting

### Проблема: "Connection refused"

```bash
# Проверить что PostgreSQL запущен
docker-compose ps postgres

# Посмотреть логи
make logs-postgres

# Перезапустить
make restart
```

### Проблема: "Database does not exist"

```bash
# Пересоздать БД
make clean
make setup
```

### Проблема: "Too many connections"

```bash
# Увеличить DB_POOL_MAX_SIZE в .env
DB_POOL_MAX_SIZE=50

# Перезапустить
make restart
```

### Проблема: Медленные запросы

```sql
-- Подключиться: make psql

-- Включить логирование медленных запросов
ALTER DATABASE booking_db SET log_min_duration_statement = 1000; -- 1 секунда

-- Посмотреть статистику запросов (требует pg_stat_statements)
SELECT query, calls, mean_exec_time 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;
```

---

## Production Deployment

### Чеклист для production:

- [ ] Изменить пароли в DATABASE_URL и docker-compose.yml
- [ ] Настроить SSL/TLS для PostgreSQL
- [ ] Включить SENTRY_ENABLED=True для мониторинга ошибок
- [ ] Настроить автоматические бэкапы (cron)
- [ ] Настроить PostgreSQL replication для HA
- [ ] Включить pg_stat_statements для мониторинга
- [ ] Настроить connection pooling (pgBouncer)
- [ ] Настроить мониторинг (Prometheus + Grafana)
- [ ] Ограничить доступ к PostgreSQL (firewall)
- [ ] Включить WAL archiving для PITR

---

## Ссылки

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [aiogram Documentation](https://docs.aiogram.dev/)

---

## Поддержка

Если возникли вопросы:

1. Проверьте логи: `make logs`
2. Проверьте БД: `make psql`
3. Создайте Issue в GitHub

**Версия:** 1.0.0 (PostgreSQL)  
**Дата:** 2026-02-14
