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

# ============================================
# VALIDATION FUNCTIONS
# ============================================

validate_bot_token() {
    local token="$1"
    
    if [[ ! "$token" =~ ^[0-9]+:[A-Za-z0-9_-]{35,}$ ]]; then
        echo "❌ Invalid BOT_TOKEN format"
        echo "Expected: 123456789:ABCdef_GHIjkl-MNOpqr..."
        return 1
    fi
    return 0
}

check_postgres_ready() {
    if ! docker ps | grep -q postgres-shared; then
        echo "❌ PostgreSQL container 'postgres-shared' not running!"
        echo "Run: ./scripts/deploy_infrastructure.sh first"
        return 1
    fi
    
    if ! docker exec postgres-shared pg_isready -U booking_admin > /dev/null 2>&1; then
        echo "❌ PostgreSQL not accepting connections"
        return 1
    fi
    
    return 0
}

check_required_files() {
    local missing=0
    
    for file in "main.py" "config.py" "requirements.txt"; do
        if [ ! -f "$file" ]; then
            echo "❌ Missing required file: $file"
            missing=1
        fi
    done
    
    for dir in "database" "handlers" "utils" "middlewares"; do
        if [ ! -d "$dir" ]; then
            echo "❌ Missing required directory: $dir"
            missing=1
        fi
    done
    
    if [ $missing -eq 1 ]; then
        echo "❌ Cannot proceed without core files"
        return 1
    fi
    
    return 0
}

# ============================================
# MAIN SCRIPT
# ============================================

if [ -z "$CLIENT_ID" ] || [ -z "$BOT_TOKEN" ]; then
    echo "❌ Usage: $0 <client_id> <bot_token> [admin_id]"
    echo "Example: $0 b2fb2108 '123456:ABC-DEF' 1720268937"
    exit 1
fi

echo "🔍 Validating bot token..."
if ! validate_bot_token "$BOT_TOKEN"; then
    exit 1
fi
echo "✅ Bot token format valid"

echo "🔍 Checking required files..."
if ! check_required_files; then
    exit 1
fi
echo "✅ All required files present"

# Load shared configuration
if [ ! -f ".env.shared.local" ]; then
    echo "❌ Error: .env.shared.local not found!"
    echo "Create it from .env.shared.example:"
    echo "  cp .env.shared.example .env.shared.local"
    echo "  nano .env.shared.local  # Edit passwords"
    exit 1
fi

source .env.shared.local

echo "🔍 Checking PostgreSQL..."
if ! check_postgres_ready; then
    exit 1
fi
echo "✅ PostgreSQL is ready"

CLIENT_DIR="clients/${CLIENT_ID}"
DB_NAME="client_${CLIENT_ID}_db"
DB_USER="client_${CLIENT_ID}_user"

echo ""
echo "🚀 Setting up client: ${CLIENT_ID}"
echo "   Database: ${DB_NAME}"
echo "   User: ${DB_USER}"
echo ""

# Create client directory
mkdir -p "${CLIENT_DIR}/{data,backups,logs,locales,database}"

# Copy core files with validation
echo "📦 Copying core files..."
cp -r database/*.py "${CLIENT_DIR}/database/" || { echo "❌ Failed to copy database files"; exit 1; }
cp main.py config.py requirements.txt "${CLIENT_DIR}/" || { echo "❌ Failed to copy core files"; exit 1; }
cp -r handlers utils middlewares "${CLIENT_DIR}/" || { echo "❌ Failed to copy handlers/utils/middlewares"; exit 1; }

if [ -d "locales" ]; then
    cp -r locales/* "${CLIENT_DIR}/locales/" 2>/dev/null || echo "⚠️  No locales to copy"
fi

echo "✅ Files copied successfully"

# Create .env file
echo "⚙️  Creating .env file..."
cat > "${CLIENT_DIR}/.env" << EOF
# Client-specific configuration
CLIENT_ID=${CLIENT_ID}
BOT_TOKEN=${BOT_TOKEN}
ADMIN_IDS=${ADMIN_ID}

# Database Configuration (from .env.shared.local)
DB_TYPE=${DB_TYPE}
DATABASE_URL=postgresql://${DB_USER}:${DB_USER_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${DB_NAME}
DB_POOL_MIN_SIZE=${DB_POOL_MIN_SIZE}
DB_POOL_MAX_SIZE=${DB_POOL_MAX_SIZE}
DB_POOL_TIMEOUT=${DB_POOL_TIMEOUT}
DB_COMMAND_TIMEOUT=${DB_COMMAND_TIMEOUT}

# Redis Configuration (from .env.shared.local)
REDIS_ENABLED=${REDIS_ENABLED}
REDIS_HOST=${REDIS_HOST}
REDIS_PORT=${REDIS_PORT}
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_DB=0

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
BACKUP_RETENTION_DAYS=30
EOF

echo "✅ .env created"

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

echo "✅ docker-compose.yml created"

# Copy Dockerfile
if [ ! -f "${CLIENT_DIR}/Dockerfile" ]; then
    echo "📄 Creating Dockerfile..."
    cat > "${CLIENT_DIR}/Dockerfile" << 'EODOCKERFILE'
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
EODOCKERFILE
    echo "✅ Dockerfile created"
fi

echo "🗄️  Creating PostgreSQL database and user..."

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

if [ $? -ne 0 ]; then
    echo "❌ Failed to create database"
    exit 1
fi

echo "✅ Database created"

# Grant schema privileges
docker exec -i postgres-shared psql -U ${POSTGRES_ADMIN_USER} -d ${DB_NAME} << EOSQL
GRANT ALL ON SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
EOSQL

echo "✅ Schema privileges granted"

# Build and start container
echo "🐳 Building and starting Docker container..."
cd "${CLIENT_DIR}"
docker-compose build --no-cache
docker-compose up -d

if [ $? -ne 0 ]; then
    echo "❌ Failed to start container"
    exit 1
fi

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
