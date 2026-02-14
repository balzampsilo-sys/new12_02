# 🚀 Быстрое развертывание мультиклиентской системы

## 📋 Предварительные требования

- Docker и Docker Compose
- Git
- Bash (Linux/macOS) или Git Bash (Windows)

## ⚡ Быстрый старт (5 минут)

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/balzampsilo-sys/new12_02.git
cd new12_02
git checkout feature/postgresql-migration
```

### 2. Настройте общую конфигурацию

```bash
# Скопируйте шаблон
cp .env.shared .env.shared.local

# Отредактируйте .env.shared.local (измените пароли!)
nano .env.shared.local
```

**⚠️ ВАЖНО:** Измените пароли в `.env.shared.local`:
- `POSTGRES_ADMIN_PASSWORD` - пароль администратора PostgreSQL
- `DB_USER_PASSWORD` - общий пароль для всех клиентов

### 3. Разверните инфраструктуру

```bash
# Сделайте скрипты исполняемыми
chmod +x scripts/*.sh

# Запустите PostgreSQL и Redis
./scripts/deploy_infrastructure.sh
```

### 4. Создайте первого клиента

```bash
./scripts/setup_client.sh <client_id> "<bot_token>" <admin_telegram_id>

# Пример:
./scripts/setup_client.sh b2fb2108 "7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" 1720268937
```

### 5. Готово! 🎉

Бот автоматически:
- ✅ Создал БД `client_<id>_db`
- ✅ Создал пользователя с правами
- ✅ Скопировал все файлы
- ✅ Собрал Docker образ
- ✅ Запустил контейнер

---

## 🔧 Детальная информация

### Структура проекта

```
new12_02/
├── .env.shared              # Общая конфигурация (НЕ коммитить с паролями!)
├── scripts/
│   ├── deploy_infrastructure.sh  # Развертывание PostgreSQL + Redis
│   └── setup_client.sh          # Создание нового клиента
├── clients/
│   ├── b2fb2108/            # Клиент 1
│   │   ├── .env
│   │   ├── docker-compose.yml
│   │   ├── main.py
│   │   └── ...
│   └── client_002/          # Клиент 2
│       └── ...
├── database/                # Общие файлы БД
├── handlers/                # Общие хэндлеры
└── docker-compose.infrastructure.yml  # Инфраструктура
```

### Параметры `.env.shared`

| Параметр | Описание | Значение по умолчанию |
|----------|----------|----------------------|
| `POSTGRES_ADMIN_USER` | Администратор PostgreSQL | `booking_admin` |
| `POSTGRES_ADMIN_PASSWORD` | Пароль администратора | `changeme_admin_password` |
| `DB_USER_PASSWORD` | Общий пароль клиентов | `secure_client_password_2026` |
| `NETWORK_NAME` | Имя Docker-сети | `new12_02_booking-network` |
| `DB_POOL_MIN_SIZE` | Минимум соединений | `5` |
| `DB_POOL_MAX_SIZE` | Максимум соединений | `20` |

---

## 📝 Управление клиентами

### Добавить нового клиента

```bash
./scripts/setup_client.sh <client_id> "<bot_token>" [admin_id]
```

### Просмотр логов клиента

```bash
cd clients/<client_id>
docker-compose logs -f
```

### Остановить клиента

```bash
cd clients/<client_id>
docker-compose down
```

### Перезапустить клиента

```bash
cd clients/<client_id>
docker-compose restart
```

### Удалить клиента

```bash
cd clients/<client_id>
docker-compose down -v  # -v удаляет volumes
cd ../..
rm -rf clients/<client_id>

# Удалить БД
docker exec -i postgres-shared psql -U booking_admin -d postgres << EOF
DROP DATABASE client_<id>_db;
DROP USER client_<id>_user;
EOF
```

---

## 🔍 Диагностика

### Проверка статуса инфраструктуры

```bash
docker ps | grep -E "postgres-shared|redis-shared"
```

### Проверка сети

```bash
docker network inspect new12_02_booking-network
```

### Проверка БД клиента

```bash
docker exec -it postgres-shared psql -U booking_admin -d postgres
\l                                    # Список БД
\du                                   # Список пользователей
\c client_<id>_db                     # Подключиться к БД клиента
\dt                                   # Список таблиц
```

### Проверка подключения клиента к БД

```bash
docker exec -it postgres-shared psql \
  postgresql://client_<id>_user:<password>@localhost:5432/client_<id>_db \
  -c "SELECT 1;"
```

---

## 🛡️ Безопасность

### ⚠️ НЕ КОММИТИТЬ:
- `.env.shared.local` (добавлен в `.gitignore`)
- `clients/*/. env` (содержит bot tokens)

### ✅ Рекомендации:
1. Используйте сильные пароли в production
2. Регулярно обновляйте пароли
3. Ограничьте доступ к портам PostgreSQL/Redis
4. Используйте SSL для PostgreSQL в production

---

## 🔄 Обновление системы

### Обновить код всех клиентов

```bash
# Создайте скрипт update_all_clients.sh
for client_dir in clients/*/; do
    client_id=$(basename "$client_dir")
    echo "Updating client: $client_id"
    
    # Копируем обновленные файлы
    cp -r database/*.py "$client_dir/database/"
    cp main.py config.py "$client_dir/"
    
    # Перезапускаем
    cd "$client_dir"
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    cd ../..
done
```

---

## 📊 Мониторинг

### Проверка всех клиентов

```bash
docker ps | grep bot-client
```

### Статистика PostgreSQL

```bash
docker exec -it postgres-shared psql -U booking_admin -d postgres -c "
SELECT datname, numbackends, xact_commit, xact_rollback 
FROM pg_stat_database 
WHERE datname LIKE 'client_%';
"
```

### Размер БД клиентов

```bash
docker exec -it postgres-shared psql -U booking_admin -d postgres -c "
SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size
FROM pg_database 
WHERE datname LIKE 'client_%'
ORDER BY pg_database_size(datname) DESC;
"
```

---

## 🆘 Troubleshooting

### Проблема: "Network not found"

```bash
docker network create new12_02_booking-network
```

### Проблема: "PostgreSQL connection refused"

```bash
# Проверьте статус
docker logs postgres-shared

# Перезапустите
docker-compose -f docker-compose.infrastructure.yml restart postgres
```

### Проблема: "Password authentication failed"

```bash
# Сбросьте пароль клиента
docker exec -it postgres-shared psql -U booking_admin -d postgres -c "
ALTER USER client_<id>_user WITH PASSWORD '<password>';
"
```

---

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs`
2. Проверьте сеть: `docker network inspect`
3. Проверьте БД: инструкции выше
4. Создайте issue на GitHub

---

## 📄 Лицензия

MIT License
