# 🤖 AUTOMATION GUIDE: Полная автоматизация

## 🎯 Обзор

Система **полностью автоматизирована**:

✅ **Больше не нужно** вручную:
- Отслеживать Redis DB номера  
- Создавать директории
- Писать .env файлы
- Проверять подписки
- Останавливать боты

✅ **Автоматически**:
- Выделение Redis DB (0-15)
- Деплой новых клиентов
- Проверка подписок (cron)
- Остановка просроченных ботов
- Учет платежей

---

## 🛠️ Архитектура

```
┌──────────────────────────────────────────────┐
│         SUBSCRIPTION MANAGER (subscriptions.db)       │
│  - Учет клиентов                                  │
│  - Авто Redis DB выделение                        │
│  - Подписки и платежи                          │
└──────────────────────────────────────────────┘
          │                    │
          ▼                    ▼
┌──────────────────────┐  ┌─────────────────────────┐
│ DEPLOYMENT MANAGER  │  │ SUBSCRIPTION CHECKER │
│ - Автодеплой        │  │ - Cron job (1ч)      │
│ - Docker setup      │  │ - Автоостановка     │
│ - .env генерация    │  │ - Уведомления       │
└──────────────────────┘  └─────────────────────────┘
```

---

## ⚡ Быстрый старт

### 👥 Добавление нового клиента

**Раньше (вручную):**
```bash
# 1. Смотреть какие Redis DB заняты
# 2. Выбирать свободный номер
# 3. Создать директорию
# 4. Написать .env
# 5. Запустить Docker
# 6. Записать в таблицу Redis DB
./scripts/deploy_client.sh client_001 "TOKEN" 123456 0
```

**Теперь (автоматически):**
```bash
# Одна команда - все автоматически!
python3 automation/deploy_manager.py \
  "123456:ABCdef" \
  987654321 \
  --company "Салон красоты"

# Автоматически:
# ✅ Найден свободный Redis DB (0)
# ✅ Создана директория clients/xxxx
# ✅ Сгенерирован .env
# ✅ Собран Docker image
# ✅ Запущен бот
# ✅ Зарегистрирован в subscriptions.db
```

---

## 📊 Subscription Manager API

### Инициализация

```python
from automation.subscription_manager import SubscriptionManager

manager = SubscriptionManager(db_path="subscriptions.db")
```

### Добавление клиента

```python
# Автоматическое выделение Redis DB!
client_id, redis_db = manager.add_client(
    bot_token="123456:ABCdef",
    admin_telegram_id=987654321,
    company_name="Салон красоты",
    subscription_days=30
)

print(f"✅ Client ID: {client_id}")
print(f"📊 Redis DB: {redis_db}")  # Автоматически найденный!
```

### Получение информации

```python
# Получить клиента
client = manager.get_client(client_id)
print(client['company_name'])
print(client['redis_db'])
print(client['subscription_expires_at'])

# Список всех активных
active_clients = manager.list_clients(status='active')

# Статистика
stats = manager.get_statistics()
print(f"Всего клиентов: {stats['total_clients']}")
print(f"Активных: {stats['active_clients']}")
print(f"Свободно Redis DB: {stats['available_redis_dbs']}")
```

### Управление подписками

```python
# Проверить истекшие
expired = manager.check_expired_subscriptions()

# Приостановить
manager.suspend_client(client_id, reason="неоплата")

# Возобновить (после оплаты)
manager.reactivate_client(client_id, extend_days=30)
```

### Платежи

```python
# Добавить платеж и автоматически продлить
manager.add_payment(
    client_id=client_id,
    amount=1500.0,
    currency="RUB",
    payment_method="карта",
    transaction_id="TXN123456",
    notes="Оплата за февраль 2026"
)
# ✅ Подписка автоматически продлена на 30 дней
```

---

## 🔄 Автоматическая проверка подписок

### Ручной запуск

```bash
python3 automation/check_subscriptions.py

# Вывод:
# ==========================================================
# 🔍 SUBSCRIPTION CHECK - 2026-02-14 15:00:00
# ==========================================================
#
# ⚠️ Найдено истекших подписок: 2
#
# 🗓️ Клиент: Салон красоты
#    ID: xxxx-yyyy-zzzz
#    Истекло: 2026-02-13 00:00:00
#    Container: bot-client-xxxx
# ✅ Бот остановлен
#
# ==========================================================
# ✅ Остановлено: 2
# ==========================================================
```

### Cron Job (автоматическая проверка)

```bash
# Открыть crontab
crontab -e

# Добавить:

# Проверка каждый час
0 * * * * cd /path/to/new12_02 && python3 automation/check_subscriptions.py >> logs/subscription_check.log 2>&1

# Или каждые 15 минут
*/15 * * * * cd /path/to/new12_02 && python3 automation/check_subscriptions.py >> logs/subscription_check.log 2>&1

# Или 1 раз в день в 00:00
0 0 * * * cd /path/to/new12_02 && python3 automation/check_subscriptions.py >> logs/subscription_check.log 2>&1
```

---

## 💻 Примеры использования

### 1️⃣ Деплой нового клиента

