# Bot Pool System - Система быстрой активации ботов

## 🎯 Концепция

Система пула готовых ботов для **мгновенной активации** (5-10 секунд) вместо долгого развёртывания нового контейнера.

### Как это работает

```
┌─────────────────────────────────────────────┐
│  При старте системы                         │
├─────────────────────────────────────────────┤
│  PostgreSQL + Redis + Pool Monitor      │
│  + 10 Bot Containers (WAITING)           │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  8 клиентов купили → 8 ботов ACTIVE      │
│  Свободно: 2 бота                         │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  Pool Monitor обнаружил:                  │
│  ⚠️ 2 < 3 (MIN_FREE_BOTS)                  │
│  🚀 Автоматически запускает 5 ботов      │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  Система готова к новым клиентам!         │
│  • Всего: 15 ботов                        │
│  • Свободно: 7 ботов                      │
└─────────────────────────────────────────────┘
```

## ⚡ Преимущества

| Характеристика | Старый способ | Bot Pool |
|---------------|---------------|----------|
| Время активации | 60-120 сек | **5-10 сек** |
| Надёжность | Зависит от Docker API | ✅ Высокая |
| Автомасштабирование | Нет | ✅ **Автоматическое** |
| Сложность | Deploy Worker на хосте | ✅ Простая |
| Масштабируемость | Требует управления | ✅ **До 100 ботов автоматом** |

## 🔄 Автоматическое пополнение пула

**Pool Monitor** - сервис, который постоянно мониторит пул и автоматически запускает новые контейнеры:

### Принцип работы:

1. **Проверка каждые 30 секунд**
2. **Если свободных ботов < 3** → запускает 5 новых
3. **Максимум 100 ботов** в системе

### Настройки:

```bash
# В docker-compose.pool.full.yml
MIN_FREE_BOTS: 3          # Порог для масштабирования
MAX_TOTAL_BOTS: 100       # Максимум ботов
SCALE_BATCH: 5            # Сколько добавлять за раз
CHECK_INTERVAL: 30        # Проверка каждые N секунд
```

📚 **Подробнее:** [docs/POOL_AUTOSCALING.md](docs/POOL_AUTOSCALING.md)

## 🚀 Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone https://github.com/balzampsilo-sys/new12_02.git
cd new12_02
git checkout feature/bot-pool
```

### 2. Настроить .env

```bash
cp .env.example .env
nano .env
```

**Обязательные переменные:**
```bash
POSTGRES_PASSWORD=YourSecurePassword123!
```

### 3. Запустить систему

```bash
chmod +x start_pool.sh
./start_pool.sh
```

### 4. Проверить статус

```bash
# Все контейнеры
docker-compose -f docker-compose.pool.full.yml ps

# Pool Monitor
docker-compose -f docker-compose.pool.full.yml logs pool-monitor
# Должно быть: 🔍 POOL MONITOR STARTED

# Боты
docker-compose -f docker-compose.pool.full.yml logs bot-pool-1
# Должно быть: 🕐 BOT CONTAINER STARTED IN WAITING MODE
```

## 📁 Структура проекта

```
new12_02/
├── main_pool.py                    # Бот с режимом ожидания
├── automation/
│   ├── bot_pool_manager.py        # Менеджер пула
│   └── pool_monitor.py            # Автомасштабирование ⚡
├── docker-compose.pool.full.yml   # 10 ботов + Pool Monitor
├── start_pool.sh                  # Скрипт запуска
├── docs/
│   ├── BOT_POOL_SETUP.md         # Полная документация
│   └── POOL_AUTOSCALING.md       # Автомасштабирование ⚡
└── README_POOL.md                # Этот файл
```

## 🔧 Компоненты системы

### 1. main_pool.py

Главный файл бота с двумя режимами:
- **WAITING** - ожидает конфигурацию через Redis
- **ACTIVE** - работает как полноценный бот клиента

### 2. bot_pool_manager.py

Менеджер пула с методами:
- `find_free_bot()` - найти свободный контейнер
- `activate_bot()` - активировать контейнер
- `get_pool_status()` - получить статус пула
- `deactivate_bot()` - вернуть бот в пул

### 3. pool_monitor.py ⚡ Новое!

Автоматическое пополнение пула:
- Мониторит количество свободных ботов
- Автоматически запускает новые контейнеры
- Масштабирует до 100 ботов

### 4. docker-compose.pool.full.yml

Конфигурация с:
- PostgreSQL 16
- Redis 7
- **Pool Monitor** ⚡
- 10 контейнеров ботов в режиме WAITING

## 📊 Мониторинг

### Через Docker

```bash
# Статус всех контейнеров
docker-compose -f docker-compose.pool.full.yml ps

# Логи Pool Monitor
docker-compose -f docker-compose.pool.full.yml logs -f pool-monitor

# Логи конкретного бота
docker-compose -f docker-compose.pool.full.yml logs -f bot-pool-5

# События масштабирования
docker-compose -f docker-compose.pool.full.yml logs pool-monitor | grep "Scaling up"
```

### Через Redis

```bash
docker exec -it booking-redis redis-cli

# Все статусы
KEYS bot_status:*

# Конкретный статус
GET bot_status:booking-bot-pool-3
```

### Через Master Bot

```
/pool - показать статус пула

🏊 СТАТУС ПУЛА БОТОВ
⚪ Свободно: 7/15
🟢 Занято: 8/15
```

## 🔐 Безопасность

### Multi-tenancy

- **PostgreSQL schemas**: Каждый клиент в отдельной schema (`client_001`, `client_002`, ...)
- **Redis префиксы**: FSM состояния изолированы (`client_001:fsm:*`)
- **Rate limiting**: Per-client ограничения (`client_001:ratelimit:*`)

### Токены

- Передаются через Redis с **TTL=300 сек**
- Удаляются сразу после получения контейнером
- Никогда не логируются в открытом виде

## 🛠 Troubleshooting

### Бот не активируется

```bash
# 1. Проверить контейнер
docker ps | grep bot-pool-3

# 2. Логи
docker logs booking-bot-pool-3

# 3. Redis
docker exec -it booking-redis redis-cli
GET bot_config:booking-bot-pool-3
```

### Pool Monitor не запускает ботов

```bash
# Проверить доступ к Docker socket
docker inspect booking-pool-monitor | grep docker.sock

# Логи монитора
docker logs booking-pool-monitor
```

### Все боты заняты

```bash
# Pool Monitor автоматически добавит новые!
# Просто подождите 30 секунд

# Или увеличьте MAX_TOTAL_BOTS в docker-compose
```

## 📚 Документация

- [Полная инструкция по настройке](docs/BOT_POOL_SETUP.md)
- [Автомасштабирование](docs/POOL_AUTOSCALING.md) ⚡

## 🎯 Production рекомендации

1. ✅ Увеличьте `MAX_TOTAL_BOTS` до **500** для высокой нагрузки
2. ✅ Настройте **алерты** при заполнении > 80%
3. ✅ Добавьте **мониторинг** (Prometheus + Grafana)
4. ✅ **Бэкапы PostgreSQL** ежедневно
5. ✅ **Redis Sentinel** для высокой доступности

## 📝 Лицензия

MIT License

## 🤝 Поддержка

По вопросам: https://github.com/balzampsilo-sys/new12_02/issues

---

**Версия:** 1.1.0 (с автомасштабированием) ⚡  
**Дата:** Февраль 2026  
**Автор:** balzampsilo-sys
