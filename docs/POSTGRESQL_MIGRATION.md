# PostgreSQL Migration Guide

## Обзор

Это руководство описывает процесс миграции с SQLite на PostgreSQL для повышения производительности и масштабируемости системы бронирования.

## Преимущества PostgreSQL

✅ **Конкурентная запись** - поддержка одновременных транзакций от нескольких пользователей  
✅ **Connection pooling** - эффективное управление подключениями  
✅ **Лучшая производительность** - оптимизация для high-load сценариев  
✅ **Транзакционная целостность** - ACID compliance  
✅ **Масштабируемость** - готовность к горизонтальному масштабированию  

## Требования

- Docker и Docker Compose
- PostgreSQL 14+
- Python 3.11+
- Существующая SQLite БД (для миграции данных)

## Шаг 1: Запуск PostgreSQL

### 1.1 Настройка окружения

Создайте файл `.env.postgresql`:

```bash
# PostgreSQL Admin
POSTGRES_ADMIN_PASSWORD=strong_admin_password_here

# PgAdmin (optional)
PGADMIN_EMAIL=admin@yourdomain.com
PGADMIN_PASSWORD=pgadmin_password_here
```

### 1.2 Запуск контейнера PostgreSQL

```bash
# Запуск PostgreSQL + PgAdmin
docker-compose -f docker-compose.postgresql.yml up -d

# Или только PostgreSQL (без PgAdmin)
docker-compose -f docker-compose.postgresql.yml up -d postgres

# Проверка статуса
docker ps | grep postgres
```

### 1.3 Проверка подключения

```bash
# Подключение к PostgreSQL
docker exec -it postgres-shared psql -U booking_admin -d postgres

# Список баз данных
\l

# Выход
\q
```

## Шаг 2: Смена паролей пользователей

**⚠️ КРИТИЧЕСКИ ВАЖНО:** Измените дефолтные пароли!

```bash
# Подключитесь к PostgreSQL
docker exec -it postgres-shared psql -U booking_admin -d postgres

# Смените пароли
ALTER USER client_001_user WITH PASSWORD 'new_secure_password_001';
ALTER USER client_002_user WITH PASSWORD 'new_secure_password_002';
ALTER USER client_003_user WITH PASSWORD 'new_secure_password_003';
ALTER USER monitoring_user WITH PASSWORD 'new_monitoring_password';
```

## Шаг 3: Конфигурация приложения

### 3.1 Обновление `.env` для каждого клиента

```bash
# clients/client_001/.env

# Database Type
DB_TYPE=postgresql

# PostgreSQL Connection
DATABASE_URL=postgresql://client_001_user:new_secure_password_001@postgres-shared:5432/client_001_db

# Connection Pool Settings
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20
DB_POOL_TIMEOUT=30.0
DB_COMMAND_TIMEOUT=60.0

# Legacy SQLite (удалите или закомментируйте)
# DATABASE_PATH=bookings.db
```

### 3.2 Проверка конфигурации

```bash
# Тест подключения
python -c "
import asyncio
from database.db_adapter import db_adapter

async def test():
    await db_adapter.init_pool()
    result = await db_adapter.fetchval('SELECT 1')
    print(f'✅ PostgreSQL connection: {result}')
    await db_adapter.close_pool()

asyncio.run(test())
"
```

## Шаг 4: Миграция данных из SQLite

### 4.1 Создание резервной копии SQLite

```bash
# Backup всех клиентов
for client in client_001 client_002 client_003; do
    cp clients/$client/bookings.db clients/$client/bookings.db.backup_$(date +%Y%m%d)
done
```

### 4.2 Запуск миграции

```bash
# Миграция одного клиента
python scripts/migrate_sqlite_to_postgres.py --client client_001

# Или миграция всех клиентов сразу
python scripts/migrate_sqlite_to_postgres.py --all
```

### 4.3 Проверка миграции

```bash
# Подключитесь к PostgreSQL
docker exec -it postgres-shared psql -U client_001_user -d client_001_db

# Проверьте количество записей
SELECT 
    'users' as table_name, COUNT(*) as row_count FROM users
UNION ALL
SELECT 'services', COUNT(*) FROM services
UNION ALL
SELECT 'bookings', COUNT(*) FROM bookings
UNION ALL
SELECT 'admins', COUNT(*) FROM admins;

# Проверьте последние бронирования
SELECT * FROM bookings ORDER BY created_at DESC LIMIT 5;
```

## Шаг 5: Запуск приложения с PostgreSQL

### 5.1 Остановка старых контейнеров

```bash
# Graceful shutdown
docker stop bot-client-001
docker stop bot-client-002
docker stop bot-client-003
```

