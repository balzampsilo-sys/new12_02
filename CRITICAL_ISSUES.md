# ❌ КРИТИЧЕСКИЕ ПРОБЛЕМЫ

**Дата:** 14 февраля 2026, 22:56 MSK  
**Статус:** 🔴 **5 критических проблем найдено**

---

## 🚨 ПРОБЛЕМА #1: PostgreSQL Schemas НЕ ИСПОЛЬЗУЮТСЯ

### Описание:
Мы настроили `PG_SCHEMA` в config.py, НО:
- ❌ `database/db_adapter.py` **НЕ использует** `PG_SCHEMA`
- ❌ `database/queries.py` **НЕ использует** `PG_SCHEMA`
- ❌ Все SQL запросы идут в `public` schema

### Последствия:
```
❌ ВСЕ клиенты используют SCHEMA "public"
❌ Данные client_001 смешиваются с client_002
❌ НЕТ изоляции между клиентами
❌ Multi-tenant архитектура НЕ РАБОТАЕТ
```

### Решение:
1. Добавить `SET search_path TO {schema}` в `db_adapter.init_pool()`
2. Префиксить таблицы в SQL запросах: `{schema}.bookings`

---

## 🚨 ПРОБЛЕМА #2: database/queries.py ИСПОЛЬЗУЕТ SQLITE

### Описание:
В `database/queries.py`:
```python
import aiosqlite
from config import DATABASE_PATH

async with aiosqlite.connect(DATABASE_PATH) as db:
    # SQLite код!
```

### Последствия:
```
❌ Database.init_db() создает SQLite таблицы
❌ PostgreSQL pool создается, но не используется
❌ Работает через SQLite, а не PostgreSQL
```

### Решение:
Переписать `Database.init_db()` чтобы использовать `db_adapter`.

---

## 🚨 ПРОБЛЕМА #3: Репозитории ИСПОЛЬЗУЮТ SQLITE

### Описание:
Все репозитории в `database/repositories/`:
```python
import aiosqlite
from config import DATABASE_PATH

async with aiosqlite.connect(DATABASE_PATH) as db:
    # SQLite код!
```

### Затронутые файлы:
- `booking_repository.py`
- `user_repository.py`
- `analytics_repository.py`
- `admin_repository.py`
- `service_repository.py`
- `calendar_repository.py`
- `settings_repository.py`
- `audit_repository.py`

### Решение:
Заменить `aiosqlite` на `db_adapter` во всех репозиториях.

---

## 🚨 ПРОБЛЕМА #4: Migrations ИСПОЛЬЗУЮТ SQLITE

### Описание:
`database/migrations/migration_manager.py`:
```python
import sqlite3

conn = sqlite3.connect(self.db_path)
# SQLite код!
```

### Последствия:
```
❌ Миграции применяются к SQLite
❌ PostgreSQL таблицы НЕ создаются
❌ Схема БД не обновляется
```

### Решение:
Переписать migrations для работы с `db_adapter`.

---

## 🚨 ПРОБЛЕМА #5: НЕТ АВТОМАТИЧЕСКОГО СОЗДАНИЯ SCHEMA

### Описание:
Когда запускается новый клиент:
- ❌ Schema `client_XXX` НЕ создается автоматически
- ❌ Таблицы НЕ создаются в schema
- ❌ Бот падает с ошибкой

### Решение:
Добавить в `Database.init_db()`:
```python
# 1. Создать schema если не существует
await db_adapter.execute(f"CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA}")

# 2. Установить search_path
await db_adapter.execute(f"SET search_path TO {PG_SCHEMA}")

# 3. Создать таблицы в schema
```

---

## 📏 СВОДНАЯ ТАБЛИЦА

| # | Проблема | Критичность | Статус |
|---|---------|--------------|--------|
| 1 | Schema не используются | 🔴 **CRITICAL** | ❌ Не исправлено |
| 2 | queries.py использует SQLite | 🔴 **CRITICAL** | ❌ Не исправлено |
| 3 | Репозитории используют SQLite | 🔴 **CRITICAL** | ❌ Не исправлено |
| 4 | Migrations используют SQLite | 🟠 **HIGH** | ❌ Не исправлено |
| 5 | Нет авто-создания schema | 🔴 **CRITICAL** | ❌ Не исправлено |

---

## 🔍 ЧТО ПРОИСХОДИТ СЕЙЧАС

```
┌──────────────────────────────────────────────────┐
│              ТЕКУЩЕЕ СОСТОЯНИЕ               │
└──────────────────────────────────────────────────┘

1. Бот запускается с CLIENT_ID=client_001
   │
   v
2. Создается PostgreSQL pool
   • PG_SCHEMA=client_001 (в config)
   • НО search_path НЕ устанавливается!
   │
   v
3. Database.init_db() вызывается
   • Использует aiosqlite.connect()
   • Создает SQLite файл data/bookings.db
   • PostgreSQL НЕ используется!
   │
   v
4. Бот работает
   • Все запросы идут в SQLite
   • PostgreSQL pool создан, но НЕ используется
   │
   v
5. Запуск client_002
   • Создает другой SQLite файл
   • НЕТ изоляции через schemas

❌ РЕЗУЛЬТАТ: Используется SQLite, PostgreSQL игнорируется!
```

