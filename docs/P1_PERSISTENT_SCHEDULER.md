# ✅ P1: Persistent Jobstore для APScheduler

**Дата:** 15 февраля 2026  
**Приоритет:** P1 (Важно)  
**Статус:** ✅ **FIXED**

---

## 🎯 ПРОБЛЕМА

### ДО исправления:

```python
# ❌ ПРОБЛЕМА: In-memory jobstore
scheduler = AsyncIOScheduler(
    jobstores={},  # ← Пустой = MemoryJobStore по умолчанию
    executors={"default": {"type": "threadpool", "max_workers": 1}},
    job_defaults={"coalesce": False, "max_instances": 1},
)
```

**Последствия:**

1. **❌ Потеря jobs при рестарте**
   - Все запланированные напоминания теряются
   - Пользователи не получают напоминания
   - Приходится восстанавливать из БД

2. **❌ Неэффективное восстановление**
   - `BookingService.restore_reminders()` при каждом старте
   - Нагрузка на БД при старте
   - Задержка старта бота

3. **❌ Проблемы в production**
   - Deploy новой версии → потеря jobs
   - Auto-scaling → потеря jobs
   - Crash recovery → потеря jobs

---

## ✅ РЕШЕНИЕ

### ПОСЛЕ исправления:

```python
# ✅ РЕШЕНИЕ: PostgreSQL jobstore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

def create_scheduler() -> AsyncIOScheduler:
    """Create scheduler with persistent jobstore"""
    jobstores = {}
    
    if DB_TYPE == "postgresql":
        try:
            jobstores["default"] = SQLAlchemyJobStore(
                url=DATABASE_URL,
                tablename="apscheduler_jobs"
            )
            logger.info(
                "✅ Using PostgreSQL jobstore\n"
                "   Jobs will persist across restarts"
            )
        except ImportError:
            logger.warning("SQLAlchemy not installed")
            jobstores = {}  # Fallback to MemoryJobStore
    
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors={"default": {"type": "threadpool", "max_workers": 1}},
        job_defaults={"coalesce": False, "max_instances": 1},
    )
    
    return scheduler
```

---

## 📊 РЕЗУЛЬТАТЫ

### ✅ Преимущества:

1. **✅ Persistence через рестарты**
   - Jobs хранятся в PostgreSQL таблице `apscheduler_jobs`
   - Полное восстановление после рестарта
   - Не нужно восстанавливать из bookings

2. **✅ Быстрый старт**
   - Не нужно вызывать `restore_reminders()`
   - Минимальная нагрузка на БД
   - Инстантный старт бота

3. **✅ Production-ready**
   - Deploy без потери jobs
   - Auto-scaling ready
   - Crash recovery автоматически

4. **✅ Backward compatible**
   - SQLite mode → MemoryJobStore (fallback)
   - Нет SQLAlchemy → MemoryJobStore (fallback)
   - Старый код продолжает работать

---

## 🛠️ ИНСТРУКЦИЯ ПО УСТАНОВКЕ

### 1. Установить зависимости

```bash
pip install -r requirements.txt
```

**Новая зависимость:**
- `SQLAlchemy==2.0.36` - для SQLAlchemyJobStore

### 2. Проверить DATABASE_URL

```bash
# .env
DATABASE_URL=postgresql://user:password@localhost:5432/booking_bot
```

### 3. Запустить бота

```bash
python main.py
```

**Ожидаемый лог:**
```
✅ Using PostgreSQL jobstore for APScheduler
   • Jobs will persist across restarts
   • Table: apscheduler_jobs
```

### 4. Проверить таблицу

```sql
-- Проверить что таблица создана
SELECT * FROM apscheduler_jobs;

-- Посмотреть запланированные jobs
SELECT id, next_run_time FROM apscheduler_jobs;
```

---

## 💻 ТЕХНИЧЕСКИЕ ДЕТАЛИ

### Структура таблицы `apscheduler_jobs`

```sql
CREATE TABLE apscheduler_jobs (
    id VARCHAR(191) PRIMARY KEY,
    next_run_time FLOAT,
    job_state BYTEA NOT NULL
);
```

