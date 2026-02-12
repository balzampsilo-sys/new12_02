# 🐳 Docker Deployment Guide

## 🚀 Quick Start

### 1️⃣ Первый запуск

```bash
# Clone repository
git clone https://github.com/balzampsilo-sys/new12_02.git
cd new12_02

# Create .env file
cp .env.example .env
nano .env  # Добавьте BOT_TOKEN и ADMIN_IDS

# Build and start
docker-compose up -d --build
```

### 2️⃣ После обновления кода

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

---

## ✅ ОБЯЗАТЕЛЬНО ПОСЛЕ ОБНОВЛЕНИЯ i18n!

**Критично:** После добавления системы локализации нужно:

```bash
# Остановить и удалить старый контейнер
docker-compose down

# Пересобрать образ (установить PyYAML)
docker-compose build --no-cache

# Запустить
docker-compose up -d

# Проверить логи
docker-compose logs -f bot
```

**Почему нужно `--no-cache`?**
- Добавлена новая зависимость `PyYAML==6.0.2`
- Docker может использовать старый кэш `requirements.txt`
- Без `--no-cache` бот упадет с ошибкой `ModuleNotFoundError: No module named 'yaml'`

---

## 🔍 Проверка работы

### Статус контейнеров
```bash
docker-compose ps
```

**Ожидаемый вывод:**
```
NAME                  STATUS         PORTS
booking-bot           Up (healthy)   -
booking-bot-redis     Up (healthy)   6379->6379/tcp
```

### Логи бота
```bash
docker-compose logs -f bot
```

**Ожидаемые сообщения:**
```
✅ HybridTextManager initialized
✅ Loaded 150 YAML categories for 'ru'
✅ Database initialized with migrations
✅ Bot started successfully
✅ Features: ... Hybrid i18n (YAML + DB with Admin UI)
```

### Проверка i18n системы
```bash
# Проверить наличие locales в контейнере
docker exec booking-bot ls -la /app/locales

# Проверить YAML файл
docker exec booking-bot cat /app/locales/ru.yaml | head -20

# Проверить установку PyYAML
docker exec booking-bot pip show PyYAML
```

---

## 💾 Volumes

### Что монтируется:

```yaml
volumes:
  - ./data:/app/data           # 💾 БД и данные
  - ./backups:/app/backups     # 📥 Бэкапы
  - ./logs:/app/logs           # 📝 Логи
  - ./locales:/app/locales     # 🌍 i18n YAML (✅ NEW!)
```

### Зачем `./locales` как volume?

✅ **Hot-reload YAML** - редактируйте `locales/ru.yaml` на хосте, перезагружайте через Admin UI

```bash
# Отредактировать YAML на хосте
nano locales/ru.yaml

# В боте: /admin → 📝 Редактор текстов → 🔄 Перезагрузить YAML
# Или подождать 5 минут (cache TTL)
```

❌ **Без volume**: нужна пересборка образа при каждом изменении YAML

---

## 🛠️ Обслуживание

### Перезапуск
```bash
docker-compose restart bot
```

### Остановка
```bash
docker-compose down
```

### Очистка (удаление всех данных)
```bash
docker-compose down -v  # Удалит Redis volume!
```

### Просмотр ресурсов
```bash
docker stats booking-bot booking-bot-redis
```

---

## 🐛 Troubleshooting

### Проблема: `ModuleNotFoundError: No module named 'yaml'`

**Причина:** Не установлен PyYAML

**Решение:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Проблема: `YAML file not found: locales/ru.yaml`

**Причина:** locales/ не смонтирована или пуста

**Решение:**
```bash
# Проверить наличие на хосте
ls -la locales/ru.yaml

# Пересобрать
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Проблема: Бот не запускается

```bash
# Проверить логи
docker-compose logs bot

# Проверить .env
cat .env | grep BOT_TOKEN
cat .env | grep ADMIN_IDS

# Перезапустить
docker-compose restart bot
```

### Проблема: Redis connection failed

```bash
# Проверить статус Redis
docker-compose ps redis

# Перезапустить Redis
docker-compose restart redis

# Перезапустить всё
docker-compose restart
```

---

## 📦 Backup & Restore

### Бэкап данных
```bash
# Бэкапы создаются автоматически
ls -lh backups/

# Ручной бэкап
cp data/bookings.db backups/manual_backup_$(date +%Y%m%d_%H%M%S).db
```

### Восстановление
```bash
# Остановить бота
docker-compose stop bot

# Восстановить из бэкапа
cp backups/backup_YYYYMMDD_HHMMSS.db data/bookings.db

# Запустить
docker-compose start bot
```

---

## 🔒 Production Checklist

✅ `.env` создан и заполнен  
✅ `BOT_TOKEN` указан  
✅ `ADMIN_IDS` указаны  
✅ `REDIS_PASSWORD` сменен с дефолтного  
✅ `./data` директория существует  
✅ `./locales` директория содержит `ru.yaml`  
✅ Бэкапы настроены (`BACKUP_ENABLED=True`)  
✅ Sentry настроен (опционально)  
✅ Docker образ пересобран с `--no-cache`  

---

## 📊 Мониторинг

### Healthcheck
```bash
docker inspect booking-bot | grep Health -A 10
```

### Ресурсы
```bash
docker stats --no-stream booking-bot
```

**Ожидаемое потребление:**
- CPU: 1-5%
- RAM: 50-150 MB
- Network: 1-10 KB/s

---

## 🔗 Ссылки

- [Docker Compose Docs](https://docs.docker.com/compose/)
- [i18n System Guide](./I18N_SYSTEM.md)
- [Project README](../README.md)

---

**Сделано с ❤️ для new12_02 booking bot**