### 5.2 Пересборка образа (если нужно)

```bash
docker build -t booking-bot:latest .
```

### 5.3 Запуск с новой конфигурацией

```bash
# Запуск всех сервисов
docker-compose up -d

# Проверка логов
docker logs -f bot-client-001 --tail 100

# Должны увидеть:
# ✅ PostgreSQL pool created: 5-20 connections
```

## Шаг 6: Тестирование

### 6.1 Запуск unit tests

```bash
pytest tests/test_postgresql_migration.py -v
```

### 6.2 Функциональное тестирование

1. **Создание бронирования** - проверьте, что новые бронирования сохраняются
2. **Конкурентные запросы** - откройте бота в нескольких устройствах одновременно
3. **Отмена бронирования** - проверьте изменение статуса
4. **Напоминания** - убедитесь, что scheduler работает корректно

### 6.3 Performance тестирование

```bash
# Load test (если есть локust или ab)
ab -n 100 -c 10 http://localhost:8080/health
```

## Шаг 7: Мониторинг

### 7.1 Мониторинг PostgreSQL

```sql
-- Активные подключения
SELECT 
    datname,
    count(*) as connections,
    max(state) as state
FROM pg_stat_activity
WHERE datname LIKE 'client_%'
GROUP BY datname;

-- Размер баз данных
SELECT 
    datname,
    pg_size_pretty(pg_database_size(datname)) as size
FROM pg_database
WHERE datname LIKE 'client_%'
ORDER BY pg_database_size(datname) DESC;

-- Медленные запросы (если настроен pg_stat_statements)
SELECT 
    query,
    calls,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### 7.2 Application metrics

```bash
# Health check
curl http://localhost:8080/health

# Detailed stats
curl http://localhost:8080/stats
```

## Troubleshooting

### Проблема: Connection refused

```bash
# Проверьте статус PostgreSQL
docker ps | grep postgres

# Проверьте логи
docker logs postgres-shared

# Проверьте network
docker network inspect booking-network
```

### Проблема: Authentication failed

```bash
# Проверьте пароль в DATABASE_URL
echo $DATABASE_URL

# Попробуйте подключиться вручную
psql "postgresql://client_001_user:password@localhost:5432/client_001_db"
```

### Проблема: Too many connections

```sql
-- Увеличьте max_connections в postgresql.conf
ALTER SYSTEM SET max_connections = 200;
SELECT pg_reload_conf();

-- Или уменьшите DB_POOL_MAX_SIZE в .env
DB_POOL_MAX_SIZE=10
```

### Проблема: Slow queries

```sql
-- Создайте индексы на часто используемых колонках
CREATE INDEX idx_bookings_user_id ON bookings(user_id);
CREATE INDEX idx_bookings_date_time ON bookings(booking_date, booking_time);
CREATE INDEX idx_bookings_status ON bookings(status);

-- Обновите статистику
ANALYZE;
```

## Rollback на SQLite

Если что-то пошло не так:

```bash
# 1. Остановите бота
docker stop bot-client-001

# 2. Восстановите SQLite из backup
cp clients/client_001/bookings.db.backup_20260214 clients/client_001/bookings.db

# 3. Измените .env
DB_TYPE=sqlite
DATABASE_PATH=bookings.db
# DATABASE_URL=...  # закомментируйте

# 4. Запустите бота
docker-compose up -d
```

## Best Practices

### Security

1. ✅ Используйте сильные пароли (минимум 32 символа)
2. ✅ Храните credentials в Vault или AWS Secrets Manager
3. ✅ Настройте SSL/TLS для production
4. ✅ Ограничьте сетевой доступ через firewall
5. ✅ Регулярно обновляйте PostgreSQL

### Performance

1. ✅ Настройте connection pool по нагрузке
2. ✅ Создайте индексы на часто запрашиваемых колонках
3. ✅ Используйте EXPLAIN ANALYZE для оптимизации запросов
4. ✅ Настройте autovacuum для очистки dead tuples
5. ✅ Мониторьте метрики с помощью pg_stat_statements

### Backup

1. ✅ Настройте автоматический backup (pg_dump)
2. ✅ Храните backups в отдельном хранилище (S3, NAS)
3. ✅ Тестируйте восстановление из backup регулярно
4. ✅ Используйте Point-in-Time Recovery (PITR) для production

## Дополнительные ресурсы

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [Connection Pooling Best Practices](https://wiki.postgresql.org/wiki/Number_Of_Database_Connections)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)

---

**Версия:** 1.0  
**Дата:** 14 февраля 2026  
**Автор:** Booking Bot Team