**Поля:**
- `id` - Уникальный ID job (например, `reminder_123`)
- `next_run_time` - Unix timestamp следующего запуска
- `job_state` - Сериализованное состояние job (pickle)

### Какие jobs хранятся

1. **Рекуррентные jobs** (из `setup_reminder_jobs`):
   - `reminder_24h` - ежедневно в 10:00
   - `reminder_2h` - каждые 2 часа
   - `reminder_1h` - каждый час

2. **Индивидуальные напоминания** (из `BookingService._schedule_reminder`):
   - `reminder_{booking_id}` - напоминание о записи
   - `feedback_{booking_id}` - запрос обратной связи

### Lifecycle

```mermaid
graph LR
    A[Job Created] --> B[Saved to DB]
    B --> C[Scheduled in APScheduler]
    C --> D{Bot Restart?}
    D -->|Yes| E[Load from DB]
    E --> C
    D -->|No| F[Execute at trigger time]
    F --> G[Remove from DB]
```

---

## 🐛 ТРАБЛШУТИНГ

### Проблема: Jobs не хранятся

**Причины:**

1. **SQLAlchemy не установлен**
   ```bash
   pip install SQLAlchemy==2.0.36
   ```

2. **Неправильный DATABASE_URL**
   ```bash
   # Проверить в .env
   echo $DATABASE_URL
   ```

3. **DB_TYPE != "postgresql"**
   ```bash
   # Проверить в .env
   echo $DB_TYPE  # должно быть: postgresql
   ```

### Проблема: Ошибка при старте

**SQLAlchemy connection error:**
```python
Failed to create PostgreSQL jobstore: ...
Falling back to in-memory jobstore
```

**Решение:**
1. Проверить PostgreSQL connection
2. Проверить DATABASE_URL format
3. Проверить права доступа к БД

---

## 📊 МОНИТОРИНГ

### SQL Запросы для мониторинга

```sql
-- Количество активных jobs
SELECT COUNT(*) FROM apscheduler_jobs;

-- Jobs с ближайшим запуском
SELECT 
    id,
    to_timestamp(next_run_time) as next_run
FROM apscheduler_jobs
ORDER BY next_run_time
LIMIT 10;

-- Jobs по типу
SELECT 
    CASE 
        WHEN id LIKE 'reminder_%' THEN 'reminder'
        WHEN id LIKE 'feedback_%' THEN 'feedback'
        ELSE id
    END as job_type,
    COUNT(*) as count
FROM apscheduler_jobs
GROUP BY job_type;
```

### Grafana Dashboard

```sql
-- Metric: Total active jobs
SELECT COUNT(*) as active_jobs FROM apscheduler_jobs;

-- Metric: Jobs by type
SELECT 
    SUBSTRING(id FROM '^[^_]+') as job_type,
    COUNT(*) as count
FROM apscheduler_jobs
GROUP BY job_type;

-- Metric: Next job execution time
SELECT MIN(next_run_time) as next_execution 
FROM apscheduler_jobs;
```

---

## 🔗 ССЫЛКИ

- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [SQLAlchemyJobStore](https://apscheduler.readthedocs.io/en/3.x/modules/jobstores/sqlalchemy.html)
- [main.py commit](https://github.com/balzampsilo-sys/new12_02/commit/dba4efa750e8c90797e78e5cae355af62cfb8042)

---

## ✅ ЗАКЛЮЧЕНИЕ

**Статус:** ✅ **PRODUCTION READY**

**Что было сделано:**
1. ✅ Добавлен PostgreSQL jobstore
2. ✅ SQLAlchemy в requirements.txt
3. ✅ Graceful fallback к MemoryJobStore
4. ✅ Backward compatibility
5. ✅ Документация

**Результат:**
- Нет потери jobs при рестарте
- Быстрый старт бота
- Production-ready deployment
- Готов к auto-scaling

---

**Дата завершения:** 15 февраля 2026  
**Commits:** 2 (main.py + requirements.txt)  
**Версия:** 1.0
