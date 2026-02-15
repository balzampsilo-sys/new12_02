#!/bin/bash
# ============================================
# ТЕСТОВЫЙ СКРИПТ ДЛЯ ПРОВЕРКИ ОПТИМИЗАЦИИ
# ============================================
# Этот скрипт проверяет работоспособность системы
# быстрого деплоя клиентов (8-10 секунд)
#
# Проверяет:
# 1. Зависимости (Docker, Python)
# 2. PostgreSQL доступность
# 3. Redis shared
# 4. Docker network
# 5. Базовый образ booking-bot:base
# 6. Тестовый деплой клиента
# ============================================

set -e  # Остановиться при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Счётчики
CHECKS_PASSED=0
CHECKS_FAILED=0
TOTAL_TIME=0

# Функции для вывода
print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    ((CHECKS_PASSED++))
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    ((CHECKS_FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Функция для измерения времени
measure_time() {
    local start_time=$(date +%s)
    "$@"
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    TOTAL_TIME=$((TOTAL_TIME + duration))
    echo -e "${GREEN}⏱️  Время выполнения: ${duration}s${NC}"
}

# ============================================
# ПРОВЕРКА 1: Зависимости
# ============================================
check_dependencies() {
    print_header "ПРОВЕРКА 1: ЗАВИСИМОСТИ"
    
    # Docker
    print_step "Проверка Docker..."
    if command -v docker &> /dev/null; then
        docker_version=$(docker --version | awk '{print $3}' | sed 's/,//')
        print_success "Docker установлен: $docker_version"
    else
        print_error "Docker не установлен!"
        print_info "Установите Docker: https://docs.docker.com/get-docker/"
        return 1
    fi
    
    # Docker Compose
    print_step "Проверка Docker Compose..."
    if docker compose version &> /dev/null; then
        compose_version=$(docker compose version --short)
        print_success "Docker Compose установлен: $compose_version"
    else
        print_error "Docker Compose не установлен!"
        return 1
    fi
    
    # Python
    print_step "Проверка Python..."
    if command -v python3 &> /dev/null; then
        python_version=$(python3 --version | awk '{print $2}')
        print_success "Python установлен: $python_version"
    else
        print_error "Python3 не установлен!"
        return 1
    fi
    
    # pip
    print_step "Проверка pip..."
    if command -v pip3 &> /dev/null; then
        print_success "pip3 установлен"
    else
        print_error "pip3 не установлен!"
        return 1
    fi
    
    # psycopg2 (для subscription_manager)
    print_step "Проверка psycopg2..."
    if python3 -c "import psycopg2" 2>/dev/null; then
        print_success "psycopg2 установлен"
    else
        print_warning "psycopg2 не установлен (требуется для subscription_manager)"
        print_info "Установка: pip3 install psycopg2-binary"
        read -p "Установить сейчас? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            pip3 install psycopg2-binary
            print_success "psycopg2 установлен"
        else
            print_warning "Пропускаем установку (может потребоваться позже)"
        fi
    fi
}

# ============================================
# ПРОВЕРКА 2: Файлы проекта
# ============================================
check_project_files() {
    print_header "ПРОВЕРКА 2: ФАЙЛЫ ПРОЕКТА"
    
    local files=(
        "base.Dockerfile"
        "build_base_image.sh"
        "requirements.txt"
        "automation/deploy_manager.py"
        "automation/subscription_manager.py"
        "docker-compose.redis.yml"
    )
    
    for file in "${files[@]}"; do
        print_step "Проверка $file..."
        if [ -f "$file" ]; then
            print_success "$file существует"
        else
            print_error "$file НЕ НАЙДЕН!"
            return 1
        fi
    done
}

# ============================================
# ПРОВЕРКА 3: PostgreSQL
# ============================================
check_postgresql() {
    print_header "ПРОВЕРКА 3: POSTGRESQL"
    
    print_step "Проверка доступности PostgreSQL..."
    
    # Попробовать подключиться через Python
    python3 << 'EOF'
import os
import psycopg2
import sys

try:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://booking_user:SecurePass2026!@localhost:5432/booking_saas"
    )
    
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"✅ PostgreSQL доступен")
    print(f"   Версия: {version.split()[0]} {version.split()[1]}")
    cursor.close()
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f"❌ Ошибка подключения к PostgreSQL: {e}")
    sys.exit(1)
