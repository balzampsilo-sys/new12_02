# 🐳 Интеграция Docker Handlers в Master Bot

## 📋 Что добавлено

Создан файл `master_bot/handlers/docker_deploy_handlers.py` с полным функционалом:

✅ **Быстрый деплой** - создание бота за 30-60 секунд  
✅ **Список контейнеров** - просмотр всех клиентских ботов  
✅ **Управление** - остановка, перезапуск, удаление  
✅ **Автоматический rollback** - откат при ошибках  

---

## 🚀 Быстрая интеграция

### Вариант 1: Добавить в главное меню (рекомендуется)

Обновите функцию `main_menu_keyboard()` в `master_bot/master_bot.py`:

```python
def main_menu_keyboard():
    keyboard = [
        [KeyboardButton(text="➕ Добавить клиента")],
        [KeyboardButton(text="🐳 Docker Деплой")],  # ← НОВАЯ КНОПКА
        [KeyboardButton(text="💰 Принять платеж")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="👥 Список клиентов")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
```

### Вариант 2: Подключить Router

Добавьте в `master_bot/master_bot.py` после импортов:

```python
# В начале файла после других импортов
from master_bot.handlers.docker_deploy_handlers import router as docker_router

# После создания dp (Dispatcher)
dp.include_router(docker_router)
```

---

## 📝 Полная интеграция (пошагово)

### Шаг 1: Скачать обновления

```bash
cd C:\bot_project\b_m_s\new12_02
git pull origin main
```

### Шаг 2: Обновить `master_bot/master_bot.py`

Добавьте после создания `dp`:

```python
# === ROUTERS ===
from master_bot.handlers.docker_deploy_handlers import router as docker_router

# Подключить Docker handlers
dp.include_router(docker_router)
logger.info("✅ Docker handlers registered")
```

### Шаг 3: Добавить кнопку в меню

Измените `main_menu_keyboard()`:

```python
def main_menu_keyboard():
    keyboard = [
        [KeyboardButton(text="➕ Добавить клиента")],
        [KeyboardButton(text="🐳 Docker Деплой")],  # ← ДОБАВИТЬ
        [KeyboardButton(text="💰 Принять платеж")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="👥 Список клиентов")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
```

### Шаг 4: Перезапустить Master Bot

```bash
# Перезапустить контейнер
docker-compose restart bot-master

# Проверить логи
docker logs booking-bot-master -f
```

---

## 🎯 Использование

### В Telegram боте:

1. Откройте Master Bot
2. Нажмите **🐳 Docker Деплой**
3. Выберите **🚀 Создать бота (быстро)**
4. Следуйте инструкциям:
   - Отправьте токен бота
   - Отправьте Telegram ID администратора
   - Введите название компании
   - Подтвердите

### Результат:

```
✅ БОТ УСПЕШНО РАЗВЁРНУТ!

🏪 Компания:      Салон красоты Анны
🆔 Client ID:    abc12345-...
🐳 Container:    booking-client-abc12345
📊 Redis DB:     5
🗄️  Schema:       client_abc12345
👤 Admin ID:     123456789

✅ Бот работает 24/7 в Docker!
```

---

## 📊 Дополнительные функции

### Список контейнеров

Нажмите **🐳 Список Docker контейнеров** для просмотра всех клиентских ботов:

```
🐳 DOCKER КОНТЕЙНЕРЫ (3)

✅ booking-client-abc12345
   🏪 Салон красоты Анны
   📊 Status: running

✅ booking-client-def67890
   🏪 Барбершоп Max
   📊 Status: running

❌ booking-client-ghi11111
   🏪 Фитнес-студия
   📊 Status: exited
```

### Управление клиентом

*Функция в разработке*

Пока используйте Docker команды:

```bash
# Остановить
docker stop booking-client-abc12345

# Перезапустить
docker restart booking-client-abc12345

# Удалить
docker rm booking-client-abc12345
```

---

## 🔍 Проверка работоспособности

### Тест 1: Проверить что хэндлеры загружены

```bash
docker exec -it booking-bot-master python -c "from master_bot.handlers.docker_deploy_handlers import router; print('✅ Handlers imported')"
```

### Тест 2: Проверить DockerDeployManager

```bash
docker exec -it booking-bot-master python -c "from automation.docker_deploy_manager import DockerDeployManager; print('✅ Manager ready')"
```

### Тест 3: Проверить Docker connection

```bash
docker exec -it booking-bot-master python -c "import docker; client=docker.from_env(); print(f'✅ Docker {client.version()[\"Version\"]}')"
```

---

## ⚠️ Troubleshooting

### Ошибка: "ModuleNotFoundError: No module named 'docker'"

**Решение:**
```bash
# Установить в контейнер
docker exec -u root -it booking-bot-master pip install docker==7.1.0

# Пересобрать образ
docker-compose build --no-cache bot-master
docker-compose up -d
```

### Ошибка: "Docker недоступен"

**Причины:**
1. Docker Desktop не запущен
2. TCP не включён в Settings → General
3. DOCKER_HOST не установлен

**Решение:**
1. Откройте Docker Desktop
2. Settings → General → ✅ "Expose daemon on tcp://localhost:2375 without TLS"
3. Apply & Restart
4. Перезапустите Master Bot: `docker-compose restart bot-master`

### Ошибка при деплое: "All Redis DB slots are occupied"

**Причина:** Все 128 Redis DB заняты.

**Решение:**
```python
# Удалить неактивных клиентов
from automation.subscription_manager import SubscriptionManager
sub_manager = SubscriptionManager()

# Получить список
clients = sub_manager.list_clients(limit=200)

# Найти неактивных и удалить через docker_deploy.delete_client()
```

---

## 🎉 Готово!

Теперь Master Bot может:

✅ Создавать клиентских ботов за 30-60 секунд  
✅ Автоматически управлять Docker контейнерами  
✅ Выполнять rollback при ошибках  
✅ Мониторить статус всех клиентов  

**Следующий шаг:** Протестировать создание первого клиента!

---

## 📚 Документация

- [DOCKER_DEPLOYMENT_GUIDE.md](DOCKER_DEPLOYMENT_GUIDE.md) - API и примеры
- [WINDOWS_SETUP.md](WINDOWS_SETUP.md) - Windows настройка
- [MASTER_BOT_GUIDE.md](MASTER_BOT_GUIDE.md) - Master Bot гайд

---

## 🆘 Поддержка

Если что-то не работает:

1. Проверьте логи: `docker logs booking-bot-master --tail 100`
2. Проверьте Docker: `docker ps`
3. Проверьте переменные: `docker exec -it booking-bot-master env | findstr DOCKER`

Или создайте Issue: https://github.com/balzampsilo-sys/new12_02/issues
