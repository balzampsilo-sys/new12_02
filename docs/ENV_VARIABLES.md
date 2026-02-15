# ⚡ Environment Variables Руководство

Этот документ объясняет **как переменные из .env файла передаются в контейнеры**.

---

## 🔑 Основной принцип

**В `.env` файле:**
```env
BOT_TOKEN_MASTER=1234567890:ABCdef...
BOT_TOKEN_SALES=0987654321:XYZabc...
BOT_TOKEN_CLIENT_001=1111111111:QWErty...
```

**В `docker-compose.yml` передаются как:**
```yaml
# Master Bot
environment:
  MASTER_BOT_TOKEN: ${BOT_TOKEN_MASTER}  # ← Передается как MASTER_BOT_TOKEN

# Sales Bot  
environment:
  SALES_BOT_TOKEN: ${BOT_TOKEN_SALES}    # ← Передается как SALES_BOT_TOKEN

# Client Bots
environment:
  BOT_TOKEN: ${BOT_TOKEN_CLIENT_001}     # ← Передается как BOT_TOKEN
```

**В коде (Python) читаются как:**
```python
# master_bot/master_bot.py
MASTER_BOT_TOKEN = os.getenv("MASTER_BOT_TOKEN")  # ← Читает MASTER_BOT_TOKEN

# sales_bot/sales_bot_yookassa.py
SALES_BOT_TOKEN = os.getenv("SALES_BOT_TOKEN")    # ← Читает SALES_BOT_TOKEN

# main.py (для клиентских ботов)
BOT_TOKEN = os.getenv("BOT_TOKEN")                 # ← Читает BOT_TOKEN
```

---

## 📊 Полная таблица соответствия

| **В .env файле** | **В docker-compose.yml** | **В контейнере** | **Entry Point** | **Назначение** |
|-------------------|------------------------------|---------------------|-----------------|---------------|
| `BOT_TOKEN_MASTER` | `MASTER_BOT_TOKEN: ${BOT_TOKEN_MASTER}` | `MASTER_BOT_TOKEN` | `master_bot/master_bot.py` | Master Bot токен |
| `BOT_TOKEN_SALES` | `SALES_BOT_TOKEN: ${BOT_TOKEN_SALES}` | `SALES_BOT_TOKEN` | `sales_bot/sales_bot_yookassa.py` | Sales Bot токен |
| `BOT_TOKEN_CLIENT_001` | `BOT_TOKEN: ${BOT_TOKEN_CLIENT_001}` | `BOT_TOKEN` | `main.py` | Client Bot токен |
| `ADMIN_IDS_MASTER` | `ADMIN_IDS: ${ADMIN_IDS_MASTER}` | `ADMIN_IDS` | `master_bot/master_bot.py` | Master Bot admins |
| `ADMIN_IDS_SALES` | н/д (Sales Bot не использует admin system) | - | - | - |
| `ADMIN_IDS_CLIENT_001` | `ADMIN_IDS: ${ADMIN_IDS_CLIENT_001}` | `ADMIN_IDS` | `main.py` | Client Bot admins |
| `POSTGRES_PASSWORD` | `${POSTGRES_PASSWORD}` | `POSTGRES_PASSWORD` | Все боты | PostgreSQL password |
| `YOOKASSA_SHOP_ID` | `YOOKASSA_SHOP_ID: ${YOOKASSA_SHOP_ID}` | `YOOKASSA_SHOP_ID` | `sales_bot/sales_bot_yookassa.py` | YooKassa Shop ID |
| `YOOKASSA_SECRET_KEY` | `YOOKASSA_SECRET_KEY: ${YOOKASSA_SECRET_KEY}` | `YOOKASSA_SECRET_KEY` | `sales_bot/sales_bot_yookassa.py` | YooKassa Secret |

---

## 📝 Пример .env файла

