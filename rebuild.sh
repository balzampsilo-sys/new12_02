#!/bin/bash
# ========================================
# FULL PLATFORM REBUILD SCRIPT (Linux/macOS)
# ========================================
# 
# Usage:
#   ./rebuild.sh              - Development mode (basic bots)
#   ./rebuild.sh production   - Production mode (all services)
# 
# What it does:
#   1. Checks prerequisites (.env, requirements.txt, Docker)
#   2. Starts PostgreSQL and Redis infrastructure
#   3. Waits for DB/Redis to be healthy
#   4. Rebuilds and starts bot containers
#   5. Shows status and logs
# 
# ========================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine mode
MODE=${1:-dev}

if [ "$MODE" = "production" ]; then
    echo "========================================"
    echo " PRODUCTION MODE"
    echo "========================================"
    COMPOSE_FILE="-f docker-compose.production.yml"
    MODE_NAME="PRODUCTION"
else
    echo "========================================"
    echo " DEVELOPMENT MODE"
    echo "========================================"
    COMPOSE_FILE=""
    MODE_NAME="DEVELOPMENT"
fi
echo ""

# ====================
# STEP 0: PRE-FLIGHT CHECKS
# ====================
echo "=================================="
echo " STEP 0: PRE-FLIGHT CHECKS"
echo "=================================="
echo ""

echo "[1/4] Checking Docker..."
if ! docker version &>/dev/null; then
    echo -e "${RED}ERROR: Docker is not running!${NC}"
    echo ""
    echo "Please start Docker and try again:"
    echo "  - Linux: sudo systemctl start docker"
    echo "  - macOS: Open Docker Desktop"
    exit 1
fi
echo "      Docker: OK"

echo "[2/4] Checking .env file..."
if [ ! -f ".env" ]; then
    echo -e "${RED}ERROR: .env file not found!${NC}"
    echo ""
    echo "Please create .env from .env.example:"
    echo "   cp .env.example .env"
    echo ""
    echo "Then edit .env and set your tokens:"
    echo "   - BOT_TOKEN_MASTER"
    echo "   - BOT_TOKEN_SALES"
    echo "   - POSTGRES_PASSWORD"
    echo "   - YOOKASSA_SHOP_ID"
    echo "   - YOOKASSA_SECRET_KEY"
    exit 1
fi
echo "      .env: OK"

echo "[3/4] Checking requirements.txt..."
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}ERROR: requirements.txt not found!${NC}"
    echo ""
    echo "Please run: git pull"
    exit 1
fi
echo "      requirements.txt: OK"

echo "[4/4] Checking Docker network..."
if ! docker network inspect booking-network &>/dev/null; then
    echo "      Creating booking-network..."
    docker network create booking-network &>/dev/null || echo "      WARNING: Could not create network (may already exist)"
    echo "      Network created: OK"
else
    echo "      booking-network: OK"
fi
echo ""
echo -e "${GREEN}✅ All pre-flight checks passed!${NC}"
echo ""

# ====================
# STEP 1: STOP ALL CONTAINERS
# ====================
echo "=================================="
echo " STEP 1: STOPPING CONTAINERS"
echo "=================================="
echo ""

echo "Stopping bot containers..."
docker-compose $COMPOSE_FILE down 2>/dev/null || true
echo ""

echo "Stopping infrastructure..."
docker-compose -f docker-compose.postgres.yml down 2>/dev/null || true
docker-compose -f docker-compose.redis.yml down 2>/dev/null || true
echo ""
echo -e "${GREEN}✅ All containers stopped${NC}"
echo ""

# ====================
# STEP 2: CLEAN OLD IMAGES
# ====================
echo "=================================="
echo " STEP 2: CLEANING OLD IMAGES"
echo "=================================="
echo ""

echo "Removing old bot images..."
docker images --filter=reference='new12_02*' -q | xargs -r docker rmi -f 2>/dev/null || true
echo ""

echo "Cleaning build cache..."
docker builder prune -f
echo ""
echo -e "${GREEN}✅ Old images removed${NC}"
echo ""

# ====================
# STEP 3: START INFRASTRUCTURE
# ====================
echo "=================================="
echo " STEP 3: STARTING INFRASTRUCTURE"
echo "=================================="
echo ""

echo "[1/2] Starting PostgreSQL..."
if ! docker-compose -f docker-compose.postgres.yml up -d; then
    echo ""
    echo -e "${RED}ERROR: Failed to start PostgreSQL!${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check docker-compose.postgres.yml exists"
    echo "  2. Check logs: docker-compose -f docker-compose.postgres.yml logs"
    echo "  3. Try: docker-compose -f docker-compose.postgres.yml up"
    exit 1
fi
echo "      PostgreSQL starting..."
echo ""

echo "[2/2] Starting Redis..."
if ! docker-compose -f docker-compose.redis.yml up -d; then
    echo ""
    echo -e "${RED}ERROR: Failed to start Redis!${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check docker-compose.redis.yml exists"
    echo "  2. Check logs: docker-compose -f docker-compose.redis.yml logs"
    exit 1
fi
echo "      Redis starting..."
echo ""

echo "Waiting for infrastructure to be healthy (15 seconds)..."
sleep 15
echo ""

# ====================
# STEP 4: VERIFY INFRASTRUCTURE
# ====================
echo "=================================="
echo " STEP 4: VERIFYING INFRASTRUCTURE"
echo "=================================="
echo ""

echo "[1/2] Checking PostgreSQL health..."
if ! docker exec postgres-shared pg_isready -U booking_admin &>/dev/null; then
    echo -e "${RED}ERROR: PostgreSQL is not healthy!${NC}"
    echo ""
    echo "Checking logs:"
    docker-compose -f docker-compose.postgres.yml logs --tail=20
    echo ""
    echo "Please fix PostgreSQL and try again."
    exit 1
