# 🌍 Система локализации (Гибридный i18n)

## 🎯 Обзор

Гибридная система управления текстами бота с поддержкой:
- ✅ **YAML-файлы** (`locales/ru.yaml`) - дефолтные тексты
- ✅ **БД** (`text_templates`) - кастомизация админом
- ✅ **Admin UI** - редактор текстов без перезапуска
- ✅ **Кэширование** (TTL 5 мин) - быстрый доступ
- ✅ **Многоязычность** - RU/EN (easily extensible)

---

## 🔍 Приоритеты загрузки

```
1. БД (text_templates)       →  Кастомизированные админом
2. YAML (locales/ru.yaml)   →  Дефолтные значения
3. Fallback (hardcoded)     →  На случай ошибок
```

---

## 🛠️ Компоненты

### 1️⃣ YAML-файлы (`locales/ru.yaml`)

**Структура:**
```yaml
common:
  back: "⬅️ Назад"
  confirm: "✅ Подтвердить"
  cancel: "❌ Отмена"

booking:
  button: "📅 Записаться"
  select_date: "📅 Выберите дату"
  success: |
    ✅ Вы успешно записаны!
    
    📅 Дата: {date}
    🕒 Время: {time}
```

### 2️⃣ БД (`text_templates` таблица)

**Структура:**
```sql
CREATE TABLE text_templates (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,        -- 'booking.success'
    text_ru TEXT NOT NULL,
    text_en TEXT,
    category TEXT DEFAULT 'general',
    is_custom BOOLEAN DEFAULT 0,     -- 1 = кастомизирован
    updated_at TIMESTAMP,
    updated_by INTEGER
);
```

### 3️⃣ HybridTextManager (`services/text_manager.py`)

**Основные методы:**

```python
from services.text_manager import HybridTextManager

# Инициализация (в main.py)
await HybridTextManager.init()

# Получение текста
text = await HybridTextManager.get('booking.success', date='10.02', time='14:00')

# Обновление текста
await HybridTextManager.update('booking.success', '✅ Готово!', admin_id=123)

# Сброс к дефолту
await HybridTextManager.reset_to_default('booking.success')

# Перезагрузка YAML
await HybridTextManager.reload_yaml()
```

### 4️⃣ Admin UI (`handlers/admin/text_editor.py`)

**Доступ:**
1. `/admin` → 📝 Редактор текстов
2. Выберите категорию (📋 Общие, 📅 Бронирование, и т.д.)
3. Нажмите на ключ для редактирования
4. Отправьте новый текст

**Возможности:**
- ✅ Редактирование текстов без перезапуска
- ✅ Сброс к дефолтному значению
- ✅ Перезагрузка YAML-файлов
- ✅ Очистка кэша
- ✅ Просмотр истории изменений

---

## 🚀 Quick Start

### Добавление нового текста

**Шаг 1:** Добавьте в `locales/ru.yaml`
```yaml
my_category:
  greeting: "👋 Привет, {name}!"
```

**Шаг 2:** Используйте в коде
```python
from services.text_manager import HybridTextManager

text = await HybridTextManager.get('my_category.greeting', name='Алекс')
await message.answer(text)
```

**Шаг 3:** Кастомизируйте через Admin UI
- `/admin` → 📝 Редактор текстов
- Выберите `my_category`
- Нажмите `greeting`
- Отправьте новый текст: `🎉 Здравствуй, {name}!`

---

## 🔧 Миграция

**Автоматическая миграция v009:**
```bash
python main.py  # Миграция применяется автоматически
```

**Что создается:**
- ✅ `text_templates` - таблица текстов
- ✅ `text_changes_log` - история изменений
- ✅ Индексы для быстрого поиска
- ✅ Примеры текстов (common, booking)

---

## 📊 Мониторинг

**Логи:**
```
✅ HybridTextManager initialized
✅ Loaded 150 YAML categories for 'ru'
✅ Text updated: booking.success by admin 123
⚠️ Text not found for key: unknown.key
```

**Кэширование:**
- TTL: 5 минут
- Max size: 1000 текстов
- Очистка: через Admin UI или `HybridTextManager.clear_cache()`

---

## 🧑‍💻 Для разработчиков

### Архитектура

```
locales/
  └─ ru.yaml              # Дефолтные тексты

services/
  └─ text_manager.py     # HybridTextManager

handlers/admin/
  └─ text_editor.py      # Admin UI

database/migrations/versions/
  └─ v009_text_templates.py  # Миграция таблиц
```

### Best Practices

✅ **Используйте структурированные ключи:**
```python
# ✅ Good
await HybridTextManager.get('booking.errors.slot_taken')

# ❌ Bad  
await HybridTextManager.get('error1')
```

✅ **Используйте параметры форматирования:**
```python
# ✅ Good
text = await HybridTextManager.get('booking.success', 
    date='10.02', 
    time='14:00',
    service='Стрижка'
)

# ❌ Bad
text = f"✅ Вы записаны {date} {time}"  # Hardcoded!
```

✅ **Обрабатывайте отсутствующие ключи:**
```python
text = await HybridTextManager.get('unknown.key')
if text.startswith('['):
    # Fallback: ключ не найден
    text = "❌ Ошибка"
```

---

## 🔒 Безопасность

- ✅ **Admin-only access** - редактор доступен только админам
- ✅ **Audit log** - все изменения логируются в `text_changes_log`
- ✅ **Rollback support** - сброс к дефолтным значениям
- ✅ **Cache isolation** - кэш по языкам (`key:lang`)

---

## 🐛 Troubleshooting

**Проблема:** Текст не обновляется после редактирования
**Решение:** Очистите кэш через Admin UI или подождите 5 минут (TTL)

**Проблема:** Ключ не найден `[booking.test]`
**Решение:** Добавьте ключ в `locales/ru.yaml` или создайте через Admin UI

**Проблема:** YAML не загружается
**Решение:** Проверьте синтаксис YAML и путь `locales/ru.yaml`

---

## ✨ Features

- ✅ **Hot reload** - изменения без перезапуска
- ✅ **Multi-language** - RU/EN + easy extension
- ✅ **Admin UI** - удобный интерфейс редактирования
- ✅ **Caching** - TTL 5min, 1000 текстов
- ✅ **Audit log** - полная история изменений
- ✅ **Fallback** - гарантированный ответ
- ✅ **Format support** - `{param}` placeholders

---

## 🔗 Ссылки

- [YAML Syntax](https://yaml.org/)
- [Python string.format()](https://docs.python.org/3/library/string.html#formatstrings)
- [cachetools TTLCache](https://cachetools.readthedocs.io/)

---

**Сделано с ❤️ для new12_02 booking bot**
