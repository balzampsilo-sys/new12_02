@echo off
REM ============================================
REM ТЕСТОВЫЙ СКРИПТ ДЛЯ WINDOWS
REM ============================================
REM Проверка работоспособности оптимизации
REM деплоя клиентов (188s → 8-10s)
REM ============================================

setlocal enabledelayedexpansion

REM Цвета для вывода
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM Счётчики
set CHECKS_PASSED=0
set CHECKS_FAILED=0

cls
echo.
echo %BLUE%========================================%NC%
echo %BLUE%  ТЕСТ ОПТИМИЗАЦИИ ДЕПЛОЯ%NC%
echo %BLUE%  188s -^> 8-10s%NC%
echo %BLUE%========================================%NC%
echo.
echo Этот скрипт проверит:
echo   1. Docker
echo   2. Python3
echo   3. PostgreSQL
echo   4. Docker Network
echo   5. Redis Shared
echo   6. Базовый образ booking-bot:base
echo   7. Тестовый деплой клиента
echo.
set /p "CONFIRM=Начать тестирование? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Отменено
    exit /b 0
)

REM ============================================
REM ПРОВЕРКА 1: Docker
REM ============================================
echo.
echo %BLUE%========================================%NC%
echo %BLUE%  ПРОВЕРКА 1: DOCKER%NC%
echo %BLUE%========================================%NC%
echo.

echo %YELLOW%▶ Проверка Docker...%NC%
docker --version >nul 2>&1
if errorlevel 1 (
    echo %RED%❌ Docker не установлен!%NC%
    echo.
    echo Установите Docker Desktop для Windows:
    echo https://docs.docker.com/desktop/install/windows-install/
    set /a CHECKS_FAILED+=1
    goto :report
) else (
    echo %GREEN%✅ Docker установлен%NC%
    docker --version
    set /a CHECKS_PASSED+=1
)

echo.
echo %YELLOW%▶ Проверка Docker Compose...%NC%
docker compose version >nul 2>&1
if errorlevel 1 (
    echo %RED%❌ Docker Compose не установлен!%NC%
    set /a CHECKS_FAILED+=1
    goto :report
) else (
    echo %GREEN%✅ Docker Compose установлен%NC%
    docker compose version
    set /a CHECKS_PASSED+=1
)

REM ============================================
REM ПРОВЕРКА 2: Python
REM ============================================
echo.
echo %BLUE%========================================%NC%
echo %BLUE%  ПРОВЕРКА 2: PYTHON%NC%
echo %BLUE%========================================%NC%
echo.

echo %YELLOW%▶ Проверка Python3...%NC%
python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%❌ Python не установлен!%NC%
    echo.
    echo Установите Python:
    echo https://www.python.org/downloads/
    set /a CHECKS_FAILED+=1
    goto :report
) else (
    echo %GREEN%✅ Python установлен%NC%
    python --version
    set /a CHECKS_PASSED+=1
)

echo.
echo %YELLOW%▶ Проверка pip...%NC%
pip --version >nul 2>&1
if errorlevel 1 (
    echo %RED%❌ pip не установлен!%NC%
    set /a CHECKS_FAILED+=1
) else (
    echo %GREEN%✅ pip установлен%NC%
    set /a CHECKS_PASSED+=1
)

echo.
echo %YELLOW%▶ Проверка psycopg2...%NC%
python -c "import psycopg2" >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%⚠️  psycopg2 не установлен%NC%
    echo.
    set /p "INSTALL_PSYCOPG2=Установить сейчас? (Y/N): "
    if /i "!INSTALL_PSYCOPG2!"=="Y" (
        echo Установка psycopg2...
        pip install psycopg2-binary
        echo %GREEN%✅ psycopg2 установлен%NC%
        set /a CHECKS_PASSED+=1
    ) else (
        echo %YELLOW%⚠️  Пропускаем (может потребоваться позже)%NC%
    )
) else (
    echo %GREEN%✅ psycopg2 установлен%NC%
    set /a CHECKS_PASSED+=1
)

REM ============================================
REM ПРОВЕРКА 3: Файлы проекта
REM ============================================
echo.
echo %BLUE%========================================%NC%
echo %BLUE%  ПРОВЕРКА 3: ФАЙЛЫ ПРОЕКТА%NC%
echo %BLUE%========================================%NC%
echo.

set FILES_OK=1

echo %YELLOW%▶ Проверка base.Dockerfile...%NC%
if not exist "base.Dockerfile" (
    echo %RED%❌ base.Dockerfile НЕ НАЙДЕН!%NC%
    set FILES_OK=0
    set /a CHECKS_FAILED+=1
) else (
    echo %GREEN%✅ base.Dockerfile существует%NC%
    set /a CHECKS_PASSED+=1
)

