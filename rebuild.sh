#!/bin/bash
# ✅ Quick rebuild script for both bots
# Usage: ./rebuild.sh

set -e  # Exit on error

echo "=================================="
echo " REBUILDING BOTH BOTS"
echo "=================================="
echo ""

# 0. Check requirements.txt exists
echo "0. Checking files..."
if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt not found!"
    echo "Run: git pull"
    exit 1
fi
echo "   requirements.txt: OK"
echo ""

# 1. Stop all containers
echo "1. Stopping containers..."
docker-compose down
echo ""

# 2. Remove old images
echo "2. Removing old images..."
docker rmi new12_02-bot-master new12_02-bot-sales 2>/dev/null || true
echo "   Old images removed"
echo ""

# 3. Clean build cache
echo "3. Cleaning build cache..."
docker builder prune -f
echo ""

# 4. Rebuild with no cache (verbose)
echo "4. Building images from scratch..."
echo "   This will take 2-3 minutes..."
echo ""
docker-compose build --no-cache --progress=plain
echo ""
echo "   Build successful!"
echo ""

# 5. Start containers
echo "5. Starting containers..."
docker-compose up -d
echo ""

# 6. Wait for startup
echo "6. Waiting for startup (5 seconds)..."
sleep 5
echo ""

# 7. Show status
echo "=================================="
echo " STATUS"
echo "=================================="
docker-compose ps
echo ""

# 8. Show recent logs
echo "=================================="
echo " RECENT LOGS (Master Bot)"
echo "=================================="
docker-compose logs --tail=20 bot-master
echo ""

echo "=================================="
echo " RECENT LOGS (Sales Bot)"
echo "=================================="
docker-compose logs --tail=20 bot-sales
echo ""

echo "=================================="
echo " SUMMARY"
echo "=================================="
echo ""
echo "✅ Done! Both bots should be running."
echo ""
echo "To check if aiogram is installed:"
echo "   docker-compose exec bot-master python -c \"import aiogram; print('aiogram', aiogram.__version__)\""
echo ""
echo "To see live logs:"
echo "   docker-compose logs -f bot-master"
echo "   docker-compose logs -f bot-sales"
echo ""
