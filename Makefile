# Makefile for PostgreSQL Booking Bot

.PHONY: help setup start stop restart logs logs-postgres logs-redis psql redis-cli clean test build

help:
	@echo "PostgreSQL Booking Bot - Available Commands:"
	@echo ""
	@echo "  make setup         - Initialize database and dependencies"
	@echo "  make start         - Start all services (bot, postgres, redis)"
	@echo "  make stop          - Stop all services"
	@echo "  make restart       - Restart all services"
	@echo "  make logs          - Show bot logs (follow mode)"
	@echo "  make logs-postgres - Show PostgreSQL logs"
	@echo "  make logs-redis    - Show Redis logs"
	@echo "  make psql          - Connect to PostgreSQL"
	@echo "  make redis-cli     - Connect to Redis CLI"
	@echo "  make clean         - Remove all volumes (⚠️  destroys data)"
	@echo "  make build         - Rebuild Docker images"
	@echo "  make test          - Run tests"
	@echo ""

setup:
	@echo "🚀 Setting up PostgreSQL Booking Bot..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "📋 .env file created from .env.example"; \
		echo "⚠️  Please edit .env and add your BOT_TOKEN and ADMIN_IDS"; \
	else \
		echo "✅ .env file already exists"; \
	fi
	@echo "⏳ Starting PostgreSQL and Redis..."
	@docker-compose up -d postgres redis
	@echo "⏳ Waiting for PostgreSQL to be ready..."
	@sleep 15
	@echo "✅ PostgreSQL is ready!"
	@echo "✅ Redis is ready!"
	@echo ""
	@echo "📝 Next steps:"
	@echo "  1. Edit .env file with your bot token: nano .env"
	@echo "  2. Start the bot: make start"
	@echo "  3. Check logs: make logs"
	@echo ""

start:
	@echo "🚀 Starting all services..."
	@docker-compose up -d
	@echo "✅ All services started!"
	@echo "📋 Check logs with: make logs"

stop:
	@echo "🛑 Stopping all services..."
	@docker-compose down
	@echo "✅ All services stopped"

restart: stop start

logs:
	@echo "📜 Showing bot logs (Ctrl+C to exit)..."
	@docker-compose logs -f bot

logs-postgres:
	@echo "📜 Showing PostgreSQL logs..."
	@docker-compose logs -f postgres

logs-redis:
	@echo "📜 Showing Redis logs..."
	@docker-compose logs -f redis

psql:
	@echo "🔗 Connecting to PostgreSQL..."
	@docker-compose exec postgres psql -U booking_user -d booking_db

redis-cli:
	@echo "🔗 Connecting to Redis..."
	@docker-compose exec redis redis-cli

build:
	@echo "🔨 Rebuilding Docker images..."
	@docker-compose build --no-cache
	@echo "✅ Build complete!"

clean:
	@echo "⚠️  WARNING: This will delete ALL data (database, redis, backups)!"
	@read -p "Are you sure? Type 'yes' to confirm: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose down -v; \
		echo "✅ All volumes deleted"; \
	else \
		echo "❌ Cancelled"; \
	fi

test:
	@echo "🧪 Running tests..."
	@docker-compose exec bot pytest tests/ -v --cov=. --cov-report=html || echo "⚠️  Tests not configured yet"

# Database management
db-backup:
	@echo "💾 Creating database backup..."
	@docker-compose exec postgres pg_dump -U booking_user -d booking_db > backups/manual_backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created in backups/"

db-restore:
	@echo "⚠️  This will restore database from backup"
	@read -p "Enter backup filename: " filename; \
	if [ -f "backups/$$filename" ]; then \
		cat "backups/$$filename" | docker-compose exec -T postgres psql -U booking_user -d booking_db; \
		echo "✅ Database restored"; \
	else \
		echo "❌ Backup file not found: $$filename"; \
	fi

# Development helpers
shell:
	@docker-compose exec bot /bin/bash

stats:
	@echo "📊 Docker stats:"
	@docker stats --no-stream booking_bot booking_postgres booking_redis
