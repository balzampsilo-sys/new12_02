#!/bin/bash
# ============================================
# BUILD BASE DOCKER IMAGE
# ============================================
# Этот скрипт собирает базовый образ booking-bot:base
# который используется для всех клиентских ботов
#
# Запуск:
#   bash build_base_image.sh
#
# Или с автоматическим push в Docker Hub:
#   bash build_base_image.sh --push
# ============================================

set -e  # Остановиться при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Параметры
IMAGE_NAME="booking-bot:base"
DOCKERFILE="base.Dockerfile"
PUSH_TO_HUB=false

# Проверить аргументы
if [ "$1" == "--push" ]; then
    PUSH_TO_HUB=true
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🚀 BUILDING BASE DOCKER IMAGE${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Проверить что Docker запущен
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker не запущен!${NC}"
    echo -e "${YELLOW}Запустите Docker Desktop и попробуйте снова.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker доступен${NC}"
echo ""

# Проверить что Dockerfile существует
if [ ! -f "$DOCKERFILE" ]; then
    echo -e "${RED}❌ $DOCKERFILE не найден!${NC}"
    exit 1
fi

echo -e "${GREEN}📄 Dockerfile найден: $DOCKERFILE${NC}"
echo ""

# Проверить что requirements.txt существует
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ requirements.txt не найден!${NC}"
    exit 1
fi

echo -e "${GREEN}📋 requirements.txt найден${NC}"
echo ""

# Показать информацию
echo -e "${YELLOW}Параметры сборки:${NC}"
echo -e "  Image: ${GREEN}$IMAGE_NAME${NC}"
echo -e "  Dockerfile: ${GREEN}$DOCKERFILE${NC}"
echo -e "  Push to Hub: ${GREEN}$PUSH_TO_HUB${NC}"
echo ""

# Засечь время
START_TIME=$(date +%s)

echo -e "${YELLOW}🔨 Начинаем сборку...${NC}"
echo ""

# Собрать образ
if docker build -f "$DOCKERFILE" -t "$IMAGE_NAME" . ; then
    echo ""
    echo -e "${GREEN}✅ Сборка успешно завершена!${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Ошибка при сборке образа${NC}"
    exit 1
fi

# Посчитать время
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo -e "${GREEN}⏱️  Время сборки: ${MINUTES}м ${SECONDS}с${NC}"
echo ""

# Показать размер образа
IMAGE_SIZE=$(docker images "$IMAGE_NAME" --format "{{.Size}}" | head -n 1)
echo -e "${GREEN}📦 Размер образа: $IMAGE_SIZE${NC}"
echo ""

# Push в Docker Hub (опционально)
if [ "$PUSH_TO_HUB" == true ]; then
    echo -e "${YELLOW}📤 Push в Docker Hub...${NC}"
    
    if docker push "$IMAGE_NAME"; then
        echo -e "${GREEN}✅ Push успешно завершён${NC}"
    else
        echo -e "${RED}❌ Ошибка при push${NC}"
        echo -e "${YELLOW}Убедитесь что вы залогинены: docker login${NC}"
    fi
    echo ""
fi

# Итоговая информация
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ ГОТОВО!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Базовый образ готов к использованию!${NC}"
echo ""
echo -e "${YELLOW}Теперь все клиентские боты будут деплоиться${NC}"
echo -e "${YELLOW}за 8-10 секунд вместо 3-5 минут! 🚀${NC}"
echo ""
echo -e "${YELLOW}Следующие шаги:${NC}"
echo -e "  1. Запустите: ${GREEN}python3 automation/deploy_worker.py${NC}"
echo -e "  2. Добавьте клиента через Master Bot${NC}"
echo -e "  3. Наслаждайтесь быстрым деплоем! ⚡${NC}"
echo ""
echo -e "${YELLOW}Полезные команды:${NC}"
echo -e "  Проверить образ:   ${GREEN}docker images | grep booking-bot${NC}"
echo -e "  Удалить образ:     ${GREEN}docker rmi $IMAGE_NAME${NC}"
echo -e "  Пересобрать:       ${GREEN}bash build_base_image.sh${NC}"
echo ""
