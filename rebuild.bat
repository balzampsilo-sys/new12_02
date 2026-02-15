@echo off
REM ========================================
REM  FULL PLATFORM REBUILD SCRIPT (Windows)
REM ========================================
REM 
REM Usage:
REM   rebuild.bat              - Development mode
REM   rebuild.bat production   - Production mode
REM 
REM What it does:
REM   1. Checks prerequisites (.env, Docker)
REM   2. Stops all containers
REM   3. Cleans old images and cache
REM   4. Rebuilds from scratch
REM   5. Starts all services
REM   6. Shows status and logs
REM 
REM ========================================

setlocal enabledelayedexpansion

REM Determine mode
set MODE=%1
if "%MODE%"=="" set MODE=dev

if "%MODE%"=="production" (
    echo ========================================
    echo  PRODUCTION MODE
    echo ========================================
    set COMPOSE_FILE=-f docker-compose.production.yml
    set MODE_NAME=PRODUCTION
) else (
    echo ========================================
    echo  DEVELOPMENT MODE
    echo ========================================
    set COMPOSE_FILE=
    set MODE_NAME=DEVELOPMENT
)
echo.

REM ====================
REM STEP 0: PRE-FLIGHT CHECKS
REM ====================
echo ==================================
echo  STEP 0: PRE-FLIGHT CHECKS
echo ==================================
echo.

echo [1/3] Checking Docker...
docker version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)
echo       Docker: OK

echo [2/3] Checking .env file...
if not exist ".env" (
    echo WARNING: .env file not found!
    echo.
    echo Creating .env from .env.example...
    if exist ".env.example" (
        copy .env.example .env >nul
        echo       .env created! Please edit it before continuing.
        echo.
        echo Required tokens:
        echo   - BOT_TOKEN_MASTER
        echo   - BOT_TOKEN_SALES
        echo   - ADMIN_IDS_MASTER
        echo   - ADMIN_IDS_SALES
        echo   - POSTGRES_PASSWORD
        echo.
        choice /C YN /M "Do you want to edit .env now"
        if errorlevel 2 goto skip_edit
        if errorlevel 1 notepad .env
        :skip_edit
    ) else (
        echo ERROR: .env.example not found!
        pause
        exit /b 1
    )
)
echo       .env: OK

echo [3/3] Checking requirements.txt...
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found!
    echo.
    echo Please run: git pull
    pause
    exit /b 1
)
echo       requirements.txt: OK
echo.
echo All pre-flight checks passed!
echo.

REM ====================
REM STEP 1: STOP ALL CONTAINERS
REM ====================
echo ==================================
echo  STEP 1: STOPPING CONTAINERS
echo ==================================
echo.

echo Stopping all containers...
docker-compose %COMPOSE_FILE% down 2>nul
echo.
echo All containers stopped
echo.

REM ====================
REM STEP 2: CLEAN OLD IMAGES
REM ====================
echo ==================================
echo  STEP 2: CLEANING OLD IMAGES
echo ==================================
echo.

echo Removing old bot images...
for /f "tokens=*" %%i in ('docker images --filter=reference=new12_02* -q 2^>nul') do (
    docker rmi %%i -f 2>nul
)
echo.

echo Cleaning build cache...
docker builder prune -f
echo.
echo Old images removed
echo.

REM ====================
REM STEP 3: BUILD IMAGES
REM ====================
echo ==================================
echo  STEP 3: BUILDING IMAGES
echo ==================================
echo.
echo This will take 2-3 minutes...
echo.

docker-compose %COMPOSE_FILE% build --no-cache --progress=plain
if errorlevel 1 (
    echo.
    echo ========================================
    echo  BUILD FAILED!
    echo ========================================
    echo.
    echo Common issues:
    echo   1. requirements.txt has syntax errors
    echo   2. Dockerfile is missing
    echo   3. Network issues downloading packages
    echo.
    echo Check the output above for specific error.
    pause
    exit /b 1
)
echo.
echo Build successful!
echo.

