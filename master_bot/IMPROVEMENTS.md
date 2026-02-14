# 🚀 MASTER BOT - НОВЫЕ УЛУЧШЕНИЯ

## 🎉 Что нового?

### 1. ✅ **REST API для Sales Bot** (`api_server.py`)
### 2. ✅ **Автоматический мониторинг подписок** (`subscription_monitor.py`)
### 3. ✅ **Уведомления клиентам и админам**
### 4. ✅ **Авто-остановка истекших ботов**

---

## 📡 REST API СЕРВЕР

### Назначение
Позволяет **Sales Bot автоматически создавать клиентов** после оплаты.

### Настройка

**1. Обновить `.env`:**
```bash
cd master_bot
cp .env.example .env
nano .env
```

**Добавьте:**
```bash
# REST API Settings
MASTER_API_PORT=8000
MASTER_API_TOKEN=super_secret_token_change_this_123456
```

**⚠️ ВАЖНО:** Измените `MASTER_API_TOKEN` на сложный токен!

**2. Установить зависимости:**
```bash
pip install fastapi uvicorn pydantic
```

**3. Запустить API сервер:**
```bash
python3 api_server.py
```

**Вы увидите:**
```
🚀 Master Bot API starting...
📡 Listening on http://0.0.0.0:8000
📚 Docs: http://localhost:8000/docs
💾 Database: /root/new12_02/subscriptions.db
```

---

### 📚 API Эндпоинты

#### **1. Проверка работы**
```bash
curl http://localhost:8000/
```

**Ответ:**
```json
{
  "service": "Master Bot API",
  "version": "1.0.0",
  "status": "running",
  "timestamp": "2026-02-14T19:00:00"
}
```

---

#### **2. Health Check**
```bash
curl http://localhost:8000/health
```

**Ответ:**
```json
{
  "status": "healthy",
  "database": "ok",
  "timestamp": "2026-02-14T19:00:00"
}
```

---

#### **3. Создать клиента** ⭐ **ОСНОВНОЙ**

```bash
curl -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "bot_token": "123456789:ABCdefGHI...",
    "admin_telegram_id": 987654321,
    "company_name": "Салон красоты Анна",
    "subscription_days": 30,
    "paid_amount": 299.0,
    "payment_id": "pay_123abc"
  }'
```

**Ответ:**
```json
{
  "success": true,
  "client_id": "550e8400-e29b-41d4-a716-446655440000",
  "bot_username": "booking_bot_0",
  "redis_db": 0,
  "container_name": "booking_bot_0",
  "subscription_expires_at": "2026-03-16",
  "message": "Bot deployed successfully for Салон красоты Анна"
}
```

---

#### **4. Продлить подписку**

```bash
curl -X POST http://localhost:8000/api/clients/{client_id}/extend \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "550e8400-e29b-41d4-a716-446655440000",
    "days": 90,
    "amount": 799.0,
    "payment_id": "pay_456def"
  }'
```

**Ответ:**
```json
{
  "success": true,
  "client_id": "550e8400-...",
  "subscription_expires_at": "2026-06-14",
  "message": "Subscription extended by 90 days"
}
```

---

#### **5. Получить статус клиента**

```bash
curl http://localhost:8000/api/clients/{client_id} \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

**Ответ:**
```json
{
  "client_id": "550e8400-...",
  "company_name": "Салон красоты Анна",
  "subscription_status": "active",
  "subscription_expires_at": "2026-03-16T00:00:00",
  "redis_db": 0,
  "container_name": "booking_bot_0",
  "bot_username": "booking_bot_0"
}
```

---

#### **6. Статистика**

```bash
curl http://localhost:8000/api/stats \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

**Ответ:**
```json
{
  "total_clients": 10,
  "active_clients": 8,
  "suspended_clients": 2,
  "trial_clients": 0,
  "available_redis_dbs": 6,
  "monthly_revenue": 7990.0,
  "timestamp": "2026-02-14T19:00:00"
}
```

---

### 🛡️ Безопасность API

**Авторизация:**
Все эндпоинты (кроме `/` и `/health`) требуют Bearer токен:

```bash
Authorization: Bearer YOUR_SECRET_TOKEN
```

