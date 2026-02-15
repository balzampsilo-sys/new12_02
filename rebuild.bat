@echo off
REM ========================================
REM  FULL PLATFORM REBUILD SCRIPT (Windows)
REM ========================================
REM 
REM Usage:
REM   rebuild.bat              - Development mode (basic bots)
 REM   rebuild.bat production   - Production mode (all services)
REM 
REM What it does:
 REM   1. Checks prerequisites (.env, requirements.txt, Docker)
REM   2. Starts PostgreSQL and Redis infrastructure
REM   3. Waits for DB/Redis to be healthy
REM   4. Rebuilds and starts bot containers
REM   5. Shows status and logs
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

echo [1/4] Checking Docker...
docker version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)
echo       Docker: OK

echo [2/4] Checking .env file...
if not exist ".env" (
    echo ERROR: .env file not found!
    echo.
    echo Please create .env from .env.example:
    echo    copy .env.example .env
    echo.
    echo Then edit .env and set your tokens:
    echo    - BOT_TOKEN_MASTER
    echo    - BOT_TOKEN_SALES
    echo    - POSTGRES_PASSWORD
    echo    - YOOKASSA_SHOP_ID
    echo    - YOOKASSA_SECRET_KEY
    pause
    exit /b 1
)
echo       .env: OK

echo [3/4] Checking requirements.txt...
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found!
    echo.
    echo Please run: git pull
    pause
    exit /b 1
)
echo       requirements.txt: OK

echo [4/4] Checking Docker network...
docker network inspect booking-network >nul 2>&1
if errorlevel 1 (
    echo       Creating booking-network...
    docker network create booking-network >nul 2>&1
    if errorlevel 1 (
        echo       WARNING: Could not create network (may already exist)
    ) else (
        echo       Network created: OK
    )
) else (
    echo       booking-network: OK
)
echo.
echo ✅ All pre-flight checks passed!
echo.

REM ====================
REM STEP 1: STOP ALL CONTAINERS
REM ====================
echo ==================================
echo  STEP 1: STOPPING CONTAINERS
echo ==================================
echo.

echo Stopping bot containers...
docker-compose %COMPOSE_FILE% down 2>nul
echo.

echo Stopping infrastructure...
docker-compose -f docker-compose.postgres.yml down 2>nul
docker-compose -f docker-compose.redis.yml down 2>nul
echo.
echo ✅ All containers stopped
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
echo ✅ Old images removed
echo.

REM ====================
REM STEP 3: START INFRASTRUCTURE
REM ====================
echo ==================================
echo  STEP 3: STARTING INFRASTRUCTURE
echo ==================================
echo.

echo [1/2] Starting PostgreSQL...
docker-compose -f docker-compose.postgres.yml up -d
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start PostgreSQL!
    echo.
    echo Troubleshooting:
    echo   1. Check docker-compose.postgres.yml exists
    echo   2. Check logs: docker-compose -f docker-compose.postgres.yml logs
    echo   3. Try: docker-compose -f docker-compose.postgres.yml up
    pause
    exit /b 1
)
echo       PostgreSQL starting...
echo.

echo [2/2] Starting Redis...
docker-compose -f docker-compose.redis.yml up -d
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start Redis!
    echo.
    echo Troubleshooting:
    echo   1. Check docker-compose.redis.yml exists
    echo   2. Check logs: docker-compose -f docker-compose.redis.yml logs
    pause
    exit /b 1
)
echo       Redis starting...
echo.

echo Waiting for infrastructure to be healthy (15 seconds)...
timeout /t 15 /nobreak >nul
echo.

REM ====================
REM STEP 4: VERIFY INFRASTRUCTURE
REM ====================
echo ==================================
echo  STEP 4: VERIFYING INFRASTRUCTURE
echo ==================================
echo.

