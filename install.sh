#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "═══════════════════════════════════════════════════════════════"
echo "  🤖 Telegram Booking Bot - Automated Installation"
echo "═══════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    print_warning "Please do not run as root"
    exit 1
fi

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    print_info "Detected OS: Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    print_info "Detected OS: macOS"
else
    print_error "Unsupported OS: $OSTYPE"
    exit 1
fi

# Check if Docker is installed
print_info "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    print_warning "Docker not found. Installing Docker..."
    
    if [ "$OS" == "linux" ]; then
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        rm get-docker.sh
        print_success "Docker installed successfully"
        print_warning "Please logout and login again for Docker permissions to take effect"
        print_info "Then run this script again"
        exit 0
    elif [ "$OS" == "macos" ]; then
        print_error "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
        exit 1
    fi
else
    print_success "Docker is already installed"
fi

# Check if Docker Compose is installed
print_info "Checking Docker Compose installation..."
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_warning "Docker Compose not found. Installing..."
    
    if [ "$OS" == "linux" ]; then
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        print_success "Docker Compose installed successfully"
    fi
else
    print_success "Docker Compose is already installed"
fi

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found. Creating from template..."
    
    if [ -f .env.example ]; then
        cp .env.example .env
        print_success ".env file created"
    else
        print_error ".env.example not found"
        exit 1
    fi
fi

# Interactive configuration
echo ""
print_info "Configuration Setup"
echo "═══════════════════════════════════════════════════════════════"

# Check if BOT_TOKEN is set
if ! grep -q "BOT_TOKEN=.*[^[:space:]]" .env || grep -q "BOT_TOKEN=1234567890" .env; then
    echo ""
    print_warning "Telegram Bot Token not configured"
    read -p "Enter your Telegram Bot Token (from @BotFather): " bot_token
    
    if [ -z "$bot_token" ]; then
        print_error "Bot token cannot be empty"
        exit 1
    fi
    
    sed -i.bak "s/BOT_TOKEN=.*/BOT_TOKEN=$bot_token/" .env
    rm .env.bak 2>/dev/null || true
    print_success "Bot token configured"
else
    print_success "Bot token already configured"
fi

# Check if ADMIN_IDS is set
if ! grep -q "ADMIN_IDS=.*[^[:space:]]" .env || grep -q "ADMIN_IDS=123456789" .env; then
    echo ""
    print_warning "Admin IDs not configured"
    read -p "Enter Admin Telegram IDs (comma-separated): " admin_ids
    
    if [ -z "$admin_ids" ]; then
        print_error "Admin IDs cannot be empty"
        exit 1
    fi
    
    sed -i.bak "s/ADMIN_IDS=.*/ADMIN_IDS=$admin_ids/" .env
    rm .env.bak 2>/dev/null || true
    print_success "Admin IDs configured"
else
    print_success "Admin IDs already configured"
fi

# Ask about Sentry
echo ""
read -p "Do you want to enable Sentry error monitoring? (y/N): " enable_sentry
if [[ $enable_sentry =~ ^[Yy]$ ]]; then
    read -p "Enter your Sentry DSN: " sentry_dsn
    
    if [ ! -z "$sentry_dsn" ]; then
        sed -i.bak "s/SENTRY_ENABLED=.*/SENTRY_ENABLED=True/" .env
        sed -i.bak "s|# SENTRY_DSN=.*|SENTRY_DSN=$sentry_dsn|" .env
        rm .env.bak 2>/dev/null || true
        print_success "Sentry configured"
    fi
fi

# Enable Redis by default
sed -i.bak "s/REDIS_ENABLED=.*/REDIS_ENABLED=True/" .env
rm .env.bak 2>/dev/null || true

# Create necessary directories
print_info "Creating directories..."
mkdir -p data backups logs
print_success "Directories created"

# Build and start containers
echo ""
print_info "Building and starting containers..."
echo "═══════════════════════════════════════════════════════════════"

if docker compose version &> /dev/null; then
    docker compose build
    docker compose up -d
else
    docker-compose build
    docker-compose up -d
fi

if [ $? -eq 0 ]; then
    print_success "Bot started successfully!"
else
    print_error "Failed to start bot"
    exit 1
fi

# Wait for containers to be healthy
print_info "Waiting for services to be ready..."
sleep 5

# Check container status
if docker compose version &> /dev/null; then
    docker compose ps
else
    docker-compose ps
fi

echo ""
echo -e "${GREEN}"
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Installation Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo -e "${NC}"

print_info "Bot is running in the background"
print_info "Data will be stored in: ./data/"
print_info "Backups will be stored in: ./backups/"
print_info "Logs will be stored in: ./logs/"

echo ""
print_info "Useful commands:"
echo "  - View logs:       docker compose logs -f bot"
echo "  - Stop bot:        docker compose stop"
echo "  - Start bot:       docker compose start"
echo "  - Restart bot:     docker compose restart"
echo "  - Update bot:      git pull && docker compose up -d --build"
echo "  - Remove all:      docker compose down -v"

echo ""
print_info "Redis is running on localhost:6379"
print_info "Password: botredis123 (change in .env: REDIS_PASSWORD)"

echo ""
print_success "Your bot is ready! Open Telegram and send /start"