**Логирование:**
- ✅ Все запросы логируются
- ❌ Неудачные попытки авторизации записываются

**Rate Limiting:**
Рекомендуется добавить nginx с rate limiting:
```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
```

---

## 🔍 МОНИТОРИНГ ПОДПИСОК

### Назначение
Автоматически **проверяет и останавливает** ботов с истекшей подпиской.

### Функции

1. **Проверка каждый час** (настраивается)
2. **Уведомления клиентам:**
   - 🚨 **7 дней до истечения**
   - ⚠️ **3 дня до истечения**
   - ⏰ **Сегодня истекает**
3. **Авто-остановка** истекших ботов
4. **Сводка админам**

---

### Настройка

**1. Обновить `.env`:**
```bash
# Проверять каждый час (3600 секунд)
SUBSCRIPTION_CHECK_INTERVAL=3600

# Или каждые 6 часов
# SUBSCRIPTION_CHECK_INTERVAL=21600
```

**2. Запустить монитор:**
```bash
python3 subscription_monitor.py
```

**Вы увидите:**
```
🚀 Subscription Monitor starting...
⏰ Check interval: 3600 seconds (1 hours)
📄 Database: /root/new12_02/subscriptions.db
🔍 Starting subscription check...
📊 Subscription check: Expired: 0, Today: 1, 3 days: 2, 7 days: 3
✅ Subscription check completed
⏸️ Sleeping for 3600 seconds...
```

---

### 📨 Примеры уведомлений

#### **Клиенту (за 7 дней):**
```
🚨 ПОДПИСКА ИСТЕКАЕТ ЧЕРЕЗ 7 ДНЕЙ

🏢 Компания: Салон красоты Анна
📅 Истекает: 2026-02-21
⌛ Осталось: 7 дней

💳 Чтобы продлить подписку:
1. Напишите нам в поддержку
2. Или оплатите через бот

❗ Без продления бот будет остановлен!
```

#### **Клиенту (после истечения):**
```
❌ ПОДПИСКА ИСТЕКЛА

🏢 Компания: Салон красоты Анна

🚫 Ваш бот был остановлен.

🔄 Чтобы возобновить работу:
1. Продлите подписку
2. Напишите в поддержку

💾 Все ваши данные сохранены!
```

#### **Админам (сводка):**
```
📊 СВОДКА ПО ПОДПИСКАМ

❌ Истекли: 2
   • Салон красоты Анна
   • Массажный кабинет

⏰ Истекают сегодня: 1
   • Ногтевая студия

⚠️ Истекают через 3 дня: 3
Истекают через 7 дней: 5
```

---

## 🐞 ЗАПУСК В PRODUCTION

### Вариант 1: Screen/Tmux

**1. Запустить Master Bot:**
```bash
screen -S master_bot
cd /root/new12_02/master_bot
python3 master_bot.py
# Ctrl+A, D (отключиться)
```

**2. Запустить API Server:**
```bash
screen -S api_server
cd /root/new12_02/master_bot
python3 api_server.py
# Ctrl+A, D
```

**3. Запустить Subscription Monitor:**
```bash
screen -S sub_monitor
cd /root/new12_02/master_bot
python3 subscription_monitor.py
# Ctrl+A, D
```

**Просмотреть активные сессии:**
```bash
screen -ls
# Вернуться в сессию:
screen -r master_bot
```

---

### Вариант 2: Systemd Сервисы

**1. Создать `master_bot.service`:**
```bash
sudo nano /etc/systemd/system/master_bot.service
```

```ini
[Unit]
Description=Master Bot - Client Management
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/new12_02/master_bot
ExecStart=/usr/bin/python3 master_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**2. Создать `api_server.service`:**
```bash
sudo nano /etc/systemd/system/master_api.service
```

```ini
[Unit]
Description=Master Bot API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/new12_02/master_bot
ExecStart=/usr/bin/python3 api_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**3. Создать `subscription_monitor.service`:**
```bash
sudo nano /etc/systemd/system/subscription_monitor.service
```

```ini
[Unit]
Description=Subscription Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/new12_02/master_bot
ExecStart=/usr/bin/python3 subscription_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**4. Запустить все сервисы:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable master_bot api_server subscription_monitor
sudo systemctl start master_bot api_server subscription_monitor
```

