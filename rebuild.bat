@echo off
REM ✅ Quick rebuild script for both bots (Windows)
REM Usage: rebuild.bat

echo ==================================
echo  REBUILDING BOTH BOTS
echo ==================================
echo.

REM 1. Stop all containers
echo 1. Stopping containers...
docker-compose down

REM 2. Remove old images
echo 2. Removing old images...
for /f "tokens=*" %%i in ('docker images --filter^=reference^=new12_02* -q') do docker rmi %%i 2>nul

REM 3. Clean build cache
echo 3. Cleaning build cache...
docker builder prune -f

REM 4. Rebuild with no cache
echo 4. Building images from scratch...
docker-compose build --no-cache

REM 5. Start containers
echo 5. Starting containers...
docker-compose up -d

REM 6. Show status
echo.
echo ==================================
echo  STATUS
echo ==================================
docker-compose ps

echo.
echo ✅ Done! Check logs with:
echo    docker-compose logs -f bot-master
echo    docker-compose logs -f bot-sales
echo.
pause
