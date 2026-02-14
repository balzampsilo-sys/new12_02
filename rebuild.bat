@echo off
REM ✅ Quick rebuild script for both bots (Windows)
REM Usage: rebuild.bat

echo ==================================
echo  REBUILDING BOTH BOTS
echo ==================================
echo.

REM 0. Check requirements.txt exists
echo 0. Checking files...
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found!
    echo Run: git pull
    pause
    exit /b 1
)
echo    requirements.txt: OK
echo.

REM 1. Stop all containers
echo 1. Stopping containers...
docker-compose down
echo.

REM 2. Remove old images
echo 2. Removing old images...
for /f "tokens=*" %%i in ('docker images --filter^=reference^=new12_02* -q 2^>nul') do (
    docker rmi %%i -f 2>nul
)
echo    Old images removed
echo.

REM 3. Clean build cache
echo 3. Cleaning build cache...
docker builder prune -f
echo.

REM 4. Rebuild with no cache (verbose)
echo 4. Building images from scratch...
echo    This will take 2-3 minutes...
echo.
docker-compose build --no-cache --progress=plain
if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    echo Check the output above for errors.
    pause
    exit /b 1
)
echo.
echo    Build successful!
echo.

REM 5. Start containers
echo 5. Starting containers...
docker-compose up -d
echo.

REM 6. Wait for startup
echo 6. Waiting for startup (5 seconds)...
timeout /t 5 /nobreak >nul
echo.

REM 7. Show status
echo ==================================
echo  STATUS
echo ==================================
docker-compose ps
echo.

REM 8. Show recent logs
echo ==================================
echo  RECENT LOGS (Master Bot)
echo ==================================
docker-compose logs --tail=20 bot-master
echo.

echo ==================================
echo  RECENT LOGS (Sales Bot)
echo ==================================
docker-compose logs --tail=20 bot-sales
echo.

echo ==================================
echo  SUMMARY
echo ==================================
echo.
echo ✅ Done! Both bots should be running.
echo.
echo To check if aiogram is installed:
echo    docker-compose exec bot-master python -c "import aiogram; print('aiogram', aiogram.__version__)"
echo.
echo To see live logs:
echo    docker-compose logs -f bot-master
echo    docker-compose logs -f bot-sales
echo.
pause
