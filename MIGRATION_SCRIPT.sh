#!/bin/bash
# Скрипт для автоматического переноса файлов из старого репо

set -e

echo "🚀 Начинаем миграцию файлов..."

# Проверяем, есть ли старый репозиторий
if [ ! -d "../tg-bot" ]; then
    echo "⚠️  Клонируем старый репозиторий..."
    cd ..
    git clone https://github.com/balzampsilo-sys/tg-bot.git
    cd tg-bot
    git checkout feature/multiple-services
    cd ../tg-bot-10_02
else
    echo "✅ Старый репозиторий найден"
    cd ../tg-bot
    git checkout feature/multiple-services
    git pull
    cd ../tg-bot-10_02
fi

OLD_REPO="../tg-bot"

echo "📂 Копируем файлы..."

# Database repositories
cp -r "$OLD_REPO/database/repositories/booking_repository.py" database/repositories/
cp -r "$OLD_REPO/database/repositories/user_repository.py" database/repositories/
cp -r "$OLD_REPO/database/repositories/analytics_repository.py" database/repositories/
cp -r "$OLD_REPO/database/repositories/service_repository.py" database/repositories/

# Migration v004
cp -r "$OLD_REPO/database/migrations/versions/v004_add_services.py" database/migrations/versions/

# Handlers
cp -r "$OLD_REPO/handlers/user_handlers.py" handlers/
cp -r "$OLD_REPO/handlers/booking_handlers.py" handlers/
cp -r "$OLD_REPO/handlers/admin_handlers.py" handlers/

# Keyboards
cp -r "$OLD_REPO/keyboards/user_keyboards.py" keyboards/
cp -r "$OLD_REPO/keyboards/admin_keyboards.py" keyboards/
cp -r "$OLD_REPO/keyboards/service_keyboards.py" keyboards/

# Middlewares
cp -r "$OLD_REPO/middlewares/rate_limit.py" middlewares/

# Services
cp -r "$OLD_REPO/services/booking_service.py" services/
cp -r "$OLD_REPO/services/notification_service.py" services/
cp -r "$OLD_REPO/services/analytics_service.py" services/

# Utils
cp -r "$OLD_REPO/utils/helpers.py" utils/
cp -r "$OLD_REPO/utils/states.py" utils/

echo "✅ Все файлы скопированы!"

echo "
📝 Добавляем файлы в Git..."
git add .
git commit -m "✨ Add all remaining files from tg-bot/feature/multiple-services"

echo "
🚀 Отправляем изменения..."
git push origin main

echo "
✅ Миграция завершена!"
echo "ℹ️  Теперь можно запустить: python main.py"
