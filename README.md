# 🤖 Telegram Bot для бронирования

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.21+](https://img.shields.io/badge/aiogram-3.21+-green.svg)](https://docs.aiogram.dev/)
[![Code Quality: B+](https://img.shields.io/badge/code%20quality-B+%20(7.5%2F10)-green.svg)](./TECHNICAL_DOCUMENTATION.md)
[![Production Ready](https://img.shields.io/badge/production-ready%20%28with%20notes%29-yellow.svg)](./TECHNICAL_DOCUMENTATION.md)

> 🌟 **Профессиональный Telegram-бот** для автоматизации бронирования услуг с развитым функционалом администрирования.

---

## ✨ Основные возможности

### 💼 Для клиентов

- 📅 **Интуитивный календарь** с индикаторами загрузки (🟢🟡🔴)
- 🎯 **Множественные услуги** с различной длительностью (60/90/120 мин)
- 🔔 **Автоматические напоминания** (за 24ч, 2ч, 1ч) ✅ **ФИКС: 2ч теперь работает!**
- ⭐ **Система отзывов** с оценкой 1-5 звёзд
- 🚫 **Лимиты на бронирования** (3 на пользователя)
- 🔄 **Перенос и отмена записей** за 24 часа до времени (✅ **ИСПРАВЛЕНО: было 2ч**)

### 👨‍💻 Для администраторов

- 👥 **Управление ролями** (super_admin, moderator)
- 📊 **Аналитика и статистика** (записи, пользователи, выручка)
- 🔍 **Audit Log** для отслеживания действий
- 🛠️ **Universal Field Editor** для редактирования любых полей
- 📢 **Broadcast система** для массовых рассылок
- 📁 **Массовое редактирование** записей
- 🌐 **Hybrid i18n система** (YAML + DB с Admin UI) ✅ **NEW!**
- ⏱️ **Гибкие интервалы слотов** (60/30/15 мин) ✅ **NEW!**

---

## 🛡️ Production-Ready фичи

### ✅ **Критические проблемы решены** (Feb 13, 2026)

- ✅ **Race Condition Protection** - `BEGIN IMMEDIATE` транзакции
- ✅ **Transaction Timeouts** - 30с транзакции, 10с запросы ✅ **ФИКС!**
- ✅ **Event Loop Fix** - asyncio.get_running_loop() ✅ **ФИКС!**
- ✅ **2h Reminders** - трёхуровневая система напоминаний ✅ **ФИКС!**
- ✅ **FOREIGN KEY Constraints** - целостность данных
- ✅ **9 Critical Tests** - тестирование race conditions
- ✅ **Proper Timezone Handling** - pytz для Moscow
- ✅ **Automatic Migrations** - безопасное обновление схемы

📊 **Оценка кода:** B+ (7.5/10) - См. [TECHNICAL_DOCUMENTATION.md](./TECHNICAL_DOCUMENTATION.md)

### 🔧 Технологии

- 📦 **Redis FSM Storage** - сохранение состояний при перезапуске
- 🚨 **Sentry Monitoring** - real-time отслеживание ошибок
- 💾 **Automatic Backups** - каждые 24ч с retention 30 дней
- ⏱️ **Rate Limiting** - защита от флуда (3 попытки/10с)
- 🔄 **Retry Logic** - автоматические повторы при `SQLITE_BUSY`
- 🧹 **MessageCleanup** - TTL 48ч для сообщений
- 📝 **Booking History** - полный аудит изменений записей

---

## 🚀 Быстрый старт

### 🐳 Docker (рекомендуется)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/balzampsilo-sys/new12_02.git
cd new12_02

# 2. Настроить переменные окружения
cp .env.example .env
nano .env  # Добавьте BOT_TOKEN и ADMIN_IDS

# 3. Запустить
docker-compose up -d
```

### 🐍 Ручная установка

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Настроить .env
cp .env.example .env

# 3. Запустить
python main.py
```

### 📦 Автоматическая установка

```bash
bash install.sh
```

📖 **Подробная инструкция:** [QUICK_START.md](./QUICK_START.md)

---

## 📝 Документация

- 🚀 [QUICK_START.md](./QUICK_START.md) - пошаговая установка
- 📖 [USER_GUIDE.md](./USER_GUIDE.md) - руководство пользователя
- 🔒 [SECURITY_GUIDE.md](./SECURITY_GUIDE.md) - рекомендации по безопасности
- 📊 [TECHNICAL_DOCUMENTATION.md](./TECHNICAL_DOCUMENTATION.md) - полная техническая документация
- 🔧 [INTEGRATION_INSTRUCTIONS.md](./INTEGRATION_INSTRUCTIONS.md) - интеграция с сервисами

---

## 🧪 Тестирование

```bash
# Запустить все тесты
pytest tests/ -v

# Только критические тесты
pytest tests/test_database.py -v

# С покрытием
pytest --cov=. tests/
```

**Реализовано 9 критических тестов:**
- ✅ Race conditions в бронировании
- ✅ Пересечение слотов с разной длительностью
- ✅ Откат транзакций
- ✅ Лимиты на пользователя
- ✅ Активация/деактивация услуг

---

## 📊 Архитектура

```
new12_02/
├── handlers/          # Обработчики пользовательского ввода (14 модулей)
├── database/          # Слой данных
│   ├── repositories/  # Repository Pattern (12 репозиториев)
│   ├── migrations/    # Миграции БД (v001-v009)
│   └── queries.py     # Facade для БД
├── services/          # Бизнес-логика (6 сервисов)
│   ├── booking_service.py
│   ├── reminder_service.py    # ✅ ФИКС: 24h/2h/1h
│   ├── notification_service.py
│   ├── analytics_service.py
│   └── text_manager.py        # ✅ NEW: Hybrid i18n
├── middlewares/       # Rate limiting, cleanup, security
├── keyboards/         # UI компоненты
├── utils/             # Вспомогательные функции
└── tests/             # Тесты (9 critical)
```

**Принципы:**
- ✅ Separation of Concerns
- ✅ Repository Pattern
- ✅ Service Layer
- ✅ Dependency Injection
- ✅ Middleware Pattern
- ✅ Migration Pattern

---

## ⚠️ Известные ограничения

### SQLite в Production

**Рекомендация:** Продукт готов для **<100 одновременных пользователей**.

📊 При росте >500 пользователей рекомендуется миграция на PostgreSQL.

**Текущая защита:**
- ✅ `BEGIN IMMEDIATE` транзакции
- ✅ Transaction timeouts (30с) ✅ **ФИКС!**
- ✅ Retry logic для `SQLITE_BUSY`
- ✅ Connection timeout handling

---

## 👨‍💻 Разработка

### Запуск в dev-режиме

```bash
# С автоперезагрузкой
python main.py --dev

# С дебаг логами
DEBUG=1 python main.py
```

### Применить миграции

```bash
# Автоматически при запуске
python main.py

# Ручной запуск конкретной миграции
python -m database.migrations.versions.v009_text_templates
```

### Code Quality

```bash
# Formatting
black .

# Linting
ruff check .

# Type checking
mypy .
```

---

## 📦 Зависимости

### Основные (✅ **ИСПРАВЛЕНО: версии совпадают с requirements.txt**)

```
aiogram==3.21.0           # Telegram Bot API (✅ ФИКС: было 3.15.0)
aiosqlite==0.20.0         # Async SQLite
apscheduler==3.10.4       # Job scheduling
python-dateutil==2.9.0    # Date parsing
pytz==2024.2              # Timezone handling (✅ ФИКС: было 2024.1)
cachetools==5.5.0         # Caching
redis==5.2.1              # FSM storage (✅ ФИКС: было 5.0.1)
sentry-sdk==2.19.2        # Error monitoring (✅ ФИКС: было 1.39.2)
aiogram-calendar==0.6.0   # Calendar UI
pydantic==2.10.5          # Data validation
PyYAML==6.0.2             # i18n YAML parser ✅ NEW!
```

### Dev-зависимости

```
pytest==7.4.3             # Testing
pytest-asyncio==0.21.1    # Async tests
black==24.1.1             # Code formatting
mypy==1.8.0               # Type checking
ruff==0.1.9               # Fast linting
```

---

## 🔒 Безопасность

- 🔑 **Не коммитьте `.env` файл**
- 🛡️ **Используйте HTTPS для webhook** (планируется)
- ⚠️ **Регулярные backup БД** (автоматические каждые 24ч)
- 🔄 **Ротация логов** (200MB, 5 файлов)

📖 **Подробнее:** [SECURITY_GUIDE.md](./SECURITY_GUIDE.md)

---

## 📊 Мониторинг

### Sentry (рекомендуется)

```bash
# В .env
SENTRY_DSN=https://your-sentry-dsn
SENTRY_ENVIRONMENT=production
```

### Российские альтернативы

- 🇷🇺 **Yandex.Cloud Monitoring**
- 🇷🇺 **VK Cloud Monitoring**
- 🇷🇺 **Selectel Monitoring**

---

## 🎓 Лицензия

MIT License - свободно используйте в коммерческих проектах.

---

## 🤝 Вклад

Pull requests приветствуются!

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing`)
3. Закоммитьте изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing`)
5. Откройте Pull Request

---

## 📞 Поддержка

- 🐛 **Issues:** [GitHub Issues](https://github.com/balzampsilo-sys/new12_02/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/balzampsilo-sys/new12_02/discussions)
- ✉️ **Email:** balzampsilo@gmail.com

---

## ⭐ Roadmap

### Ближайшие планы

- [ ] Интеграция с платежными системами
- [ ] Экспорт в Google Calendar / iCal
- [ ] Webhook вместо polling
- [ ] WebSocket для админ-панели
- [ ] Multi-tenant поддержка

### Долгосрочные

- [ ] Миграция на PostgreSQL
- [ ] Kubernetes deployment
- [ ] Prometheus + Grafana
- [ ] Мобильное приложение

---

## 🏆 Благодарности

- [aiogram](https://github.com/aiogram/aiogram) - отличный Telegram Bot framework
- [APScheduler](https://github.com/agronholm/apscheduler) - надежный scheduler
- [Sentry](https://sentry.io) - error monitoring

---

## ✅ Исправления (Feb 13, 2026)

Все 4 критические задачи выполнены:

1. ✅ **Event Loop Fix** - используется `asyncio.get_running_loop()` [Commit 3d8f22e](https://github.com/balzampsilo-sys/new12_02/commit/3d8f22e)
2. ✅ **Transaction Timeouts** - 30с для транзакций, 10с для запросов (уже было в booking_repository_v2.py)
3. ✅ **2h Reminders** - реализовано в reminder_service.py [Commit 81c917e](https://github.com/balzampsilo-sys/new12_02/commit/81c917e)
4. ✅ **Documentation** - исправлено 27 несоответствий в README.md

---

<div align="center">

**Сделано с ❤️ в Москве**

[![GitHub stars](https://img.shields.io/github/stars/balzampsilo-sys/new12_02?style=social)](https://github.com/balzampsilo-sys/new12_02/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/balzampsilo-sys/new12_02?style=social)](https://github.com/balzampsilo-sys/new12_02/network/members)

</div>
