#!/bin/bash

echo "🚀 Starting Bot Pool System"
echo "======================================"

if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Copy .env.example to .env and configure it"
    exit 1
fi

echo "🛑 Stopping old containers..."
docker-compose -f docker-compose.pool.full.yml down

echo "🔨 Building images..."
docker-compose -f docker-compose.pool.full.yml build

echo "🚀 Starting infrastructure..."
docker-compose -f docker-compose.pool.full.yml up -d postgres redis

echo "⏳ Waiting for PostgreSQL..."
sleep 10

echo "🏊 Starting bot pool (10 containers)..."
docker-compose -f docker-compose.pool.full.yml up -d

echo ""
echo "✅ System started!"
echo "======================================"
docker-compose -f docker-compose.pool.full.yml ps

echo ""
echo "📊 Check logs:"
echo "  docker-compose -f docker-compose.pool.full.yml logs -f bot-pool-1"
echo ""
echo "🏊 Pool status:"
echo "  docker-compose -f docker-compose.pool.full.yml logs bot-pool-1 | grep WAITING"