```python
from automation.deploy_manager import DeploymentManager

deployer = DeploymentManager()

result = deployer.deploy_client(
    bot_token="123456:ABCdefGHI",
    admin_telegram_id=987654321,
    company_name="Салон красоты",
    bot_username="beauty_salon_bot",
    subscription_days=30
)

if result['success']:
    print(f"✅ Client ID: {result['client_id']}")
    print(f"📊 Redis DB: {result['redis_db']}")
    print(f"🐳 Container: {result['container_name']}")
else:
    print(f"❌ Error: {result['error']}")
```

### 2️⃣ Проверка статистики

```python
from automation.subscription_manager import SubscriptionManager

manager = SubscriptionManager()
stats = manager.get_statistics()

print("""  
📊 СТАТИСТИКА
================
Всего клиентов: {total}
Активных: {active}
Приостановлено: {suspended}
Свободно Redis DB: {available_db}
Доход за месяц: {revenue} руб.
""".format(
    total=stats['total_clients'],
    active=stats['active_clients'],
    suspended=stats['suspended_clients'],
    available_db=stats['available_redis_dbs'],
    revenue=stats['monthly_revenue']
))
```

### 3️⃣ Обработка платежа

```python
def process_payment(client_id: str, amount: float, transaction_id: str):
    """Webhook от платежной системы"""
    manager = SubscriptionManager()
    
    # Добавить платеж
    manager.add_payment(
        client_id=client_id,
        amount=amount,
        payment_method="online",
        transaction_id=transaction_id
    )
    
    # Продлить подписку и запустить бота
    client = manager.get_client(client_id)
    
    # Запустить контейнер
    import subprocess
    subprocess.run(["docker", "start", client['container_name']])
    manager.update_container_status(client_id, running=True)
    
    print(f"✅ Подписка продлена, бот запущен")
```

---

## 🔧 Полезные команды

### Просмотр всех клиентов

```python
from automation.subscription_manager import SubscriptionManager

manager = SubscriptionManager()
clients = manager.list_clients(limit=100)

for client in clients:
    print(f"""
    🏪 {client['company_name']}
       Status: {client['subscription_status']}
       Redis DB: {client['redis_db']}
       Expires: {client['subscription_expires_at']}
       Container: {client['container_name']}
    """)
```

### Поиск клиента

```bash
# По имени
sqlite3 subscriptions.db "SELECT * FROM clients WHERE company_name LIKE '%Салон%'"

# По Telegram ID
sqlite3 subscriptions.db "SELECT * FROM clients WHERE admin_telegram_id = 987654321"

# По Redis DB
sqlite3 subscriptions.db "SELECT * FROM clients WHERE redis_db = 0"
```

### Вручное управление

```bash
# Остановить клиента
python3 -c "
from automation.subscription_manager import SubscriptionManager
manager = SubscriptionManager()
manager.suspend_client('client-id-here')
print('✅ Client suspended')
"

# Возобновить клиента
python3 -c "
from automation.subscription_manager import SubscriptionManager
manager = SubscriptionManager()
manager.reactivate_client('client-id-here', extend_days=30)
print('✅ Client reactivated')
"
```

---

## 🌐 Web Dashboard (опционально)

### Концепция Flask панели

```python
# dashboard.py
from flask import Flask, render_template, jsonify
from automation.subscription_manager import SubscriptionManager
import subprocess

app = Flask(__name__)
manager = SubscriptionManager()

@app.route("/")
def dashboard():
    """ Главная страница """
    stats = manager.get_statistics()
    clients = manager.list_clients(limit=50)
    return render_template("dashboard.html", stats=stats, clients=clients)

@app.route("/api/clients")
def api_clients():
    """ API: список клиентов """
    clients = manager.list_clients()
    return jsonify(clients)

@app.route("/api/client/<client_id>/stop", methods=["POST"])
def api_stop_client(client_id):
    """ API: остановить клиента """
    client = manager.get_client(client_id)
    subprocess.run(["docker", "stop", client['container_name']])
    manager.update_container_status(client_id, running=False)
    return jsonify({"success": True})

@app.route("/api/client/<client_id>/start", methods=["POST"])
def api_start_client(client_id):
    """ API: запустить клиента """
    client = manager.get_client(client_id)
    subprocess.run(["docker", "start", client['container_name']])
    manager.update_container_status(client_id, running=True)
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
```

**Запуск:**
```bash
pip install flask
python3 dashboard.py

# Открыть: http://localhost:5000
```

---

## 🛡️ Защита subscriptions.db

```bash
# Резервная копия каждый день
0 0 * * * cp /path/to/subscriptions.db /path/to/backups/subscriptions_$(date +\%Y\%m\%d).db

# Удаление старых бэкапов (>30 дней)
find /path/to/backups -name "subscriptions_*.db" -mtime +30 -delete
```

---

## 🎉 Резюме

✅ **Теперь все автоматически:**

| Задача | Раньше | Сейчас |
|-------|---------|--------|
| Redis DB | Вручную отслеживать | ✅ Авто |
| Деплой | 10+ шагов | ✅ 1 команда |
| Подписки | Вручную проверять | ✅ Cron job |
| Остановка ботов | Вручную | ✅ Авто |
| Платежи | Excel/бумага | ✅ БД |
| Учет | В голове | ✅ БД + API |

**Готово к использованию!** 🚀
