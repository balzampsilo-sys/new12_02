#!/bin/bash
# Restart Master Bot with PostgreSQL

echo "🔄 Restarting Master Bot..."

# Stop Master Bot
docker-compose stop bot-master

# Rebuild image
docker-compose build bot-master

# Start Master Bot
docker-compose up -d bot-master

# Show logs
echo ""
echo "✅ Master Bot restarted!"
echo ""
echo "📋 Logs:"
docker-compose logs -f bot-master
