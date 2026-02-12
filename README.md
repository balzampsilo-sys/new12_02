# 🤖 Telegram Bot для бронирования

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.15+](https://img.shields.io/badge/aiogram-3.15+-green.svg)](https://docs.aiogram.dev/)
[![Code Quality: A-](https://img.shields.io/badge/code%20quality-A---%20(8.5%2F10)-brightgreen.svg)](./ISSUES_RESOLUTION_REPORT.md)
[![Production Ready](https://img.shields.io/badge/production-ready-brightgreen.svg)](./ISSUES_RESOLUTION_REPORT.md)

> 🌟 **Профессиональный Telegram-бот** для автоматизации бронирования услуг с развитым функционалом администрирования.

---

## ✨ Основные возможности

### 💼 Для клиентов

- 📅 **Интуитивный календарь** с индикаторами загрузки (🟢🟡🔴)
- 🎯 **Множественные услуги** с различной лительностью
- 🔔 **Автоматические напоминания** (за 24ч, 2ч, 1ч)
- ⭐ **Система отзывов** с оценкой 1-5 звёзд
- 🚫 **Лимиты на бронирования** (3 на пользователя)
- 🔄 **Перенос и отмена записей** за 2 часа до времени

### 👨‍💻 Для администраторов

- 👥 **Управление ролями** (super_admin, moderator)
- 📊 **Аналитика и статистика** (записи, пользователи, выручка)
- 🔍 **Audit Log** для отслеживания действий
- 🛠️ **Universal Field Editor** для редактирования любых полей
- 📢 **Broadcast система** для массовых рассылок
- 📁 **Массовое редактирование** записей

---

## 🛡️ Production-Ready фичи

### ✅ **Критические проблемы решены** (Feb 12, 2026)

- ✅ **Race Condition Protection** - `BEGIN IMMEDIATE` транзакции
- ✅ **FOREIGN KEY Constraints** - целостность данных
- ✅ **9 Critical Tests** - тестирование race conditions
- ✅ **Proper Timezone Handling** - pytz для Moscow
- ✅ **Automatic Migrations** - безопасное обновление схемы

📊 **Оценка кода:** A- (8.5/10) - См. [ISSUES_RESOLUTION_REPORT.md](./ISSUES_RESOLUTION_REPORT.md)

### 🔧 Технологии

- 📦 **Redis FSM Storage** - сохранение состояний при перезапуске
- 🚨 **Sentry Monitoring** - real-time отслеживание ошибок
- 💾 **Automatic Backups** - каждые 24ч с retention 30 дней
- ⏱️ **Rate Limiting** - защита от флуда
- 🔄 **Retry Logic** - автоматические повторы при `SQLITE_BUSY`
- 🧹 **MessageCleanup** - TTL 48ч для сообщений

---

## 🚀 Быстрый старт

### 🐳 Docker (рекомендуется)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/balzampsilo-sys/tg-bot-10_02.git
cd tg-bot-10_02

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
- 📊 [ISSUES_RESOLUTION_REPORT.md](./ISSUES_RESOLUTION_REPORT.md) - отчет о решении критических проблем
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
- ✅ Пересечение слотов с разной лительностью
- ✅ Откат транзакций
- ✅ Лимиты на пользователя
- ✅ Активация/деактивация услуг

---

## 📊 Архитектура

```
tg-bot-10_02/
├── handlers/          # Обработчики пользовательского ввода (11 модулей)
├── database/          # Слой данных
│   ├── repositories/  # Repository Pattern
│   ├── migrations/    # Миграции БД
│   └── queries.py     # Facade для БД
├── services/          # Бизнес-логика
│   ├── booking_service.py
│   └── notification_service.py
├── middlewares/       # Rate limiting, cleanup
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

---

## ⚠️ Известные ограничения

### SQLite в Production

**Рекомендация:** Продукт готов для **<100 одновременных пользователей**.

📊 При росте >500 пользователей рекомендуется миграция на PostgreSQL.

**Текущая защита:**
- ✅ `BEGIN IMMEDIATE` транзакции
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

### Применить FOREIGN KEY миграцию

```bash
python -m database.migrations.versions.v005_add_foreign_keys
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

### Основные

```
aiogram==3.15.0           # Telegram Bot API
aiosqlite==0.20.0         # Async SQLite
apscheduler==3.10.4       # Job scheduling
pytz==2024.1              # Timezone handling
redis==5.0.1              # FSM storage
sentry-sdk==1.39.2        # Error monitoring
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
- 🛡️ **Используйте HTTPS для webhook**
- ⚠️ **Регулярные backup БД**
- 🔄 **Ротация логов (200MB, 5 файлов)**

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

- 🐛 **Issues:** [GitHub Issues](https://github.com/balzampsilo-sys/tg-bot-10_02/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/balzampsilo-sys/tg-bot-10_02/discussions)
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

<div align="center">

**Сделано с ❤️ в Москве**

[![GitHub stars](https://img.shields.io/github/stars/balzampsilo-sys/tg-bot-10_02?style=social)](https://github.com/balzampsilo-sys/tg-bot-10_02/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/balzampsilo-sys/tg-bot-10_02?style=social)](https://github.com/balzampsilo-sys/tg-bot-10_02/network/members)

</div>