echo [1/2] Checking PostgreSQL health...
docker exec postgres-shared pg_isready -U booking_admin >nul 2>&1
if errorlevel 1 (
    echo ERROR: PostgreSQL is not healthy!
    echo.
    echo Checking logs:
    docker-compose -f docker-compose.postgres.yml logs --tail=20
    echo.
    echo Please fix PostgreSQL and try again.
    pause
    exit /b 1
)
echo       PostgreSQL: HEALTHY ✅

echo [2/2] Checking Redis health...
docker exec booking-bot-redis-shared redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo ERROR: Redis is not healthy!
    echo.
    echo Checking logs:
    docker-compose -f docker-compose.redis.yml logs --tail=20
    echo.
    echo Please fix Redis and try again.
    pause
    exit /b 1
)
echo       Redis: HEALTHY ✅
echo.
echo ✅ Infrastructure ready!
echo.

REM ====================
REM STEP 5: BUILD BOT IMAGES
REM ====================
echo ==================================
echo  STEP 5: BUILDING BOT IMAGES
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
echo ✅ Build successful!
echo.

REM ====================
REM STEP 6: START BOT CONTAINERS
REM ====================
echo ==================================
echo  STEP 6: STARTING BOT CONTAINERS
echo ==================================
echo.

docker-compose %COMPOSE_FILE% up -d
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start bot containers!
    echo.
    echo Check logs:
    echo    docker-compose %COMPOSE_FILE% logs
    pause
    exit /b 1
)
echo.
echo ✅ Bots started!
echo.

echo Waiting for startup (10 seconds)...
timeout /t 10 /nobreak >nul
echo.

REM ====================
REM STEP 7: VERIFY DEPLOYMENT
REM ====================
echo ==================================
echo  STEP 7: DEPLOYMENT STATUS
echo ==================================
echo.

echo [Infrastructure]
docker-compose -f docker-compose.postgres.yml ps
echo.
docker-compose -f docker-compose.redis.yml ps
echo.

echo [Bots - %MODE_NAME%]
docker-compose %COMPOSE_FILE% ps
echo.

REM ====================
REM STEP 8: SHOW LOGS
REM ====================
echo ==================================
echo  STEP 8: RECENT LOGS
echo ==================================
echo.

if "%MODE%"=="production" (
    echo [PostgreSQL]
    docker-compose -f docker-compose.postgres.yml logs --tail=10 postgres
    echo.
    
    echo [Redis]
    docker-compose -f docker-compose.redis.yml logs --tail=10 redis-shared
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
echo  ✅ DEPLOYMENT COMPLETE!
echo ========================================
echo.
echo Mode: %MODE_NAME%
echo.
echo Services running:
echo   - PostgreSQL (port 5432)
echo   - Redis (port 6379)

if "%MODE%"=="production" (
    echo   - Master Bot (Telegram)
    echo   - Master Bot API (port 8000)
    echo   - Sales Bot (Telegram)
    echo   - Sales Webhook (port 8001)
    echo.
    echo Next steps:
    echo   1. Configure Nginx for ports 8000 and 8001
    echo   2. Set up YooKassa webhook: https://yourdomain.com/yookassa/webhook
    echo   3. Test Master Bot API: http://localhost:8000/docs
) else (
    echo   - Master Bot (Telegram)
    echo   - Sales Bot (Telegram)
    echo.
    echo Next steps:
    echo   1. Open Telegram and find your bots
    echo   2. Send /start to Master Bot
    echo   3. Configure services in admin panel
)

echo.
echo Useful commands:
echo   - View logs:     docker-compose %COMPOSE_FILE% logs -f
echo   - Restart:       docker-compose %COMPOSE_FILE% restart
echo   - Stop:          docker-compose %COMPOSE_FILE% down
echo   - Status:        docker-compose %COMPOSE_FILE% ps
echo.
echo   - PostgreSQL:    docker exec -it postgres-shared psql -U booking_admin -d postgres
echo   - Redis:         docker exec -it booking-bot-redis-shared redis-cli
echo.
echo For production deployment:
echo   - Run: rebuild.bat production
echo   - See: docs/DEPLOYMENT.md
echo.
pause