EOF
    
    if [ $? -eq 0 ]; then
        print_success "PostgreSQL работает"
    else
        print_error "PostgreSQL недоступен!"
        print_info "Запустите PostgreSQL из docker-compose.postgres.yml"
        print_info "Команда: docker compose -f docker-compose.postgres.yml up -d"
        return 1
    fi
}

# ============================================
# ПРОВЕРКА 4: Docker Network
# ============================================
check_docker_network() {
    print_header "ПРОВЕРКА 4: DOCKER NETWORK"
    
    print_step "Проверка bot-network..."
    if docker network ls | grep -q "bot-network"; then
        print_success "Network bot-network существует"
    else
        print_warning "Network bot-network не существует"
        print_step "Создание bot-network..."
        docker network create bot-network
        print_success "Network bot-network создана"
    fi
}

# ============================================
# ПРОВЕРКА 5: Redis Shared
# ============================================
check_redis() {
    print_header "ПРОВЕРКА 5: REDIS SHARED"
    
    print_step "Проверка Redis контейнера..."
    if docker ps | grep -q "booking-bot-redis-shared"; then
        print_success "Redis запущен"
        
        # Проверить подключение
        if docker exec booking-bot-redis-shared redis-cli ping &> /dev/null; then
            print_success "Redis отвечает на команды"
        else
            print_warning "Redis запущен но не отвечает"
        fi
    else
        print_warning "Redis не запущен"
        print_step "Запуск Redis..."
        
        # Создать папку для данных
        mkdir -p redis_data
        
        # Запустить Redis
        docker compose -f docker-compose.redis.yml up -d
        
        # Подождать запуска
        print_step "Ожидание запуска Redis (5 сек)..."
        sleep 5
        
        if docker ps | grep -q "booking-bot-redis-shared"; then
            print_success "Redis запущен успешно"
        else
            print_error "Не удалось запустить Redis"
            return 1
        fi
    fi
}

# ============================================
# ПРОВЕРКА 6: Базовый образ
# ============================================
check_base_image() {
    print_header "ПРОВЕРКА 6: БАЗОВЫЙ ОБРАЗ booking-bot:base"
    
    print_step "Проверка наличия образа..."
    if docker images | grep -q "booking-bot.*base"; then
        image_size=$(docker images booking-bot:base --format "{{.Size}}")
        image_created=$(docker images booking-bot:base --format "{{.CreatedSince}}")
        print_success "Образ booking-bot:base существует"
        print_info "Размер: $image_size"
        print_info "Создан: $image_created"
        
        read -p "Пересобрать образ? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            build_base_image
        fi
    else
        print_warning "Образ booking-bot:base не найден"
        print_step "Сборка базового образа..."
        build_base_image
    fi
}

build_base_image() {
    print_step "Запуск build_base_image.sh..."
    echo ""
    
    # Измерить время сборки
    local start_time=$(date +%s)
    
    bash build_base_image.sh
    
    local end_time=$(date +%s)
    local build_time=$((end_time - start_time))
    
    echo ""
    print_success "Образ собран за ${build_time}s"
    TOTAL_TIME=$((TOTAL_TIME + build_time))
}

# ============================================
# ТЕСТ: Деплой клиента
# ============================================
test_deploy_client() {
    print_header "ТЕСТ: ДЕПЛОЙ КЛИЕНТА"
    
    print_step "Генерация тестовых данных..."
    local test_token="TEST_$(date +%s)_TOKEN"
    local test_admin_id=$(( 100000000 + RANDOM % 900000000 ))
    local test_company="Test Company $(date +%H:%M:%S)"
    
    print_info "Токен: $test_token"
    print_info "Admin ID: $test_admin_id"
    print_info "Компания: $test_company"
    echo ""
    
    print_step "Запуск деплоя клиента..."
    echo ""
    print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Измерить время деплоя
    local deploy_start=$(date +%s)
    
    cd automation
    python3 deploy_manager.py \
        "$test_token" \
        "$test_admin_id" \
        --company "$test_company" \
        --days 30
    
    local deploy_status=$?
    cd ..
    
    local deploy_end=$(date +%s)
    local deploy_time=$((deploy_end - deploy_start))
    
    echo ""
    print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    if [ $deploy_status -eq 0 ]; then
        print_success "Деплой выполнен за ${deploy_time}s"
        
        # Проверить контейнер
        print_step "Проверка контейнера..."
        sleep 2
        
        if docker ps | grep -q "bot-client"; then
            local container_name=$(docker ps --filter "name=bot-client" --format "{{.Names}}" | head -1)
            print_success "Контейнер запущен: $container_name"
            
            # Показать логи
            print_step "Последние логи контейнера:"
            echo ""
            docker logs "$container_name" --tail 20
            echo ""
            
            # Сохранить имя для очистки
            echo "$container_name" > /tmp/test_container_name.txt
            
            print_success "ТЕСТ ПРОЙДЕН! ⚡"
            
            # Оценка скорости
            if [ $deploy_time -le 10 ]; then
                print_success "Скорость деплоя ОТЛИЧНАЯ: ${deploy_time}s ≤ 10s"
            elif [ $deploy_time -le 15 ]; then
                print_success "Скорость деплоя ХОРОШАЯ: ${deploy_time}s"
                print_warning "Можно оптимизировать ещё"
            else
                print_warning "Скорость деплоя: ${deploy_time}s"
                print_warning "Ожидалось: ~8-10s"
                print_info "Возможные причины задержки:"
                print_info "  - Медленный диск"
                print_info "  - Высокая загрузка CPU"
                print_info "  - Первый запуск (холодный старт)"
            fi
        else
            print_error "Контейнер не запустился!"
            return 1
        fi
    else
        print_error "Деплой завершился с ошибкой!"
        return 1
    fi
}

