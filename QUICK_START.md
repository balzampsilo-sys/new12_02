# 🚀 Quick Start - Коробочное решение

> 🎉 **Полностью автоматизированная установка за 3 минуты!**

---

## 🟢 Вариант 1: Автоматическая установка (Рекомендуется)

### 💻 Linux / macOS

```bash
# 1. Склонировать репозиторий
git clone https://github.com/balzampsilo-sys/tg-bot-10_02.git
cd tg-bot-10_02

# 2. Запустить автоустановщик
chmod +x install.sh
./install.sh
```

**Что сделает скрипт:**
- ✅ Установит Docker и Docker Compose (если нет)
- ✅ Создаст `.env` файл
- ✅ Запросит Bot Token и Admin IDs
- ✅ Запустит бот и Redis в Docker

### 🪠 Windows

```powershell
# 1. Установить Docker Desktop
# Скачать: https://www.docker.com/products/docker-desktop

# 2. Открыть PowerShell и выполнить:
git clone https://github.com/balzampsilo-sys/tg-bot-10_02.git
cd tg-bot-10_02

# 3. Скопировать .env.example в .env
copy .env.example .env

# 4. Отредактировать .env (добавить BOT_TOKEN и ADMIN_IDS)
notepad .env

# 5. Запустить
docker compose up -d --build
```

---

## ⚙️ Настройка

### 1. Получить Bot Token

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Отправьте: `/newbot`
3. Введите имя бота
4. Введите username (должен заканчиваться на `bot`)
5. Скопируйте token

### 2. Получить Admin ID

1. Найдите [@userinfobot](https://t.me/userinfobot)
2. Отправьте любое сообщение
3. Скопируйте ваш ID

### 3. (Опционально) Мониторинг ошибок

> ⚠️ **Важно:** Sentry заблокирован в России. См. [MONITORING_ALTERNATIVES.md](MONITORING_ALTERNATIVES.md)

**По умолчанию используется встроенное логирование:**

```bash
# Просмотр логов
docker compose logs -f bot

# Фильтр по ошибкам
docker compose logs -f bot | grep ERROR
```

**Альтернативы:** см. [MONITORING_ALTERNATIVES.md](MONITORING_ALTERNATIVES.md) для self-hosted Sentry, Hawk.so и других решений.

---

## 🛠️ Управление

### Основные команды

```bash
# Просмотр логов (в реальном времени)
docker compose logs -f bot

# Остановить бота
docker compose stop

# Запустить бота
docker compose start

# Перезапустить бота
docker compose restart

# Проверить статус
docker compose ps

# Обновить бота
git pull
docker compose up -d --build

# Полное удаление (включая данные)
docker compose down -v
```

### Работа с Redis

```bash
# Подключиться к Redis
docker compose exec redis redis-cli -a botredis123

# Просмотреть FSM состояния
docker compose exec redis redis-cli -a botredis123 KEYS "fsm:*"

# Очистить все состояния
docker compose exec redis redis-cli -a botredis123 FLUSHALL
```

### Бэкапы

```bash
# Бэкапы автоматически сохраняются в ./backups/

# Создать ручной бэкап
cp data/bookings.db backups/manual-$(date +%Y%m%d-%H%M%S).db

# Восстановить из бэкапа
docker compose stop bot
cp backups/backup-20260212-120000.db data/bookings.db
docker compose start bot
```

---

## 📁 Структура проекта

```
tg-bot-10_02/
├── data/              # База данных SQLite
├── backups/          # Автоматические бэкапы
├── logs/             # Логи бота
├── handlers/         # Обработчики команд
├── database/         # Работа с БД
├── services/         # Бизнес-логика
├── tests/            # Тесты
├── .env              # Конфигурация
├── docker-compose.yml
└── install.sh        # Автоустановщик
```

---

## ❓ Troubleshooting

### Бот не запускается

```bash
# 1. Проверить логи
docker compose logs bot

# 2. Проверить .env
cat .env | grep BOT_TOKEN
cat .env | grep ADMIN_IDS

# 3. Пересоздать контейнеры
docker compose down
docker compose up -d --build
```

### Redis не подключается

```bash
# Проверить статус Redis
docker compose ps redis

# Проверить логи
docker compose logs redis

# Перезапустить
docker compose restart redis
```

### Потеряны данные

```bash
# Восстановить из последнего бэкапа
ls -lt backups/ | head -n 2
docker compose stop bot
cp backups/backup-YYYYMMDD-HHMMSS.db data/bookings.db
docker compose start bot
```

### Порт 6379 уже занят

```bash
# Найти процесс
sudo lsof -i :6379

# Или изменить порт в docker-compose.yml:
ports:
  - "6380:6379"  # Использовать порт 6380
```

---

## 🌐 Production Deployment

### VPS (например, DigitalOcean)

```bash
# 1. SSH подключение
ssh root@your-server-ip

# 2. Установка
apt update && apt upgrade -y
git clone https://github.com/balzampsilo-sys/tg-bot-10_02.git
cd tg-bot-10_02
./install.sh

# 3. Настроить автозапуск
sudo systemctl enable docker

# 4. Настроить auto-restart
# Добавьте в docker-compose.yml:
restart: always  # уже есть!
```

### Рекомендации для production

1. **Смените Redis пароль:**
```bash
# В .env:
REDIS_PASSWORD=your_very_strong_password_here
```

2. **Мониторинг:**
- Используйте встроенное логирование
- Или см. [MONITORING_ALTERNATIVES.md](MONITORING_ALTERNATIVES.md)

3. **Настройте регулярные бэкапы:**
```bash
# Добавьте в crontab:
0 3 * * * cd /path/to/tg-bot-10_02 && docker compose exec -T bot python -c "from utils.backup_service import BackupService; BackupService('/app/data/bookings.db', '/app/backups', 30).create_backup()"
```

4. **Настройте файервол:**
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (если нужен)
sudo ufw allow 443/tcp   # HTTPS (если нужен)
sudo ufw enable
```

---

## 📊 Мониторинг

### Статистика Docker

```bash
# Использование ресурсов
docker stats

# Использование диска
du -sh data/ backups/ logs/
```

### Логирование

**Встроенное логирование (работает из коробки):**

```bash
# Реальное время
docker compose logs -f bot

# Только ошибки
docker compose logs bot | grep ERROR

# Последние 100 строк
docker compose logs --tail=100 bot
```

**Для продвинутого мониторинга:** см. [MONITORING_ALTERNATIVES.md](MONITORING_ALTERNATIVES.md)

---

## ✅ Проверка работы

После установки:

1. ✅ Откройте Telegram
2. ✅ Найдите вашего бота
3. ✅ Отправьте `/start`
4. ✅ Бот должен ответить приветствием
5. ✅ Попробуйте создать бронь

---

## 📚 Дополнительные ресурсы

- 📝 [CRITICAL_FIXES_COMPLETED.md](CRITICAL_FIXES_COMPLETED.md) - Полный отчет о изменениях
- 🚨 [MONITORING_ALTERNATIVES.md](MONITORING_ALTERNATIVES.md) - Альтернативы Sentry
- 📊 [Tests Documentation](tests/) - Документация по тестам
- 🔧 [.env.example](.env.example) - Пример конфигурации

---

## 👤 Поддержка

Если возникли проблемы:

1. 📝 Проверьте Troubleshooting выше
2. 🔍 Посмотрите логи: `docker compose logs -f bot`
3. 🐞 Создайте issue на GitHub

---

**Статус:** 🟢 Production-Ready  
**Версия:** 1.0.0  
**Последнее обновление:** 12 февраля 2026

🎉 **Ваш бот готов к работе!**
