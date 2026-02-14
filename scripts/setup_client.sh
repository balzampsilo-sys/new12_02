#!/bin/bash
set -e

# ============================================
# AUTOMATED CLIENT SETUP SCRIPT
# ============================================
# Usage: ./scripts/setup_client.sh <client_id> <bot_token>
# Example: ./scripts/setup_client.sh b2fb2108 "123456:ABC-DEF..."

CLIENT_ID="$1"
BOT_TOKEN="$2"
ADMIN_ID="${3:-1720268937}"  # Default admin ID

if [ -z "$CLIENT_ID" ] || [ -z "$BOT_TOKEN" ]; then
    echo "❌ Usage: $0 <client_id> <bot_token> [admin_id]"
    echo "Example: $0 b2fb2108 '123456:ABC-DEF' 1720268937"
    exit 1
fi

# Load shared configuration
if [ ! -f ".env.shared" ]; then
    echo "❌ Error: .env.shared not found!"
    echo "Please create .env.shared from .env.shared.example"
    exit 1
fi

source .env.shared

CLIENT_DIR="clients/${CLIENT_ID}"
DB_NAME="client_${CLIENT_ID}_db"
DB_USER="client_${CLIENT_ID}_user"

echo "🚀 Setting up client: ${CLIENT_ID}"
echo "   Database: ${DB_NAME}"
echo "   User: ${DB_USER}"

# Create client directory
mkdir -p "${CLIENT_DIR}/{data,backups,logs,locales,database}"

# Copy core files
echo "📦 Copying core files..."
cp -r database/*.py "${CLIENT_DIR}/database/"
cp -r locales/* "${CLIENT_DIR}/locales/" 2>/dev/null || echo "⚠️  No locales to copy"
cp main.py config.py "${CLIENT_DIR}/"
cp -r handlers utils middlewares "${CLIENT_DIR}/" 2>/dev/null || true

# Create .env file
echo "⚙️  Creating .env file..."
cat > "${CLIENT_DIR}/.env" << EOF
# Client-specific configuration
CLIENT_ID=${CLIENT_ID}
BOT_TOKEN=${BOT_TOKEN}
ADMIN_IDS=${ADMIN_ID}

# Database Configuration (from .env.shared)
DB_TYPE=${DB_TYPE}
DATABASE_URL=postgresql://${DB_USER}:${DB_USER_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${DB_NAME}
DB_POOL_MIN_SIZE=${DB_POOL_MIN_SIZE}
DB_POOL_MAX_SIZE=${DB_POOL_MAX_SIZE}
DB_POOL_TIMEOUT=${DB_POOL_TIMEOUT}
DB_COMMAND_TIMEOUT=${DB_COMMAND_TIMEOUT}

# Redis Configuration (from .env.shared)
REDIS_ENABLED=${REDIS_ENABLED}
REDIS_HOST=${REDIS_HOST}
REDIS_PORT=${REDIS_PORT}
REDIS_DB=0

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
BACKUP_RETENTION_DAYS=30
EOF

# Create docker-compose.yml
echo "🐳 Creating docker-compose.yml..."
cat > "${CLIENT_DIR}/docker-compose.yml" << EOF
version: '3.8'

services:
  bot:
    build:
      context: .
      dockerfile: Dockerfile

    container_name: bot-client-${CLIENT_ID}
    restart: unless-stopped

    env_file:
      - .env

    volumes:
      - ./data:/app/data
      - ./backups:/app/backups
      - ./logs:/app/logs
      - ./locales:/app/locales

    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

    healthcheck:
      test: ["CMD-SHELL", "python -c 'import sys; sys.exit(0)'"]
      interval: 30s
      timeout: 10s
      start_period: 5s
      retries: 3

networks:
  default:
    name: ${NETWORK_NAME}
    external: true
EOF

# Copy Dockerfile if not exists
if [ ! -f "${CLIENT_DIR}/Dockerfile" ]; then
    echo "📄 Creating Dockerfile..."
    cat > "${CLIENT_DIR}/Dockerfile" << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/backups /app/logs

CMD ["python", "main.py"]
EOF
fi

# Copy requirements.txt
if [ -f "requirements.txt" ]; then
    cp requirements.txt "${CLIENT_DIR}/"
else
    echo "⚠️  requirements.txt not found in root, creating minimal version..."
    cat > "${CLIENT_DIR}/requirements.txt" << EOF
aiogram==3.15.0
aiosqlite==0.20.0
asyncpg==0.30.0
python-dotenv==1.0.1
APScheduler==3.11.0
redis==5.2.1
PyYAML==6.0.2
EOF
fi

echo "🗄️  Creating PostgreSQL database and user..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
for i in {1..30}; do
    if docker exec postgres-shared pg_isready -U ${POSTGRES_ADMIN_USER} > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL not ready after 30 seconds"
        exit 1
    fi
    sleep 1
done

# Create database and user
docker exec -i postgres-shared psql -U ${POSTGRES_ADMIN_USER} -d ${POSTGRES_DEFAULT_DB} << EOSQL
-- Create database
CREATE DATABASE ${DB_NAME};

-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '${DB_USER}') THEN
        CREATE USER ${DB_USER} WITH PASSWORD '${DB_USER_PASSWORD}';
    END IF;
END
\$\$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};
EOSQL

# Grant schema privileges
docker exec -i postgres-shared psql -U ${POSTGRES_ADMIN_USER} -d ${DB_NAME} << EOSQL
GRANT ALL ON SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
EOSQL

echo "✅ Database ${DB_NAME} created with user ${DB_USER}"

# Build and start container
echo "🐳 Building and starting Docker container..."
cd "${CLIENT_DIR}"
docker-compose build --no-cache
docker-compose up -d

echo ""
echo "✅ Client ${CLIENT_ID} setup complete!"
echo ""
echo "📊 Status:"
echo "   Container: bot-client-${CLIENT_ID}"
echo "   Database: ${DB_NAME}"
echo "   Network: ${NETWORK_NAME}"
echo ""
echo "🔍 View logs:"
echo "   cd ${CLIENT_DIR} && docker-compose logs -f"
echo ""
echo "🛑 Stop client:"
echo "   cd ${CLIENT_DIR} && docker-compose down"
echo ""
