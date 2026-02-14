# 🤖 Sales Bot - Автоматическая Продажа Подписок

## 📋 Описание

Sales Bot - это рекламный бот для автоматической продажи подписок на ботов для бизнеса.

### ✨ Основные возможности:

- 📱 **Интерактивное демо** - покажите потенциальным клиентам как работает бот
- 💰 **Автоматическая оплата** - через Telegram Stars (или ЮKassa/Stripe)
- 🤖 **Auto-deploy** - бот создается и запускается автоматически после оплаты
- 📊 **4 тарифных плана** - от 299₽/мес до 2499₽/год
- 🎁 **Пробный период** - 7 дней бесплатно
- 💬 **Поддержка** - интеграция с поддержкой

---

## 🚀 Быстрый старт

### 1. Создать бота в BotFather

```
/newbot
Название: Bot Sales Assistant
Username: YourSalesBot
```

Сохраните токен.

### 2. Настроить переменные окружения

```bash
cp .env.example sales_bot/.env
```

Редактировать `.env`:
```env
SALES_BOT_TOKEN=your_sales_bot_token_here
MASTER_BOT_API_URL=http://localhost:8000
SUPPORT_USERNAME=YourSupport
```

### 3. Установить зависимости

```bash
cd sales_bot
pip install -r requirements.txt
```

### 4. Запустить

```bash
python sales_bot.py
```

---

## 💳 Интеграция платежей

### Telegram Stars (рекомендуется)

**Преимущества:**
- ✅ Встроено в Telegram
- ✅ Нет комиссий для покупателей
- ✅ Мгновенное подтверждение
- ✅ Не требует настройки

**Как включить:**
1. Telegram Stars работают "из коробки"
2. Установите `currency="XTR"` в invoice
3. Готово!

### ЮKassa (для России)

```python
from yookassa import Configuration, Payment

Configuration.account_id = 'your_shop_id'
Configuration.secret_key = 'your_secret_key'

payment = Payment.create({
    "amount": {"value": "299.00", "currency": "RUB"},
    "confirmation": {"type": "redirect", "return_url": "https://..."},
    "capture": True
})
```

### Stripe (международный)

```python
import stripe

stripe.api_key = 'your_stripe_key'

checkout = stripe.checkout.Session.create(
    payment_method_types=['card'],
    line_items=[{...}],
    mode='payment'
)
```

---

## 📊 Тарифные планы

| Тариф | Период | Цена | Экономия | Цена/день |
|-------|--------|------|----------|----------|
| 🟢 **Starter** | 1 месяц | 299₽ | - | 10₽ |
| 🔵 **Standard** | 3 месяца | 799₽ | 98₽ | 9₽ |
| 🟣 **Business** | 6 месяцев | 1499₽ | 301₽ | 8₽ |
| ⭐ **Premium** | 1 год | 2499₽ | 1151₽ | 7₽ |

---

## 🎯 User Journey (Путь клиента)

```
1. Пользователь пишет @YourSalesBot
   ↓
2. Видит приветствие и возможности
   ↓
3. Нажимает "📱 Посмотреть демо"
   ↓
4. Взаимодействует с демо-версией
   ↓
5. Нажимает "💰 Купить подписку"
   ↓
6. Выбирает тариф (1м/3м/6м/12м)
   ↓
7. Вводит название бизнеса
   ↓
8. Оплачивает через Telegram Stars
   ↓
9. ✅ Получает готового бота за 2 минуты!
```

---

## 🔄 Автоматизация после оплаты

### Что происходит автоматически:

1. **Создание бота через BotFather API**
   - Username: `booking_{user_id}_bot`
   - Name: `{company_name} - Запись`

2. **Деплой через Master Bot**
   - Вызов Master Bot API
   - Выделение Redis DB
   - Запуск Docker контейнера

3. **Уведомление клиента**
   - Ссылка на бота
   - Инструкция по настройке
   - Контакты поддержки

---

## 🎨 Кастомизация

### Изменить тарифы:

```python
PRICING = {
    "1m": {
        "name": "Ваше название",
        "days": 30,
        "price": 299,  # Ваша цена
        "price_per_day": 10,
        "savings": 0
    },
    ...
}
```

### Изменить текст приветствия:

```python
@dp.message(CommandStart())
async def cmd_start(message: Message):
    welcome_text = """
    Ваш текст здесь
    """
```

---

## 📡 API интеграция с Master Bot

### Создание клиента:

```python
import requests

response = requests.post(
    f"{MASTER_BOT_API_URL}/api/clients",
    json={
        "admin_telegram_id": user_id,
        "company_name": company_name,
        "subscription_days": days,
        "paid_amount": amount
    },
    headers={"Authorization": f"Bearer {API_TOKEN}"}
)

result = response.json()
bot_username = result["bot_username"]
```

---

## 🐛 Отладка

### Проверить платежи:

```bash
# Логи платежей
tail -f logs/payments.log

# Тестовый платеж
python test_payment.py
```

### Проверить демо:

```bash
# Отправить /start боту
# Нажать "📱 Посмотреть демо"
```

---

## 📈 Метрики

### Отслеживаемые события:

- Количество /start
- Просмотров демо
- Начатых покупок
- Завершенных платежей
- Конверсия (просмотр → покупка)

### Интеграция с аналитикой:

```python
import analytics

analytics.track(user_id, 'demo_viewed')
analytics.track(user_id, 'purchase_started', {'plan': '1m'})
analytics.track(user_id, 'purchase_completed', {'amount': 299})
```

---

## 🔒 Безопасность

### Проверка платежей:

- ✅ Используем `pre_checkout_query` для валидации
- ✅ Проверяем `successful_payment` от Telegram
- ✅ Логируем все транзакции
- ✅ Храним payment_charge_id

### Защита от мошенничества:

```python
# Проверка повторных платежей
if await is_duplicate_payment(payment_id):
    return

# Лимит на количество ботов на пользователя
if await get_user_bots_count(user_id) >= MAX_BOTS_PER_USER:
    await message.answer("Превышен лимит ботов")
    return
```

---

## 🚀 Production Deploy

### Docker:

```bash
docker build -t sales-bot .
docker run -d --name sales-bot \
  --env-file .env \
  --restart unless-stopped \
  sales-bot
```

### Systemd:

```ini
[Unit]
Description=Sales Bot
After=network.target

[Service]
Type=simple
User=bot
WorkingDirectory=/opt/sales_bot
ExecStart=/usr/bin/python3 sales_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 📞 Поддержка

- 📱 Telegram: @YourSupport
- 📧 Email: support@example.com
- 📚 Docs: https://docs.example.com
- 💬 Chat: https://t.me/your_support_chat

---

## 📝 License

MIT License - используйте как хотите!