# ============================================
# Очистка после теста
# ============================================
cleanup_test() {
    print_header "ОЧИСТКА ТЕСТОВОГО КОНТЕЙНЕРА"
    
    if [ -f /tmp/test_container_name.txt ]; then
        local container_name=$(cat /tmp/test_container_name.txt)
        
        print_step "Остановка $container_name..."
        docker stop "$container_name" &> /dev/null || true
        
        print_step "Удаление $container_name..."
        docker rm "$container_name" &> /dev/null || true
        
        print_success "Тестовый контейнер удалён"
        rm /tmp/test_container_name.txt
    else
        print_info "Нет тестового контейнера для очистки"
    fi
    
    read -p "Удалить тестовые файлы в clients/? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_step "Очистка clients/..."
        # Удалить только тестовые (созданные сегодня)
        find clients/ -maxdepth 1 -type d -mtime -1 -exec rm -rf {} + 2>/dev/null || true
        print_success "Тестовые файлы удалены"
    fi
}

# ============================================
# ИТОГОВЫЙ ОТЧЁТ
# ============================================
print_report() {
    print_header "ИТОГОВЫЙ ОТЧЁТ"
    
    echo ""
    echo -e "${BLUE}📊 Статистика:${NC}"
    echo -e "   ✅ Проверок пройдено: ${GREEN}$CHECKS_PASSED${NC}"
    echo -e "   ❌ Проверок провалено: ${RED}$CHECKS_FAILED${NC}"
    echo -e "   ⏱️  Общее время: ${YELLOW}${TOTAL_TIME}s${NC}"
    echo ""
    
    if [ $CHECKS_FAILED -eq 0 ]; then
        echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!${NC}"
        echo -e "${GREEN}  Система готова к работе ⚡${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}═══════════════════════════════════════════════${NC}"
        echo -e "${RED}  ❌ ЕСТЬ ПРОБЛЕМЫ!${NC}"
        echo -e "${RED}  Исправьте ошибки выше${NC}"
        echo -e "${RED}═══════════════════════════════════════════════${NC}"
        echo ""
        return 1
    fi
}

# ============================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================
main() {
    clear
    
    print_header "ТЕСТ ОПТИМИЗАЦИИ ДЕПЛОЯ (188s → 8-10s)"
    
    echo -e "${BLUE}Этот скрипт проверит:${NC}"
    echo "  1. Зависимости (Docker, Python)"
    echo "  2. Файлы проекта"
    echo "  3. PostgreSQL"
    echo "  4. Docker Network"
    echo "  5. Redis Shared"
    echo "  6. Базовый образ booking-bot:base"
    echo "  7. Тестовый деплой клиента"
    echo ""
    
    read -p "Начать тестирование? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Отменено"
        exit 0
    fi
    
    # Запуск проверок
    check_dependencies || exit 1
    check_project_files || exit 1
    check_postgresql || exit 1
    check_docker_network || exit 1
    check_redis || exit 1
    check_base_image || exit 1
    
    # Тестовый деплой
    test_deploy_client || exit 1
    
    # Очистка
    echo ""
    read -p "Очистить тестовый контейнер? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cleanup_test
    fi
    
    # Итоговый отчёт
    print_report
}

# Запуск
main
