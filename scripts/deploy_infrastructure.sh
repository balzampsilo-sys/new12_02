#!/bin/bash
set -e

# ============================================
# INFRASTRUCTURE DEPLOYMENT SCRIPT
# ============================================
# This script deploys PostgreSQL and Redis
# Must be run BEFORE creating any clients

echo "🚀 Deploying infrastructure..."

# Load shared configuration
if [ ! -f ".env.shared" ]; then
    echo "❌ Error: .env.shared not found!"
    echo "Please create .env.shared from .env.shared.example"
    exit 1
fi

source .env.shared

# Create network if it doesn't exist
echo "🌐 Creating Docker network: ${NETWORK_NAME}"
docker network create ${NETWORK_NAME} 2>/dev/null || echo "ℹ️ Network already exists"

# Create docker-compose.yml for infrastructure
echo "📄 Creating infrastructure docker-compose.yml..."
cat > docker-compose.infrastructure.yml << EOF
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: postgres-shared
    environment:
      POSTGRES_USER: ${POSTGRES_ADMIN_USER}
      POSTGRES_PASSWORD: ${POSTGRES_ADMIN_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DEFAULT_DB}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d:ro
    ports:
      - "${POSTGRES_PORT}:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_ADMIN_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - booking-network

  redis:
    image: redis:7-alpine
    container_name: redis-shared
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:-''}
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT}:6379"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - booking-network

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

networks:
  booking-network:
    name: ${NETWORK_NAME}
    driver: bridge
EOF

# Create init scripts directory
mkdir -p init-scripts

echo "🐳 Starting infrastructure containers..."
docker-compose -f docker-compose.infrastructure.yml up -d

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker exec postgres-shared pg_isready -U ${POSTGRES_ADMIN_USER} > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL failed to start"
        exit 1
    fi
    echo "   Attempt $i/30..."
    sleep 2
done

# Wait for Redis to be ready
echo "⏳ Waiting for Redis to be ready..."
for i in {1..15}; do
    if docker exec redis-shared redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis is ready!"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "❌ Redis failed to start"
        exit 1
    fi
    echo "   Attempt $i/15..."
    sleep 1
done

echo ""
echo "✅ Infrastructure deployed successfully!"
echo ""
echo "📊 Status:"
echo "   PostgreSQL: postgres-shared (port ${POSTGRES_PORT})"
echo "   Redis: redis-shared (port ${REDIS_PORT})"
echo "   Network: ${NETWORK_NAME}"
echo ""
echo "🔑 Credentials:"
echo "   PostgreSQL Admin: ${POSTGRES_ADMIN_USER} / ${POSTGRES_ADMIN_PASSWORD}"
echo "   Client Password: ${DB_USER_PASSWORD}"
echo ""
echo "🚀 Next steps:"
echo "   1. Run: ./scripts/setup_client.sh <client_id> <bot_token>"
echo "   2. Example: ./scripts/setup_client.sh b2fb2108 '123456:ABC-DEF'"
echo ""
echo "🔍 View logs:"
echo "   docker-compose -f docker-compose.infrastructure.yml logs -f"
echo ""