**Проверить статус:**
```bash
sudo systemctl status master_bot
sudo systemctl status master_api
sudo systemctl status subscription_monitor
```

**Просмотреть логи:**
```bash
sudo journalctl -u master_bot -f
sudo journalctl -u master_api -f
sudo journalctl -u subscription_monitor -f
```

---

## 🔗 ИНТЕГРАЦИЯ С SALES BOT

### В Sales Bot добавьте:

**1. Обновить `.env`:**
```bash
# В sales_bot/.env
MASTER_BOT_API_URL=http://localhost:8000
MASTER_API_TOKEN=super_secret_token_change_this_123456
```

**2. Добавить функцию создания клиента:**

```python
import aiohttp
import os

MASTER_BOT_API_URL = os.getenv("MASTER_BOT_API_URL")
MASTER_API_TOKEN = os.getenv("MASTER_API_TOKEN")

async def create_client_via_api(
    bot_token: str,
    admin_telegram_id: int,
    company_name: str,
    subscription_days: int,
    paid_amount: float,
    payment_id: str
):
    """Создать клиента через Master Bot API"""
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{MASTER_BOT_API_URL}/api/clients",
            json={
                "bot_token": bot_token,
                "admin_telegram_id": admin_telegram_id,
                "company_name": company_name,
                "subscription_days": subscription_days,
                "paid_amount": paid_amount,
                "payment_id": payment_id
            },
            headers={
                "Authorization": f"Bearer {MASTER_API_TOKEN}",
                "Content-Type": "application/json"
            }
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                error = await response.text()
                raise Exception(f"API Error: {error}")
```

**3. Использовать в обработчике оплаты:**

```python
@dp.message(F.successful_payment)
async def process_successful_payment(message: Message, state: FSMContext):
    payment = message.successful_payment
    data = await state.get_data()
    
    # Создать бота через API
    result = await create_client_via_api(
        bot_token="TODO: получить от BotFather API",
        admin_telegram_id=message.from_user.id,
        company_name=data['company_name'],
        subscription_days=data['subscription_days'],
        paid_amount=payment.total_amount / 100,
        payment_id=payment.telegram_payment_charge_id
    )
    
    await message.answer(
        f"🎉 Ваш бот готов!\n\n"
        f"🤖 @{result['bot_username']}\n"
        f"🏢 {data['company_name']}\n"
        f"📅 Подписка до: {result['subscription_expires_at']}"
    )
```

---

## 📊 МОНИТОРИНГ

### Prometheus Метрики (опционально)

Добавьте в `api_server.py`:

```python
from prometheus_client import Counter, Gauge, generate_latest

client_creation_counter = Counter('clients_created_total', 'Total clients created')
active_clients_gauge = Gauge('active_clients', 'Number of active clients')

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")
```

---

## ❓ FAQ

### Q: Можно ли изменить интервал проверки?
**A:** Да! Измените `SUBSCRIPTION_CHECK_INTERVAL` в `.env`

### Q: Как добавить еще одного админа?
**A:** Добавьте его ID в `ADMIN_IDS` через запятую

### Q: Что если API сервер упал?
**A:** Клиентские боты продолжат работать! API нужен только для создания новых.

### Q: Как проверить что API работает?
**A:** `curl http://localhost:8000/health`

---

## ✅ ЧЕК-ЛИСТ НАСТРОЙКИ

- [ ] Обновил `.env` с API_TOKEN
- [ ] Установил `fastapi` и `uvicorn`
- [ ] Запустил `api_server.py`
- [ ] Проверил health check
- [ ] Запустил `subscription_monitor.py`
- [ ] Настроил systemd сервисы
- [ ] Обновил Sales Bot с API интеграцией
- [ ] Протестировал создание клиента
- [ ] Проверил уведомления

---

## 🎉 РЕЗЮМЕ

✅ **REST API** - Sales Bot может автоматически создавать клиентов  
✅ **Мониторинг** - автоматическая остановка истекших ботов  
✅ **Уведомления** - клиенты и админы всегда в курсе  
✅ **Production-ready** - systemd, авто-перезапуск, логи  

**Теперь Master Bot полностью автоматизирован!** 🚀
