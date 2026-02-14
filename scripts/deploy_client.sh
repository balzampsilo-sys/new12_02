#!/bin/bash

# ========================================
# AUTOMATED CLIENT DEPLOYMENT SCRIPT
# ========================================
# 
# This script automates deployment of new bot clients
# Each client gets:
#   - Unique directory
#   - Isolated database
#   - Dedicated Redis DB (0-15)
#   - Independent Docker container
#
# Usage:
#   ./deploy_client.sh CLIENT_ID BOT_TOKEN ADMIN_ID REDIS_DB [COMPANY_NAME]
#
# Example:
#   ./deploy_client.sh client_001 "123456:ABCdef" 987654321 0 "Beauty Salon"
#
# ========================================

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Validation
if [ "$#" -lt 4 ]; then
    echo -e "${RED}❌ Usage: $0 CLIENT_ID BOT_TOKEN ADMIN_ID REDIS_DB [COMPANY_NAME]${NC}"
    echo ""
    echo "Example:"
    echo "  $0 client_001 \"123456:ABCdef\" 987654321 0 \"Beauty Salon\""
    echo ""
    echo "REDIS_DB must be 0-15 (unique for each client)"
    exit 1
fi

CLIENT_ID=$1
BOT_TOKEN=$2
ADMIN_ID=$3
REDIS_DB=$4
COMPANY_NAME=${5:-$CLIENT_ID}

# Validate REDIS_DB
if [ "$REDIS_DB" -lt 0 ] || [ "$REDIS_DB" -gt 15 ]; then
    echo -e "${RED}❌ Error: REDIS_DB must be between 0 and 15${NC}"
    exit 1
fi

echo -e "${GREEN}🚀 Deploying bot for: $COMPANY_NAME${NC}"
echo "   Client ID: $CLIENT_ID"
echo "   Redis DB: $REDIS_DB"
echo ""

# Project root (assuming script is in scripts/ directory)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLIENTS_DIR="$PROJECT_ROOT/clients"
CLIENT_DIR="$CLIENTS_DIR/$CLIENT_ID"

# Check if client already exists
if [ -d "$CLIENT_DIR" ]; then
    echo -e "${RED}❌ Error: Client directory already exists: $CLIENT_DIR${NC}"
    echo "   Use a different CLIENT_ID or remove existing directory"
    exit 1
fi

echo -e "${YELLOW}📁 Creating client directory...${NC}"
mkdir -p "$CLIENT_DIR"/{data,logs,backups,locales}

# Copy bot source files
echo -e "${YELLOW}📝 Copying bot files...${NC}"
cp -r "$PROJECT_ROOT"/{handlers,database,services,middlewares,utils,keyboards,main.py,config.py,requirements.txt,Dockerfile,.dockerignore} "$CLIENT_DIR/"

# Copy locales if exists
if [ -d "$PROJECT_ROOT/locales" ]; then
    cp -r "$PROJECT_ROOT/locales"/* "$CLIENT_DIR/locales/"
fi

# Create .env file
echo -e "${YELLOW}⚙️  Generating .env file...${NC}"
cat > "$CLIENT_DIR/.env" <<EOF
# ========================================
# BOT CONFIGURATION FOR: $COMPANY_NAME
# ========================================
# Generated: $(date)
# Client ID: $CLIENT_ID
# Redis DB: $REDIS_DB
# ========================================

# Bot Credentials
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_ID

# Redis Configuration (SHARED)
REDIS_ENABLED=True
REDIS_HOST=redis-shared
REDIS_PORT=6379
REDIS_DB=$REDIS_DB
REDIS_PASSWORD=

# Database
DATABASE_PATH=/app/data/bookings.db

# Backup Settings
BACKUP_ENABLED=True
BACKUP_DIR=/app/backups
BACKUP_INTERVAL_HOURS=24
BACKUP_RETENTION_DAYS=30

# Work Schedule
WORK_HOURS_START=9
WORK_HOURS_END=18

# Booking Settings
MAX_BOOKINGS_PER_USER=3
CANCELLATION_HOURS=24

# Reminders
REMINDER_HOURS_BEFORE_1H=1
REMINDER_HOURS_BEFORE_2H=2
REMINDER_HOURS_BEFORE_24H=24

# Feedback
FEEDBACK_HOURS_AFTER=2

# Service Info
SERVICE_LOCATION=Москва, ул. Примерная, 1

# Calendar
CALENDAR_MAX_MONTHS_AHEAD=3

# Sentry (optional)
SENTRY_ENABLED=False
SENTRY_DSN=
SENTRY_ENVIRONMENT=production

# Rate Limiting
RATE_LIMIT_MESSAGE=0.5
RATE_LIMIT_CALLBACK=0.3
EOF

# Create docker-compose.yml
echo -e "${YELLOW}🐳 Generating docker-compose.yml...${NC}"
cat > "$CLIENT_DIR/docker-compose.yml" <<EOF
version: '3.8'

services:
  bot:
    build:
      context: .
      dockerfile: Dockerfile
    
    container_name: bot-$CLIENT_ID
    
    restart: unless-stopped
    
    env_file:
      - .env
    
    environment:
      - REDIS_ENABLED=True
      - REDIS_HOST=redis-shared
      - REDIS_DB=$REDIS_DB
    
    volumes:
      - ./data:/app/data
      - ./backups:/app/backups
      - ./logs:/app/logs
      - ./locales:/app/locales
    
    networks:
      - bot-network
    
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

networks:
  bot-network:
    external: true
EOF

# Check if shared Redis is running
echo -e "${YELLOW}🔍 Checking shared Redis...${NC}"
if ! docker ps | grep -q "booking-bot-redis-shared"; then
    echo -e "${RED}⚠️  Warning: Shared Redis is not running!${NC}"
    echo "   Starting Redis now..."
    docker-compose -f "$PROJECT_ROOT/docker-compose.redis.yml" up -d
    sleep 3
fi

# Build and start bot
echo -e "${YELLOW}🔨 Building Docker image...${NC}"
cd "$CLIENT_DIR"
docker-compose build --no-cache

echo -e "${YELLOW}🚀 Starting bot container...${NC}"
docker-compose up -d

# Wait for container to start
sleep 2

# Check if container is running
if docker ps | grep -q "bot-$CLIENT_ID"; then
    echo ""
    echo -e "${GREEN}✅ ===========================================  ${NC}"
    echo -e "${GREEN}✅ BOT DEPLOYED SUCCESSFULLY!${NC}"
    echo -e "${GREEN}✅ ===========================================  ${NC}"
    echo ""
    echo -e "   🏪 Company: ${GREEN}$COMPANY_NAME${NC}"
    echo -e "   🆔 Client ID: ${GREEN}$CLIENT_ID${NC}"
    echo -e "   📁 Directory: ${GREEN}$CLIENT_DIR${NC}"
    echo -e "   🐳 Container: ${GREEN}bot-$CLIENT_ID${NC}"
    echo -e "   📊 Redis DB: ${GREEN}$REDIS_DB${NC}"
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo "   View logs:     docker logs bot-$CLIENT_ID -f"
    echo "   Stop bot:      docker-compose -f $CLIENT_DIR/docker-compose.yml stop"
    echo "   Restart bot:   docker-compose -f $CLIENT_DIR/docker-compose.yml restart"
    echo "   Remove bot:    docker-compose -f $CLIENT_DIR/docker-compose.yml down"
    echo ""
else
    echo -e "${RED}❌ Error: Container failed to start${NC}"
    echo "   Check logs: docker logs bot-$CLIENT_ID"
    exit 1
fi