---

## ⚡ КАК ДОЛЖНО РАБОТАТЬ

```
┌──────────────────────────────────────────────────┐
│              ПРАВИЛЬНОЕ ПОВЕДЕНИЕ            │
└──────────────────────────────────────────────────┘

1. Бот запускается с CLIENT_ID=client_001
   │
   v
2. db_adapter.init_pool()
   • Создает PostgreSQL pool
   • Устанавливает search_path = client_001
   │
   v
3. Database.init_db() (через db_adapter)
   • CREATE SCHEMA IF NOT EXISTS client_001
   • SET search_path TO client_001
   • CREATE TABLE client_001.bookings ...
   • CREATE TABLE client_001.services ...
   │
   v
4. Бот работает
   • Все запросы идут в PostgreSQL
   • Используется schema client_001
   │
   v
5. Запуск client_002
   • Создает schema client_002
   • Изоляция данных через schemas

✅ РЕЗУЛЬТАТ: PostgreSQL с multi-tenant изоляцией!
```

---

## 🛠️ ПЛАН ИСПРАВЛЕНИЯ

### Шаг 1: Исправить db_adapter.py
```python
# Добавить в init_pool():
from config import PG_SCHEMA

self.pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    # ...
    # ✅ Установить search_path
    server_settings={
        "search_path": PG_SCHEMA,
        "application_name": "booking_bot",
        "jit": "off",
    },
)
```

### Шаг 2: Исправить Database.init_db()
```python
# Заменить aiosqlite на db_adapter:
from database.db_adapter import db_adapter
from config import PG_SCHEMA, DB_TYPE

if DB_TYPE == "postgresql":
    # Создать schema
    await db_adapter.execute(f"CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA}")
    
    # Создать таблицы
    await db_adapter.execute(
        f"""CREATE TABLE IF NOT EXISTS {PG_SCHEMA}.bookings (...)"""
    )
else:
    # SQLite fallback (legacy)
    ...
```

### Шаг 3: Исправить репозитории
```python
# Во всех repositories/*.py:
from database.db_adapter import db_adapter

# Заменить:
# async with aiosqlite.connect(DATABASE_PATH) as db:
#     await db.execute(...)

# На:
async with db_adapter.acquire() as conn:
    await conn.execute(...)
```

### Шаг 4: Исправить migrations
```python
# В migration_manager.py:
from database.db_adapter import db_adapter
from config import DB_TYPE

if DB_TYPE == "postgresql":
    # Использовать db_adapter
else:
    # SQLite fallback
```

---

## 🐞 КАК ПРОВЕРИТЬ

### 1. Проверка schema:
```bash
docker-compose exec postgres psql -U booking_user -d booking_saas

# Проверить schemas:
SELECT schema_name FROM information_schema.schemata 
WHERE schema_name LIKE 'client_%';

# Должны увидеть:
# client_001
# client_002
```

### 2. Проверка таблиц:
```sql
-- Проверить таблицы в client_001:
SET search_path TO client_001;
\dt

-- Должны увидеть:
-- bookings, services, users, admins, ...
```

### 3. Проверка изоляции:
```sql
-- Добавить запись в client_001:
SET search_path TO client_001;
INSERT INTO bookings (date, time, user_id) VALUES ('2026-03-01', '10:00', 123);

-- Проверить client_002 (должно быть пусто):
SET search_path TO client_002;
SELECT * FROM bookings;
-- Результат: 0 rows
```

---

## ✅ ЧЕК-ЛИСТ ИСПРАВЛЕНИЙ

- [ ] Исправить `db_adapter.py` (добавить search_path)
- [ ] Исправить `Database.init_db()` (использовать db_adapter)
- [ ] Исправить `BookingRepository`
- [ ] Исправить `UserRepository`
- [ ] Исправить `AnalyticsRepository`
- [ ] Исправить `AdminRepository`
- [ ] Исправить `ServiceRepository`
- [ ] Исправить `CalendarRepository`
- [ ] Исправить `SettingsRepository`
- [ ] Исправить `AuditRepository`
- [ ] Исправить `MigrationManager`
- [ ] Протестировать создание schema
- [ ] Протестировать изоляцию данных

---

## 🚨 ВЫВОД

**ТЕКУЩАЯ АРХИТЕКТУРА НЕ РАБОТАЕТ!**

Мы настроили:
- ✅ `config.py` - PostgreSQL, schemas, key prefix
- ✅ `main.py` - PrefixedRedisStorage
- ✅ `db_adapter.py` - Connection pooling

НО:
- ❌ **ВСЯ БД логика ИСПОЛЬЗУЕТ SQLITE**
- ❌ PostgreSQL pool создается, но **НЕ ИСПОЛЬЗУЕТСЯ**
- ❌ Schemas **НЕ СОЗДАЮТСЯ**
- ❌ Multi-tenant **НЕ РАБОТАЕТ**

Нужно **ПОЛНОСТЬЮ ПЕРЕПИСАТЬ** database layer!
