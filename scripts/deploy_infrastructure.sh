#!/bin/bash
set -e

# ============================================
# INFRASTRUCTURE DEPLOYMENT SCRIPT
# ============================================
# This script deploys PostgreSQL and Redis
# Must be run BEFORE creating any clients

echo "🚀 Deploying infrastructure..."

# Load shared configuration
if [ ! -f ".env.shared.local" ]; then
    echo "❌ Error: .env.shared.local not found!"
    echo "Create it from .env.shared.example:"
    echo "  cp .env.shared.example .env.shared.local"
    echo "  nano .env.shared.local  # Edit passwords"
    exit 1
fi

source .env.shared.local

# Validate required variables
if [ -z "$POSTGRES_ADMIN_PASSWORD" ] || [ "$POSTGRES_ADMIN_PASSWORD" = "CHANGE_ME_STRONG_PASSWORD" ]; then
    echo "❌ Please set POSTGRES_ADMIN_PASSWORD in .env.shared.local"
    exit 1
fi

if [ -z "$DB_USER_PASSWORD" ] || [ "$DB_USER_PASSWORD" = "CHANGE_ME_CLIENT_PASSWORD" ]; then
    echo "❌ Please set DB_USER_PASSWORD in .env.shared.local"
    exit 1
fi

if [ -z "$REDIS_PASSWORD" ] || [ "$REDIS_PASSWORD" = "CHANGE_ME_REDIS_PASSWORD" ]; then
    echo "⚠️  Warning: REDIS_PASSWORD not set, Redis will run without auth"
    REDIS_PASSWORD=""
fi

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
EOF

# Add Redis command based on password
if [ -n "$REDIS_PASSWORD" ]; then
    cat >> docker-compose.infrastructure.yml << EOF
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
EOF
else
    cat >> docker-compose.infrastructure.yml << EOF
    command: redis-server --appendonly yes
EOF
fi

# Continue Redis config
cat >> docker-compose.infrastructure.yml << EOF
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT}:6379"
    restart: unless-stopped
    healthcheck:
EOF

# Add health check based on password
if [ -n "$REDIS_PASSWORD" ]; then
    cat >> docker-compose.infrastructure.yml << EOF
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
EOF
else
    cat >> docker-compose.infrastructure.yml << EOF
      test: ["CMD", "redis-cli", "ping"]
EOF
fi

# Finish docker-compose
cat >> docker-compose.infrastructure.yml << EOF
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

echo "✅ docker-compose.infrastructure.yml created"

# Create init scripts directory
mkdir -p init-scripts

echo "🐳 Starting infrastructure containers..."
docker-compose -f docker-compose.infrastructure.yml up -d

if [ $? -ne 0 ]; then
    echo "❌ Failed to start infrastructure"
    exit 1
fi

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker exec postgres-shared pg_isready -U ${POSTGRES_ADMIN_USER} > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL failed to start"
        echo "Check logs: docker logs postgres-shared"
        exit 1
    fi
    echo "   Attempt $i/30..."
    sleep 2
done

# Wait for Redis to be ready
echo "⏳ Waiting for Redis to be ready..."
for i in {1..15}; do
    if [ -n "$REDIS_PASSWORD" ]; then
        if docker exec redis-shared redis-cli -a "$REDIS_PASSWORD" ping > /dev/null 2>&1; then
            echo "✅ Redis is ready!"
            break
        fi
    else
        if docker exec redis-shared redis-cli ping > /dev/null 2>&1; then
            echo "✅ Redis is ready!"
            break
        fi
    fi
    
    if [ $i -eq 15 ]; then
        echo "❌ Redis failed to start"
        echo "Check logs: docker logs redis-shared"
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
if [ -n "$REDIS_PASSWORD" ]; then
    echo "   Redis: Password protected"
else
    echo "   Redis: No password (not recommended for production)"
fi
echo "   Network: ${NETWORK_NAME}"
echo ""
echo "🔑 Credentials:"
echo "   PostgreSQL Admin: ${POSTGRES_ADMIN_USER} / [hidden]"
echo "   Client Password: [hidden]"
echo ""
echo "🚀 Next steps:"
echo "   1. Run: ./scripts/setup_client.sh <client_id> <bot_token>"
echo "   2. Example: ./scripts/setup_client.sh b2fb2108 '123456:ABC-DEF'"
echo ""
echo "🔍 View logs:"
echo "   docker-compose -f docker-compose.infrastructure.yml logs -f"
echo ""
echo "🛑 Stop infrastructure:"
echo "   docker-compose -f docker-compose.infrastructure.yml down"
echo ""