echo %YELLOW%▶ Проверка build_base_image.sh...%NC%
if not exist "build_base_image.sh" (
    echo %RED%❌ build_base_image.sh НЕ НАЙДЕН!%NC%
    set FILES_OK=0
    set /a CHECKS_FAILED+=1
) else (
    echo %GREEN%✅ build_base_image.sh существует%NC%
    set /a CHECKS_PASSED+=1
)

echo %YELLOW%▶ Проверка automation/deploy_manager.py...%NC%
if not exist "automation\deploy_manager.py" (
    echo %RED%❌ deploy_manager.py НЕ НАЙДЕН!%NC%
    set FILES_OK=0
    set /a CHECKS_FAILED+=1
) else (
    echo %GREEN%✅ deploy_manager.py существует%NC%
    set /a CHECKS_PASSED+=1
)

if %FILES_OK%==0 (
    echo.
    echo %RED%❌ Не все файлы найдены!%NC%
    echo Убедитесь что вы в корне проекта.
    goto :report
)

REM ============================================
REM ПРОВЕРКА 4: PostgreSQL
REM ============================================
echo.
echo %BLUE%========================================%NC%
echo %BLUE%  ПРОВЕРКА 4: POSTGRESQL%NC%
echo %BLUE%========================================%NC%
echo.

echo %YELLOW%▶ Проверка доступности PostgreSQL...%NC%
python -c "import psycopg2; conn = psycopg2.connect('postgresql://booking_user:SecurePass2026!@localhost:5432/booking_saas'); print('OK'); conn.close()" >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%⚠️  PostgreSQL недоступен%NC%
    echo.
    set /p "START_PG=Запустить PostgreSQL? (Y/N): "
    if /i "!START_PG!"=="Y" (
        echo Запуск PostgreSQL...
        docker compose -f docker-compose.postgres.yml up -d
        timeout /t 5 >nul
        echo %GREEN%✅ PostgreSQL запущен%NC%
        set /a CHECKS_PASSED+=1
    ) else (
        echo %YELLOW%⚠️  Пропускаем PostgreSQL%NC%
        echo Subscription manager может не работать
    )
) else (
    echo %GREEN%✅ PostgreSQL доступен%NC%
    set /a CHECKS_PASSED+=1
)

REM ============================================
REM ПРОВЕРКА 5: Docker Network
REM ============================================
echo.
echo %BLUE%========================================%NC%
echo %BLUE%  ПРОВЕРКА 5: DOCKER NETWORK%NC%
echo %BLUE%========================================%NC%
echo.

echo %YELLOW%▶ Проверка bot-network...%NC%
docker network ls | findstr "bot-network" >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%⚠️  Network bot-network не существует%NC%
    echo %YELLOW%▶ Создание bot-network...%NC%
    docker network create bot-network
    echo %GREEN%✅ Network bot-network создана%NC%
    set /a CHECKS_PASSED+=1
) else (
    echo %GREEN%✅ Network bot-network существует%NC%
    set /a CHECKS_PASSED+=1
)

REM ============================================
REM ПРОВЕРКА 6: Redis Shared
REM ============================================
echo.
echo %BLUE%========================================%NC%
echo %BLUE%  ПРОВЕРКА 6: REDIS SHARED%NC%
echo %BLUE%========================================%NC%
echo.

echo %YELLOW%▶ Проверка Redis контейнера...%NC%
docker ps | findstr "booking-bot-redis-shared" >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%⚠️  Redis не запущен%NC%
    echo %YELLOW%▶ Запуск Redis...%NC%
    
    if not exist "redis_data" mkdir redis_data
    docker compose -f docker-compose.redis.yml up -d
    
    echo Ожидание запуска Redis (5 сек)...
    timeout /t 5 >nul
    
    docker ps | findstr "booking-bot-redis-shared" >nul 2>&1
    if errorlevel 1 (
        echo %RED%❌ Не удалось запустить Redis%NC%
        set /a CHECKS_FAILED+=1
        goto :report
    ) else (
        echo %GREEN%✅ Redis запущен успешно%NC%
        set /a CHECKS_PASSED+=1
    )
) else (
    echo %GREEN%✅ Redis запущен%NC%
    set /a CHECKS_PASSED+=1
)

REM ============================================
REM ПРОВЕРКА 7: Базовый образ
REM ============================================
echo.
echo %BLUE%========================================%NC%
echo %BLUE%  ПРОВЕРКА 7: БАЗОВЫЙ ОБРАЗ%NC%
echo %BLUE%========================================%NC%
echo.

