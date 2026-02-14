# 🚀 Настройка ЮKassa для Sales Bot

## 📋 Шаг за шагом

### 1. Регистрация в ЮKassa

1. Перейдите на https://yookassa.ru/
2. Нажмите "Подключить ЮKassa"
3. Зарегистрируйтесь (нужны реквизиты ИП или компании)
4. Дождитесь модерации (обычно 1-2 дня)

### 2. Получить API ключи

1. Войдите в личный кабинет ЮKassa
2. Перейдите в раздел **"Настройки" → "API и Webhook"**
3. Скопируте:
   - **shopId** (идентификатор магазина)
   - **Секретный ключ** (secret key)

⚠️ **Важно:** Храните секретный ключ в безопасности!

### 3. Настроить .env файл

```bash
cd sales_bot
cp .env.example .env
nano .env
```

Вставьте:
```env
SALES_BOT_TOKEN=ваш_токен_бота
YOOKASSA_SHOP_ID=ваш_shop_id
YOOKASSA_SECRET_KEY=ваш_secret_key
WEBHOOK_URL=https://yourdomain.com
SUPPORT_USERNAME=YourSupport
```

### 4. Настроить Webhook в ЮKassa

1. В личном кабинете ЮKassa перейдите:
   **"Настройки" → "Уведомления" → "HTTP-уведомления"**

2. Включите уведомления

3. URL для уведомлений:
   ```
   https://yourdomain.com/webhook/yookassa
   ```

4. События для уведомлений:
   - ✅ `payment.succeeded` (платеж успешен)
   - ✅ `payment.canceled` (платеж отменен)
   - ✅ `payment.waiting_for_capture` (ожидание подтверждения)

5. Сохраните настройки

### 5. Получить домен и SSL сертификат

ЮKassa требует HTTPS для webhook.

#### Вариант A: Использовать Ngrok (для тестирования)

```bash
# Установить ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# Запустить туннель
ngrok http 8080
```

Используйте предоставленный HTTPS URL как `WEBHOOK_URL`.

#### Вариант B: Использовать свой домен (для продакшена)

```bash
# Установить Certbot для бесплатного SSL
sudo apt install certbot python3-certbot-nginx

# Получить SSL сертификат
sudo certbot --nginx -d yourdomain.com
```

### 6. Запустить Webhook сервер

```bash
cd sales_bot
python yookassa_webhook.py
```

Должно появиться:
```
🚀 Starting webhook server on port 8080
YooKassa Shop ID: 123456
Webhook endpoint: /webhook/yookassa
```

### 7. Запустить Sales Bot

В отдельном терминале:
```bash
cd sales_bot
python sales_bot_yookassa.py
```

---

## 🧪 Тестирование

### 1. Проверить webhook доступность

```bash
curl https://yourdomain.com/health
```

Ответ:
```json
{"status": "ok", "timestamp": "2026-02-14T16:42:00"}
```

### 2. Тестовый платеж

ЮKassa предоставляет тестовые карты:

**Успешный платеж:**
- Номер: `4111 1111 1111 1111`
- Месяц: любой будущий
- Год: любой будущий
- CVV: любой (например, 123)

**Отклоненный платеж:**
- Номер: `4444 4444 4444 4448`

### 3. Проверить логи

**Webhook логи:**
```bash
# В терминале где запущен yookassa_webhook.py
# Должны появляться уведомления от ЮKassa
```

**Bot логи:**
```bash
# В терминале где запущен sales_bot_yookassa.py
# Должны быть сообщения о создании платежей
```

---

## 🐳 Production Deploy

### Docker Compose

Создайте `docker-compose.yml`:

```yaml
version: '3.8'

services:
  sales-bot:
    build: .
    command: python sales_bot_yookassa.py
    env_file: .env
    restart: unless-stopped
    networks:
      - bot-network
  
  webhook:
    build: .
    command: python yookassa_webhook.py
    env_file: .env
    ports:
      - "8080:8080"
    restart: unless-stopped
    networks:
      - bot-network
  
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - /etc/letsencrypt:/etc/letsencrypt
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - webhook
    restart: unless-stopped
    networks:
      - bot-network

networks:
  bot-network:
    driver: bridge
```

### Nginx конфигурация

`nginx.conf`:
```nginx
events {
    worker_connections 1024;
}

http {
    upstream webhook {
        server webhook:8080;
    }
    
    server {
        listen 80;
        server_name yourdomain.com;
        return 301 https://$server_name$request_uri;
    }
    
    server {
        listen 443 ssl;
        server_name yourdomain.com;
        
        ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
        
        location /webhook/yookassa {
            proxy_pass http://webhook;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        location /health {
            proxy_pass http://webhook;
        }
        
        location /payment/success {
            proxy_pass http://webhook;
        }
    }
}
```

### Запустить

```bash
docker-compose up -d
```

---

## 🔒 Безопасность

### 1. Проверка подписи (рекомендуется)

Добавьте в `yookassa_webhook.py`:

```python
def verify_webhook_signature(body: str, signature: str) -> bool:
    """
    Проверить подпись webhook от ЮKassa
    """
    import hmac
    import hashlib
    
    expected_signature = hmac.new(
        YOOKASSA_SECRET_KEY.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)
```

### 2. Rate limiting

```python
from aiohttp import web
from aiolimiter import AsyncLimiter

rate_limiter = AsyncLimiter(10, 60)  # 10 запросов в минуту

@web.middleware
async def rate_limit_middleware(request, handler):
    async with rate_limiter:
        return await handler(request)
```

### 3. IP whitelist

Добавьте IP адреса ЮKassa в whitelist:
```python
YOOKASSA_IPS = [
    '185.71.76.0/27',
    '185.71.77.0/27',
    '77.75.153.0/25',
    '77.75.156.11',
    '77.75.156.35',
    '77.75.154.128/25'
]
```

---

## 📊 Мониторинг

### Логирование платежей

Добавьте в `yookassa_webhook.py`:

```python
import sqlite3

def log_payment(payment_id, user_id, amount, status):
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO payments (payment_id, user_id, amount, status, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (payment_id, user_id, amount, status, datetime.now()))
    conn.commit()
    conn.close()
```

### Алерты при ошибках

```python
async def send_admin_alert(message: str):
    ADMIN_IDS = [123456789]  # Ваши Telegram ID
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"⚠️ Алерт:\n{message}")
        except:
            pass
```

---

## ❓ Частые проблемы

### Webhook не получает уведомления

**Проверьте:**
1. ✅ URL доступен по HTTPS
2. ✅ SSL сертификат валиден
3. ✅ Webhook настроен в ЮKassa
4. ✅ Сервер запущен и слушает порт

**Тест:**
```bash
curl -X POST https://yourdomain.com/webhook/yookassa \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### Платеж создается но не обрабатывается

**Проверьте логи webhook:**
```bash
tail -f logs/webhook.log
```

**Убедитесь что payment.id сохранен в pending_payments**

### Timeout при создании бота

**Увеличьте timeout в Master Bot API:**
```python
timeout = aiohttp.ClientTimeout(total=300)  # 5 минут
```

---

## 📞 Поддержка

- 📚 Документация ЮKassa: https://yookassa.ru/docs/
- 💬 Техподдержка ЮKassa: support@yookassa.ru
- 📱 Telegram: @yookassa_support
