# 🔧 Developer API Documentation

Краткая справка по API для разработчиков.

---

## 📚 Содержание

- [Services API](#services-api)
- [Repositories API](#repositories-api)
- [Handlers](#handlers)
- [Middlewares](#middlewares)
- [Utils](#utils)

---

## 🔹 Services API

### BookingService

**Местоположение:** `services/booking_service.py`

```python
from services.booking_service import BookingService

# Инициализация
service = BookingService(scheduler, bot)

# Восстановление напоминаний
await service.restore_reminders()

# Добавить напоминание
await service.add_reminder(user_id, booking_id, date, time)

# Отменить напоминание
await service.cancel_reminder(booking_id)
```

---

### ReminderService

**Местоположение:** `services/reminder_service.py`

```python
from services.reminder_service import ReminderService

# Отправить напоминания за 24 часа
success, total = await ReminderService.send_reminders_24h(bot)

# Отправить напоминания за 2 часа
success, total = await ReminderService.send_reminders_2h(bot)

# Отправить напоминания за 1 час
success, total = await ReminderService.send_reminders_1h(bot)

# Получить количество предстоящих записей
count = await ReminderService.get_upcoming_bookings_count(hours=24)
```

---

### NotificationService

**Местоположение:** `services/notification_service.py`

```python
from services.notification_service import NotificationService

service = NotificationService(bot)

# Отправить уведомление о записи
await service.send_booking_confirmation(user_id, booking_info)

# Отправить уведомление об отмене
await service.send_cancellation_notice(user_id, booking_info)

# Broadcast сообщение
await service.broadcast_message(user_ids, message)
```

---

### AnalyticsService

**Местоположение:** `services/analytics_service.py`

```python
from services.analytics_service import AnalyticsService

# Записать событие
await AnalyticsService.log_event(
    user_id=123,
    event="booking_created",
    data={"service_id": 1, "date": "2026-02-13"}
)

# Получить статистику
stats = await AnalyticsService.get_stats(period="week")
```

---

### HybridTextManager

**Местоположение:** `services/text_manager.py`

```python
from services.text_manager import HybridTextManager

# Инициализация (загрузка YAML)
await HybridTextManager.init()

# Получить текст (из DB или YAML)
text = await HybridTextManager.get("common.back", lang="ru")

# Обновить текст (в DB)
await HybridTextManager.update(
    key="common.back",
    text_ru="Назад",
    updated_by=admin_id
)
```

---

## 📊 Repositories API

### BookingRepositoryV2

**Местоположение:** `database/repositories/booking_repository_v2.py`

```python
from database.repositories.booking_repository_v2 import BookingRepositoryV2

# Создать запись с ACID транзакцией
success, error = await BookingRepositoryV2.create_booking_atomic(
    user_id=123,
    username="user",
    date_str="2026-02-13",
    time_str="14:00",
    service_id=1,
    duration_minutes=60
)

# Отменить запись
success, error = await BookingRepositoryV2.cancel_booking_atomic(
    booking_id=1,
    user_id=123,
    reason="Перенос"
)

# Заблокировать слот
success, cancelled_users, error = await BookingRepositoryV2.block_slot_atomic(
    date_str="2026-02-13",
    time_str="14:00",
    admin_id=456,
    reason="Обед"
)

# Получить занятые слоты
slots = await BookingRepositoryV2.get_occupied_slots_for_day("2026-02-13")

# Получить записи пользователя
bookings = await BookingRepositoryV2.get_user_bookings(user_id=123)
```

**Особенности:**
- ✅ ACID транзакции (`BEGIN IMMEDIATE`)
- ✅ Transaction timeout (30с)
- ✅ Query timeout (10с)
- ✅ Rate limiting (3 попытки/10с)
- ✅ Retry logic (3 попытки)

---

### ServiceRepository

**Местоположение:** `database/repositories/service_repository.py`

```python
from database.repositories.service_repository import ServiceRepository

# Получить все активные услуги
services = await ServiceRepository.get_active_services()

# Получить услугу по ID
service = await ServiceRepository.get_service_by_id(service_id=1)

# Создать услугу
await ServiceRepository.create_service(
    name="Стрижка",
    description="Мужская стрижка",
    duration_minutes=60,
    price="1500₽",
    slot_interval_minutes=30
)

# Обновить услугу
await ServiceRepository.update_service(service_id=1, **updates)
```

---

### AdminRepository

**Местоположение:** `database/repositories/admin_repository.py`

```python
from database.repositories.admin_repository import AdminRepository

# Проверить админа
is_admin = await AdminRepository.is_admin(user_id=123)

# Получить роль
role = await AdminRepository.get_admin_role(user_id=123)

# Добавить админа
await AdminRepository.add_admin(
    user_id=789,
    username="newadmin",
    added_by=123,
    role="moderator"  # или 'super_admin'
)

# Удалить админа
await AdminRepository.remove_admin(user_id=789)
```

---

## 🎯 Handlers

### Структура handler'а

```python
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет!")

@router.callback_query(F.data == "action")
async def process_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Обработано")
```

### Доступные handlers

| Handler | Описание | Файл |
|---------|----------|-------|
| user_handlers | Основные команды | `handlers/user_handlers.py` |
| booking_handlers | Бронирование | `handlers/booking_handlers.py` |
| admin_handlers | Админ-панель | `handlers/admin_handlers.py` |
| calendar_handlers | Календарь | `handlers/calendar_handlers.py` |
| service_management | Управление услугами | `handlers/service_management_handlers.py` |
| admin_management | Управление админами | `handlers/admin_management_handlers.py` |
| audit_handlers | Audit log | `handlers/audit_handlers.py` |
| settings_handlers | Настройки | `handlers/settings_handlers.py` |
| text_editor | Редактор текстов (i18n) | `handlers/admin/text_editor.py` |

---

## 🛡️ Middlewares

### RateLimitMiddleware

**Местоположение:** `middlewares/rate_limit.py`

```python
from middlewares.rate_limit import RateLimitMiddleware

# Добавить к dispatcher
dp.message.middleware(RateLimitMiddleware(rate_limit=0.5))
dp.callback_query.middleware(RateLimitMiddleware(rate_limit=0.3))
```

**Параметры:**
- `rate_limit` - минимальный интервал между действиями (секунды)

---

### MessageCleanupMiddleware

**Местоположение:** `middlewares/message_cleanup.py`

```python
from middlewares.message_cleanup import MessageCleanupMiddleware

# Добавить к dispatcher
dp.callback_query.middleware(MessageCleanupMiddleware(ttl_hours=48))
```

**Параметры:**
- `ttl_hours` - время жизни сообщений (часы)

---

## 🧰 Utils

### Helpers

**Местоположение:** `utils/helpers.py`

```python
from utils.helpers import now_local, format_datetime

# Получить текущее время в Moscow
now = now_local()

# Форматировать datetime
formatted = format_datetime(dt, format="%d.%m.%Y %H:%M")
```

---

### BackupService

**Местоположение:** `utils/backup_service.py`

```python
from utils.backup_service import BackupService

service = BackupService(
    db_path="data/bookings.db",
    backup_dir="backups",
    retention_days=30
)

# Создать бэкап
service.create_backup()

# Список бэкапов
backups = service.list_backups()

# Восстановить
success = service.restore_backup(backup_path)

# Очистить старые
service.cleanup_old_backups()
```

---

### Error Handler

**Местоположение:** `utils/error_handler.py`

```python
from utils.error_handler import (
    async_retry_on_error,
    handle_database_error,
    safe_operation
)

# Retry decorator
@async_retry_on_error(max_attempts=3, delay=0.5)
async def my_function():
    # Your code
    pass

# Database error handler
try:
    # DB operation
    pass
except aiosqlite.Error as e:
    can_retry = await handle_database_error(e, context={"user_id": 123})

# Safe operation context
async with safe_operation("operation_name", **context):
    # Your code
    pass
```

---

## 🔍 Validation

### Pydantic Schemas

**Местоположение:** `validation/schemas.py`

```python
from validation.schemas import (
    BookingCreateInput,
    BookingCancelInput,
    TimeSlotInput,
    SlotBlockInput
)

# Валидация входных данных
try:
    booking = BookingCreateInput(
        user_id=123,
        username="user",
        date=datetime.date(2026, 2, 13),
        time=datetime.time(14, 0),
        service_id=1,
        duration_minutes=60
    )
except ValidationError as e:
    print(e.errors())
```

**Доступные schemas:**
- `BookingCreateInput`
- `BookingCancelInput`
- `TimeSlotInput`
- `SlotBlockInput`

---

## 📚 Примеры использования

### Создание записи

```python
from database.repositories.booking_repository_v2 import BookingRepositoryV2
from services.notification_service import NotificationService

# 1. Создать запись
success, error = await BookingRepositoryV2.create_booking_atomic(
    user_id=message.from_user.id,
    username=message.from_user.username,
    date_str="2026-02-13",
    time_str="14:00",
    service_id=1,
    duration_minutes=60
)

if not success:
    await message.answer(f"Ошибка: {error}")
    return

# 2. Отправить уведомление
service = NotificationService(bot)
await service.send_booking_confirmation(
    user_id=message.from_user.id,
    booking_info={...}
)

# 3. Добавить напоминание
await booking_service.add_reminder(
    user_id=message.from_user.id,
    booking_id=booking_id,
    date="2026-02-13",
    time="14:00"
)
```

---

### Добавление нового handler'а

```python
# handlers/my_new_handler.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

router = Router()

@router.callback_query(F.data == "my_action")
async def my_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Обработано!")
```

```python
# main.py
from handlers import my_new_handler

# Добавить в dispatcher
dp.include_router(my_new_handler.router)
```

---

### Добавление middleware

```python
# middlewares/my_middleware.py
from aiogram import BaseMiddleware
from aiogram.types import Message

class MyMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        # Before handler
        print(f"Processing: {event.text}")
        
        # Call handler
        result = await handler(event, data)
        
        # After handler
        print("Done!")
        
        return result
```

```python
# main.py
from middlewares.my_middleware import MyMiddleware

dp.message.middleware(MyMiddleware())
```

---

## 📌 Лучшие практики

1. **Используйте BookingRepositoryV2** - он обеспечивает ACID транзакции
2. **Всегда используйте now_local()** - для корректного timezone
3. **Добавляйте @async_retry_on_error** - для обработки SQLITE_BUSY
4. **Логируйте с context** - для лучшей отладки
5. **Валидируйте входные данные** - используйте Pydantic schemas

---

## 🔗 Ссылки

- [README.md](README.md) - Основная документация
- [CHANGELOG.md](CHANGELOG.md) - История изменений
- [FEATURES.md](FEATURES.md) - Подробное описание функционала
- [QUICK_START.md](QUICK_START.md) - Быстрый старт

---

**Последнее обновление:** 13 февраля 2026