fi
echo -e "      PostgreSQL: ${GREEN}HEALTHY ✅${NC}"

echo "[2/2] Checking Redis health..."
if ! docker exec booking-bot-redis-shared redis-cli ping &>/dev/null; then
    echo -e "${RED}ERROR: Redis is not healthy!${NC}"
    echo ""
    echo "Checking logs:"
    docker-compose -f docker-compose.redis.yml logs --tail=20
    echo ""
    echo "Please fix Redis and try again."
    exit 1
fi
echo -e "      Redis: ${GREEN}HEALTHY ✅${NC}"
echo ""
echo -e "${GREEN}✅ Infrastructure ready!${NC}"
echo ""

# ====================
# STEP 5: BUILD BOT IMAGES
# ====================
echo "=================================="
echo " STEP 5: BUILDING BOT IMAGES"
echo "=================================="
echo ""
echo "This will take 2-3 minutes..."
echo ""

if ! docker-compose $COMPOSE_FILE build --no-cache --progress=plain; then
    echo ""
    echo "========================================"
    echo " BUILD FAILED!"
    echo "========================================"
    echo ""
    echo "Common issues:"
    echo "  1. requirements.txt has syntax errors"
    echo "  2. Dockerfile is missing"
    echo "  3. Network issues downloading packages"
    echo ""
    echo "Check the output above for specific error."
    exit 1
fi
echo ""
echo -e "${GREEN}✅ Build successful!${NC}"
echo ""

# ====================
# STEP 6: START BOT CONTAINERS
# ====================
echo "=================================="
echo " STEP 6: STARTING BOT CONTAINERS"
echo "=================================="
echo ""

if ! docker-compose $COMPOSE_FILE up -d; then
    echo ""
    echo -e "${RED}ERROR: Failed to start bot containers!${NC}"
    echo ""
    echo "Check logs:"
    echo "   docker-compose $COMPOSE_FILE logs"
    exit 1
fi
echo ""
echo -e "${GREEN}✅ Bots started!${NC}"
echo ""

echo "Waiting for startup (10 seconds)..."
sleep 10
echo ""

# ====================
# STEP 7: VERIFY DEPLOYMENT
# ====================
echo "=================================="
echo " STEP 7: DEPLOYMENT STATUS"
echo "=================================="
echo ""

echo "[Infrastructure]"
docker-compose -f docker-compose.postgres.yml ps
echo ""
docker-compose -f docker-compose.redis.yml ps
echo ""

echo "[Bots - $MODE_NAME]"
docker-compose $COMPOSE_FILE ps
echo ""

# ====================
# STEP 8: SHOW LOGS
# ====================
echo "=================================="
echo " STEP 8: RECENT LOGS"
echo "=================================="
echo ""

if [ "$MODE" = "production" ]; then
    echo "[PostgreSQL]"
    docker-compose -f docker-compose.postgres.yml logs --tail=10 postgres
    echo ""
    
    echo "[Redis]"
    docker-compose -f docker-compose.redis.yml logs --tail=10 redis-shared
    echo ""
    
    echo "[Master Bot]"
    docker-compose $COMPOSE_FILE logs --tail=20 bot-master
    echo ""
    
    echo "[Master Bot API]"
    docker-compose $COMPOSE_FILE logs --tail=20 bot-master-api
    echo ""
    
    echo "[Sales Bot]"
    docker-compose $COMPOSE_FILE logs --tail=20 bot-sales
    echo ""
    
    echo "[Sales Webhook]"
    docker-compose $COMPOSE_FILE logs --tail=20 sales-webhook
    echo ""
else
    echo "[Master Bot]"
    docker-compose logs --tail=20 bot-master
    echo ""
    
    echo "[Sales Bot]"
    docker-compose logs --tail=20 bot-sales
    echo ""
fi

# ====================
# SUMMARY
# ====================
echo "========================================"
echo -e " ${GREEN}✅ DEPLOYMENT COMPLETE!${NC}"
echo "========================================"
echo ""
echo "Mode: $MODE_NAME"
echo ""
echo "Services running:"
echo "  - PostgreSQL (port 5432)"
echo "  - Redis (port 6379)"

if [ "$MODE" = "production" ]; then
    echo "  - Master Bot (Telegram)"
    echo "  - Master Bot API (port 8000)"
    echo "  - Sales Bot (Telegram)"
    echo "  - Sales Webhook (port 8001)"
    echo ""
    echo "Next steps:"
    echo "  1. Configure Nginx for ports 8000 and 8001"
    echo "  2. Set up YooKassa webhook: https://yourdomain.com/yookassa/webhook"
    echo "  3. Test Master Bot API: http://localhost:8000/docs"
else
    echo "  - Master Bot (Telegram)"
    echo "  - Sales Bot (Telegram)"
    echo ""
    echo "Next steps:"
    echo "  1. Open Telegram and find your bots"
    echo "  2. Send /start to Master Bot"
    echo "  3. Configure services in admin panel"
fi

echo ""
echo "Useful commands:"
echo "  - View logs:     docker-compose $COMPOSE_FILE logs -f"
echo "  - Restart:       docker-compose $COMPOSE_FILE restart"
echo "  - Stop:          docker-compose $COMPOSE_FILE down"
echo "  - Status:        docker-compose $COMPOSE_FILE ps"
echo ""
echo "  - PostgreSQL:    docker exec -it postgres-shared psql -U booking_admin -d postgres"
echo "  - Redis:         docker exec -it booking-bot-redis-shared redis-cli"
echo ""
echo "For production deployment:"
echo "  - Run: ./rebuild.sh production"
echo "  - See: docs/DEPLOYMENT.md"
echo ""
