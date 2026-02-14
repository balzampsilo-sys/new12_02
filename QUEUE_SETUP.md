# 🚀 Queue-Based Deployment Setup

## 🎯 Архитектура

```
┌─────────────────┐
│   Master Bot     │──> Создаёт задачи в Redis Queue
│  (in Docker)     │
└─────────────────┘
         │
         ↓
┌─────────────────┐
│  Redis Queue     │    master_bot:deploy_queue
│  (in Docker)     │    [task1, task2, task3...]
└─────────────────┘
         │
         ↓
┌─────────────────┐
│ Deploy Worker   │──> Читает задачи, запускает docker-compose
│  (on HOST)       │
└─────────────────┘
         │
         ↓
┌─────────────────┐
│ Client Bots     │    bot-client-xxx1
│ (in Docker)     │    bot-client-xxx2
└─────────────────┘    bot-client-xxx3...
```

---

## 🛠️ Изменения в master_bot.py

В функции `process_confirmation` заменить:

### ❌ **Старый код (прямой деплой):**
```python
result = deploy_manager.deploy_client(
    bot_token=data['bot_token'],
    admin_telegram_id=data['admin_telegram_id'],
    company_name=data['company_name']
)
```

### ✅ **Новый код (через очередь):**
```python
from deploy_queue import DeployQueue

# В начале файла, после инициализации sub_manager:
deploy_queue = DeployQueue(
    redis_host=os.getenv("REDIS_HOST", "redis"),
    redis_port=int(os.getenv("REDIS_PORT", "6379")),
    redis_db=int(os.getenv("REDIS_DB", "0")),
    key_prefix=os.getenv("REDIS_KEY_PREFIX", "master_bot:")
)

# В функции process_confirmation:
if not deploy_queue.is_available():
    await message.answer(
        "❌ Redis недоступен. Обратитесь к техподдержке.",
        reply_markup=main_menu_keyboard()
    )
    await state.clear()
    return

# Добавить задачу в очередь
task_id = deploy_queue.add_deploy_task(
    bot_token=data['bot_token'],
    admin_telegram_id=data['admin_telegram_id'],
    company_name=data['company_name'],
    created_by=message.from_user.id
)

if not task_id:
    await message.answer(
        "❌ Не удалось добавить задачу. Попробуйте ещё раз.",
        reply_markup=main_menu_keyboard()
    )
    await state.clear()
    return

# Уведомить о постановке в очередь
await processing_msg.delete()
await message.answer(
    f"✅ **ЗАДАЧА ДОБАВЛЕНА В ОЧЕРЕДЬ**\n\n"
    f"🏢 Компания: **{data['company_name']}**\n"
    f"🆔 Task ID: `{task_id}`\n\n"
    f"⏳ Деплой начнётся в течение 1-2 минут.\n"
    f"🔔 Вы получите уведомление о результате.",
    parse_mode="Markdown",
    reply_markup=main_menu_keyboard()
)
```

---

## 📝 Инструкция по установке

### **1️⃣ Установить зависимости на хосте:**

```bash
# Перейти в папку проекта
cd /path/to/new12_02

# Установить Python зависимости
pip3 install redis aiogram python-dotenv
```

---

### **2️⃣ Проверить что Redis работает:**

```bash
# Проверить что Redis запущен в Docker
docker-compose ps redis

# Если не запущен:
docker-compose up -d redis

# Проверить доступ:
redis-cli -h localhost -p 6379 ping
# Должно вернуть: PONG
```

---

### **3️⃣ Запустить Deploy Worker на хосте:**

#### **Вариант A: Вручную (для теста)**

```bash
# Запустить в отдельном терминале
cd /path/to/new12_02
python3 automation/deploy_worker.py

# Вы увидите:
# 🚀 Deploy Worker started
# ✅ WORKER READY - Waiting for deploy tasks...
```

#### **Вариант B: Через systemd (для продакшена)**

