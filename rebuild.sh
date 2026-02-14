#!/bin/bash
# ✅ Quick rebuild script for both bots
# Usage: ./rebuild.sh

echo "=================================="
echo " REBUILDING BOTH BOTS"
echo "=================================="
echo ""

# 1. Stop all containers
echo "1. Stopping containers..."
docker-compose down

# 2. Remove old images
echo "2. Removing old images..."
docker rmi new12_02-bot-master new12_02-bot-sales 2>/dev/null || true

# 3. Clean build cache
echo "3. Cleaning build cache..."
docker builder prune -f

# 4. Rebuild with no cache
echo "4. Building images from scratch..."
docker-compose build --no-cache

# 5. Start containers
echo "5. Starting containers..."
docker-compose up -d

# 6. Show status
echo ""
echo "=================================="
echo " STATUS"
echo "=================================="
docker-compose ps

echo ""
echo "✅ Done! Check logs with:"
echo "   docker-compose logs -f bot-master"
echo "   docker-compose logs -f bot-sales"