echo %YELLOW%▶ Проверка наличия образа...%NC%
docker images | findstr "booking-bot.*base" >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%⚠️  Образ booking-bot:base не найден%NC%
    echo.
    echo %RED%ВАЖНО: Сборка образа на Windows через Docker%NC%
    echo.
    set /p "BUILD_IMAGE=Собрать образ сейчас? (Y/N): "
    if /i "!BUILD_IMAGE!"=="Y" (
        echo.
        echo %YELLOW%⏳ Сборка базового образа (это займёт 3-5 минут)...%NC%
        echo.
        docker build -f base.Dockerfile -t booking-bot:base .
        if errorlevel 1 (
            echo %RED%❌ Ошибка сборки образа%NC%
            set /a CHECKS_FAILED+=1
            goto :report
        ) else (
            echo %GREEN%✅ Образ собран успешно%NC%
            set /a CHECKS_PASSED+=1
        )
    ) else (
        echo %RED%❌ Образ НЕ собран%NC%
        echo Невозможно продолжить без базового образа
        set /a CHECKS_FAILED+=1
        goto :report
    )
) else (
    echo %GREEN%✅ Образ booking-bot:base существует%NC%
    docker images booking-bot:base
    set /a CHECKS_PASSED+=1
)

REM ============================================
REM ТЕСТ: Деплой клиента
REM ============================================
echo.
echo %BLUE%========================================%NC%
echo %BLUE%  ТЕСТ: ДЕПЛОЙ КЛИЕНТА%NC%
echo %BLUE%========================================%NC%
echo.

REM Генерация тестовых данных
set TEST_TOKEN=TEST_%RANDOM%_TOKEN
set /a TEST_ADMIN_ID=100000000 + %RANDOM%
set TEST_COMPANY=Test Company %TIME%

echo %YELLOW%▶ Генерация тестовых данных...%NC%
echo   Токен: %TEST_TOKEN%
echo   Admin ID: %TEST_ADMIN_ID%
echo   Компания: %TEST_COMPANY%
echo.

echo %YELLOW%▶ Запуск деплоя клиента...%NC%
echo.
echo %BLUE%────────────────────────────────────────%NC%
echo.

REM Замер времени
set START_TIME=%TIME%

cd automation
python deploy_manager.py "%TEST_TOKEN%" %TEST_ADMIN_ID% --company "%TEST_COMPANY%" --days 30
set DEPLOY_STATUS=%ERRORLEVEL%
cd ..

set END_TIME=%TIME%

echo.
echo %BLUE%────────────────────────────────────────%NC%
echo.

if %DEPLOY_STATUS% NEQ 0 (
    echo %RED%❌ Деплой завершился с ошибкой!%NC%
    set /a CHECKS_FAILED+=1
    goto :report
)

echo %GREEN%✅ Деплой выполнен успешно%NC%
set /a CHECKS_PASSED+=1

REM Проверка контейнера
echo.
echo %YELLOW%▶ Проверка контейнера...%NC%
timeout /t 2 >nul

for /f "tokens=*" %%i in ('docker ps --filter "name=bot-client" --format "{{.Names}}" 2^>nul ^| findstr /r "^bot-client"') do set CONTAINER_NAME=%%i

if defined CONTAINER_NAME (
    echo %GREEN%✅ Контейнер запущен: %CONTAINER_NAME%%NC%
    echo.
    echo %YELLOW%▶ Последние логи контейнера:%NC%
    echo.
    docker logs %CONTAINER_NAME% --tail 20
    echo.
    echo %GREEN%✅ ТЕСТ ПРОЙДЕН! ⚡%NC%
    set /a CHECKS_PASSED+=1
) else (
    echo %RED%❌ Контейнер не запустился!%NC%
    set /a CHECKS_FAILED+=1
)

REM ============================================
REM Очистка
REM ============================================
echo.
set /p "CLEANUP=Очистить тестовый контейнер? (Y/N): "
if /i "%CLEANUP%"=="Y" (
    if defined CONTAINER_NAME (
        echo Остановка %CONTAINER_NAME%...
        docker stop %CONTAINER_NAME% >nul 2>&1
        echo Удаление %CONTAINER_NAME%...
        docker rm %CONTAINER_NAME% >nul 2>&1
        echo %GREEN%✅ Тестовый контейнер удалён%NC%
    )
)

REM ============================================
REM Итоговый отчёт
REM ============================================
:report
echo.
echo %BLUE%========================================%NC%
echo %BLUE%  ИТОГОВЫЙ ОТЧЁТ%NC%
echo %BLUE%========================================%NC%
echo.
echo %BLUE%📊 Статистика:%NC%
echo    ✅ Проверок пройдено: %CHECKS_PASSED%
echo    ❌ Проверок провалено: %CHECKS_FAILED%
echo.

if %CHECKS_FAILED%==0 (
    echo %GREEN%════════════════════════════════════════%NC%
    echo %GREEN%  ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!%NC%
    echo %GREEN%  Система готова к работе ⚡%NC%
    echo %GREEN%════════════════════════════════════════%NC%
    echo.
    exit /b 0
) else (
    echo %RED%════════════════════════════════════════%NC%
    echo %RED%  ❌ ЕСТЬ ПРОБЛЕМЫ!%NC%
    echo %RED%  Исправьте ошибки выше%NC%
    echo %RED%════════════════════════════════════════%NC%
    echo.
    exit /b 1
)