REM ====================
REM STEP 4: START CONTAINERS
REM ====================
echo ==================================
echo  STEP 4: STARTING CONTAINERS
echo ==================================
echo.

docker-compose %COMPOSE_FILE% up -d
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start containers!
    echo.
    echo Check logs:
    echo    docker-compose %COMPOSE_FILE% logs
    pause
    exit /b 1
)
echo.
echo Containers started!
echo.

echo Waiting for startup (15 seconds^)...
timeout /t 15 /nobreak >nul
echo.

REM ====================
REM STEP 5: VERIFY DEPLOYMENT
REM ====================
echo ==================================
echo  STEP 5: DEPLOYMENT STATUS
echo ==================================
echo.

echo [All Services - %MODE_NAME%]
docker-compose %COMPOSE_FILE% ps
echo.

REM ====================
REM STEP 6: SHOW LOGS
REM ====================
echo ==================================
echo  STEP 6: RECENT LOGS
echo ==================================
echo.

if "%MODE%"=="production" (
    echo [PostgreSQL]
    docker-compose %COMPOSE_FILE% logs --tail=10 postgres
    echo.
    
    echo [Redis]
    docker-compose %COMPOSE_FILE% logs --tail=10 redis
    echo.
    
    echo [Master Bot]
    docker-compose %COMPOSE_FILE% logs --tail=20 bot-master
    echo.
    
    echo [Master Bot API]
    docker-compose %COMPOSE_FILE% logs --tail=20 bot-master-api
    echo.
    
    echo [Sales Bot]
    docker-compose %COMPOSE_FILE% logs --tail=20 bot-sales
    echo.
    
    echo [Sales Webhook]
    docker-compose %COMPOSE_FILE% logs --tail=20 sales-webhook
    echo.
) else (
    echo [PostgreSQL]
    docker-compose logs --tail=10 postgres
    echo.
    
    echo [Redis]
    docker-compose logs --tail=10 redis
    echo.
    
    echo [Master Bot]
    docker-compose logs --tail=20 bot-master
    echo.
    
    echo [Sales Bot]
    docker-compose logs --tail=20 bot-sales
    echo.
)

REM ====================
REM SUMMARY
REM ====================
echo ========================================
echo  DEPLOYMENT COMPLETE!
echo ========================================
echo.
echo Mode: %MODE_NAME%
echo.
echo Services running:
echo   - PostgreSQL ^(port 5432^)
echo   - Redis ^(port 6379^)

if "%MODE%"=="production" (
    echo   - Master Bot ^(Telegram^)
    echo   - Master Bot API ^(port 8000^)
    echo   - Sales Bot ^(Telegram^)
    echo   - Sales Webhook ^(port 8001^)
    echo.
    echo Next steps:
    echo   1. Configure Nginx for ports 8000 and 8001
    echo   2. Set up YooKassa webhook
    echo   3. Test Master Bot API: http://localhost:8000/docs
) else (
    echo   - Master Bot ^(Telegram^)
    echo   - Sales Bot ^(Telegram^)
    echo.
    echo Next steps:
    echo   1. Open Telegram and find your bots
    echo   2. Send /start to Master Bot
    echo   3. Test bookings
)

echo.
echo Useful commands:
echo   - View logs:     docker-compose %COMPOSE_FILE% logs -f
echo   - Restart bot:   docker-compose %COMPOSE_FILE% restart bot-master
echo   - Stop all:      docker-compose %COMPOSE_FILE% down
echo   - Status:        docker-compose %COMPOSE_FILE% ps
echo.
echo   - PostgreSQL:    docker exec -it booking-postgres psql -U booking_user -d booking_saas
echo   - Redis:         docker exec -it booking-redis redis-cli
echo.
echo For production deployment:
echo   - Run: rebuild.bat production
echo.
pause