```bash
# Создать systemd service
sudo nano /etc/systemd/system/deploy-worker.service
```

Содержимое файла:
```ini
[Unit]
Description=Booking Bot Deploy Worker
After=network.target docker.service redis.service
Requires=docker.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/new12_02
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 /path/to/new12_02/automation/deploy_worker.py
Restart=always
RestartSec=10
StandardOutput=append:/path/to/new12_02/logs/deploy_worker.log
StandardError=append:/path/to/new12_02/logs/deploy_worker_error.log

[Install]
WantedBy=multi-user.target
```

Запустить:
```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable deploy-worker

# Запустить
sudo systemctl start deploy-worker

# Проверить статус
sudo systemctl status deploy-worker

# Посмотреть логи
sudo journalctl -u deploy-worker -f
```

---

### **4️⃣ Обновить Master Bot:**

```bash
# Получить последние изменения
git pull

# Пересобрать Master Bot с новым кодом
docker-compose build bot-master

# Перезапустить
docker-compose restart bot-master

# Проверить логи
docker-compose logs -f bot-master
```

---

## 🧪 Тестирование

### **1. Проверить что Worker работает:**

В логах Worker должно быть:
```
🚀 Deploy Worker started
✅ Connected to Redis: localhost:6379/0
============================================================
✅ WORKER READY - Waiting for deploy tasks...
============================================================
```

### **2. Добавить тестового клиента:**

1. Откройте Master Bot в Telegram
2. Нажмите "➕ Добавить клиента"
3. Введите данные

### **3. Наблюдать за процессом:**

**Master Bot лог:**
```
✅ Task added to queue: abc123-def456... for Тестовый салон
```

**Deploy Worker лог:**
```
📥 New task received from master_bot:deploy_queue
🚀 Deploying bot for: Тестовый салон
...
✅ Deploy successful: client_id_xxx
✅ Notification sent to 123456789
✅ Task completed. Waiting for next task...
```

**В Telegram клиенту придёт:**
```
✅ БОТ УСПЕШНО РАЗВЕРНУТ!

🏢 Компания: Тестовый салон
🆔 Client ID: abc12345
💾 Redis DB: 1
🐳 Container: bot-client-abc12345
...
```

---

## 🐛 Отладка

### **Проблема: Worker не видит Redis**

```bash
# Проверить что Redis доступен с хоста
redis-cli -h localhost -p 6379 ping

# Если "Connection refused":
docker-compose up -d redis

# Проверить ports в docker-compose.yml:
ports:
  - "6379:6379"  # Должно быть!
```

### **Проблема: Master Bot не добавляет задачи**

```bash
# Проверить логи Master Bot
docker-compose logs bot-master | grep -i redis

# Должно быть:
# ✅ Deploy Queue connected to Redis: redis:6379/0
```

### **Проблема: Worker падает при деплое**

```bash
# Проверить что docker-compose доступен
which docker-compose

# Проверить что docker работает
docker ps

# Проверить что сеть bot-network существует
docker network ls | grep bot-network

# Создать если нет:
docker network create bot-network
```

---

## ✅ Преимущества этой архитектуры

1. **Безопасность** - Master Bot не имеет прямого доступа к Docker
2. **Масштабируемость** - можно запустить несколько Workers
3. **Надёжность** - если Worker упадёт, задачи останутся в очереди
4. **Мониторинг** - можно видеть состояние каждой задачи
5. **Асинхронность** - Master Bot не блокируется на время деплоя

---

## 📊 Мониторинг

```bash
# Посмотреть количество задач в очереди
redis-cli -h localhost -p 6379 LLEN master_bot:deploy_queue

# Посмотреть последнюю задачу (без удаления)
redis-cli -h localhost -p 6379 LINDEX master_bot:deploy_queue -1

# Посмотреть все результаты
redis-cli -h localhost -p 6379 KEYS "master_bot:deploy_results:*"
```

---

**Готово к работе! 🚀**