```env
# ========================================
# MASTER BOT (управление подписками)
# ========================================
BOT_TOKEN_MASTER=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS_MASTER=123456789,987654321

# ========================================
# SALES BOT (продажи через YooKassa)
# ========================================
BOT_TOKEN_SALES=0987654321:ZYXwvuTSRqponMLKjiHGFedcba
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=live_abcdefghijklmnopqrstuvwxyz
WEBHOOK_URL=https://yourdomain.com
SUPPORT_USERNAME=YourSupportBot

# ========================================
# CLIENT BOTS (боты бронирования для клиентов)
# ========================================
BOT_TOKEN_CLIENT_001=1111111111:QWErtyUIOPasdfGHJKLzxcvBNM
ADMIN_IDS_CLIENT_001=111111111,222222222

BOT_TOKEN_CLIENT_002=2222222222:ASDfghJKLqwerTYUIzxcvBNMop
ADMIN_IDS_CLIENT_002=333333333,444444444

# ========================================
# DATABASE
# ========================================
POSTGRES_PASSWORD=YourSecurePassword123!

# ========================================
# REDIS (Optional)
# ========================================
REDIS_PASSWORD=AnotherSecurePassword456!

# ========================================
# MONITORING (Optional)
# ========================================
SENTRY_ENABLED=false
SENTRY_DSN=https://your_sentry_dsn@sentry.io/project_id
SENTRY_DSN_MASTER=https://master_sentry_dsn@sentry.io/project_master
SENTRY_DSN_SALES=https://sales_sentry_dsn@sentry.io/project_sales
SENTRY_DSN_CLIENT_001=https://client001_sentry_dsn@sentry.io/project_client001

# ========================================
# TIMEZONE
# ========================================
TIMEZONE=Europe/Moscow

# ========================================
# DOCKER (for Master Bot autonomous deployment)
# ========================================
# Windows: включите Docker Desktop > Settings > General > Expose daemon on tcp://localhost:2375
DOCKER_HOST=tcp://host.docker.internal:2375  # Windows
# DOCKER_HOST=unix:///var/run/docker.sock     # Linux/Mac
```

---

## 🔍 Как проверить, что переменные передались правильно?

### Метод 1: Просмотр логов
```bash
# Master Bot
docker-compose logs bot-master | grep "BOT_TOKEN"
# Должно быть: ✅ BOT_TOKEN validated (если в коде есть логирование)

# Client Bot
docker-compose logs bot-client-001 | grep "BOT_TOKEN"
```

### Метод 2: Зайти в контейнер и проверить
```bash
# Master Bot
docker-compose exec bot-master env | grep "MASTER_BOT_TOKEN"
# Должно показать: MASTER_BOT_TOKEN=1234567890:ABCdef...

# Sales Bot
docker-compose exec bot-sales env | grep "SALES_BOT_TOKEN"
# Должно показать: SALES_BOT_TOKEN=0987654321:XYZabc...

# Client Bot
docker-compose exec bot-client-001 env | grep "BOT_TOKEN"
# Должно показать: BOT_TOKEN=1111111111:QWErty...
```

### Метод 3: Проверить через Python
```bash
# Зайти в контейнер
docker-compose exec bot-master python -c "import os; print('MASTER_BOT_TOKEN:', os.getenv('MASTER_BOT_TOKEN')[:20] + '...')"

# Вывод: MASTER_BOT_TOKEN: 1234567890:ABCdef...
```

---

## ⚠️ Частые ошибки

### Ошибка 1: «Неверный токен»

**Причина:** В `.env` указан `BOT_TOKEN=...` вместо `BOT_TOKEN_MASTER=...`

**Решение:** Проверьте таблицу соответствия выше и исправьте имя переменной.

### Ошибка 2: «Бот не запускается после добавления в docker-compose.yml»

**Причина:** В `docker-compose.yml` указано `BOT_TOKEN: ${BOT_TOKEN_CLIENT_001}`, но в `.env` переменная не добавлена.

**Решение:**
```env
# Добавьте в .env
BOT_TOKEN_CLIENT_001=your_token_here
ADMIN_IDS_CLIENT_001=your_admin_ids
```

### Ошибка 3: «.env файл не читается»

**Причина:** `.env` файл находится не в корневой директории проекта.

**Решение:**
```bash
# Проверьте структуру:
ls -la
# Должны увидеть:
# .env
# docker-compose.yml
# main.py
# ...

# Если .env нет:
cp .env.example .env
```

---

## 🔐 Безопасность

### Никогда не коммитьте .env в Git!

**Проверьте .gitignore:**
```bash
cat .gitignore | grep .env

# Должно быть:
# .env
# .env.local
# .env.*.local
```

### Используйте сильные пароли

❌ **Плохо:**
```env
POSTGRES_PASSWORD=123456
REDIS_PASSWORD=password
```

✅ **Хорошо:**
```env
POSTGRES_PASSWORD=Xk9$mP2nQ#7vL!wR@5tY
REDIS_PASSWORD=A8#bN4pT$6dK!xC@9mZ
```

### Production: используйте Docker Secrets

Вместо `.env` файла используйте:
- Docker Swarm secrets
- Kubernetes secrets
- HashiCorp Vault
- AWS Secrets Manager

---

## 📚 Дополнительные ресурсы

- [README.md](../README.md) - Общий обзор
- [DEPLOYMENT.md](../DEPLOYMENT.md) - Руководство по развертыванию
- [.env.example](../.env.example) - Пример конфигурации
- [docker-compose.yml](../docker-compose.yml) - Docker Compose конфигурация
