# 🚀 DEPLOYMENT GUIDE: Multi-Client Bot Setup

## 🎯 Architecture Overview

This bot uses a **managed SaaS model** where:
- **One Redis** serves all bot instances (using different DB numbers 0-15)
- **Each client** gets their own bot container with isolated database
- **You manage** all deployments on your server

```
┌──────────────────────────────────────────────┐
│         SHARED REDIS (booking-bot-redis-shared)         │
│  ┌────────────────────────────────────────┐  │
│  │ DB 0 → Bot Client 1 (Beauty Salon)        │  │
│  │ DB 1 → Bot Client 2 (Massage Parlor)      │  │
│  │ DB 2 → Bot Client 3 (Nail Studio)         │  │
│  │ ...                                        │  │
│  │ DB 15 → Bot Client 16                     │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
          │                │                │
          ↓                ↓                ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ bot-client-1 │  │ bot-client-2 │  │ bot-client-3 │
│   (DB 0)     │  │   (DB 1)     │  │   (DB 2)     │
│ bookings.db  │  │ bookings.db  │  │ bookings.db  │
└─────────────┘  └─────────────┘  └─────────────┘
```

---

## 🛠️ Initial Setup (One Time)

### 1. **Install Docker**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io docker-compose -y
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect
```

### 2. **Clone Repository**

```bash
git clone https://github.com/balzampsilo-sys/new12_02.git
cd new12_02
```

### 3. **Create Directory Structure**

```bash
mkdir -p clients redis_data
```

### 4. **Start Shared Redis (Once)**

```bash
# Start shared Redis container
docker-compose -f docker-compose.redis.yml up -d

# Verify Redis is running
docker ps | grep redis

# Should see:
# booking-bot-redis-shared
```

---

## 👥 Deploying Clients

### **Method 1: Automated Script (Recommended)**

```bash
# Make script executable
chmod +x scripts/deploy_client.sh

# Deploy new client
./scripts/deploy_client.sh CLIENT_ID "BOT_TOKEN" ADMIN_ID REDIS_DB "Company Name"
```

**Example:**

```bash
# Client 1: Beauty Salon
./scripts/deploy_client.sh client_001 "123456789:ABCdefGHI" 987654321 0 "Beauty Salon"

# Client 2: Massage Parlor
./scripts/deploy_client.sh client_002 "234567890:XYZabcDEF" 123456789 1 "Massage Parlor"

# Client 3: Nail Studio
./scripts/deploy_client.sh client_003 "345678901:QWErtyUIO" 456789012 2 "Nail Studio"
```

**IMPORTANT:** 
- Each client MUST have a unique `REDIS_DB` (0-15)
- Maximum 16 clients per Redis instance
- BOT_TOKEN: Get from @BotFather
- ADMIN_ID: Get from @userinfobot

---

### **Method 2: Manual Deployment**

```bash
# 1. Create client directory
mkdir -p clients/client_001
cd clients/client_001

# 2. Copy bot files
cp -r ../../{handlers,database,services,middlewares,utils,keyboards,main.py,config.py,requirements.txt,Dockerfile,.dockerignore} .

# 3. Create .env file
cat > .env <<EOF
BOT_TOKEN=your_bot_token
ADMIN_IDS=your_telegram_id

REDIS_ENABLED=True
REDIS_HOST=redis-shared
REDIS_PORT=6379
REDIS_DB=0

DATABASE_PATH=/app/data/bookings.db
BACKUP_ENABLED=True
WORK_HOURS_START=9
WORK_HOURS_END=18
EOF

# 4. Copy docker-compose.yml from root and modify
cp ../../docker-compose.yml .
# Edit container_name to: bot-client-001

# 5. Start bot
docker-compose up -d --build
```

---

## 📊 Redis DB Allocation

**Keep track of used Redis DB numbers:**

| Redis DB | Client ID | Company Name | Status |
|----------|-----------|--------------|--------|
| 0 | client_001 | Beauty Salon | Active |
| 1 | client_002 | Massage Parlor | Active |
| 2 | client_003 | Nail Studio | Active |
| 3 | client_004 | - | Available |
| ... | ... | ... | ... |
| 15 | client_016 | - | Available |

**⚠️ WARNING:** If you need more than 16 clients, you must:
1. Deploy another Redis instance (`docker-compose.redis.yml` with different name)
2. Update new clients to use the second Redis

---

## 🔧 Management Commands

### **View All Running Bots**

```bash
docker ps

# Should show:
# - booking-bot-redis-shared (Redis)
# - bot-client-001
# - bot-client-002
# - bot-client-003
# ...
```

### **View Bot Logs**

```bash
# Real-time logs
docker logs bot-client-001 -f

# Last 100 lines
docker logs bot-client-001 --tail 100

# Logs since 1 hour ago
docker logs bot-client-001 --since 1h
```

### **Stop Bot**

```bash
cd clients/client_001
docker-compose stop

# Or directly
docker stop bot-client-001
```

### **Restart Bot**

```bash
cd clients/client_001
docker-compose restart

# Or directly
docker restart bot-client-001
```

### **Remove Bot (Suspend Client)**

```bash
cd clients/client_001
docker-compose down

# Data is preserved in clients/client_001/data/
# To restart: docker-compose up -d
```

### **Completely Delete Client**

```bash
# Stop and remove container
cd clients/client_001
docker-compose down

# Delete all data
cd ../..
rm -rf clients/client_001
```

---

## 🔍 Monitoring

### **Check Redis Usage**

```bash
# Connect to Redis CLI
docker exec -it booking-bot-redis-shared redis-cli

# Inside Redis:
INFO keyspace

# Output:
# db0:keys=5,expires=0   ← Client 1
# db1:keys=3,expires=0   ← Client 2
# db2:keys=7,expires=0   ← Client 3
```

### **Check Memory Usage**

```bash
docker stats

# Shows CPU/RAM usage for each container
```

### **Check Disk Usage**

```bash
du -sh clients/*

# Output:
# 50M  clients/client_001
# 45M  clients/client_002
# 48M  clients/client_003
```

---

## 🚫 Subscription Management

### **Suspend Client (Non-Payment)**

```bash
# Stop bot container
docker stop bot-client-001

# Or
cd clients/client_001
docker-compose stop

# Data is preserved, can be restarted after payment
```

### **Reactivate Client (After Payment)**

```bash
# Restart bot container
docker start bot-client-001

# Or
cd clients/client_001
docker-compose start
```

---

## 🐛 Troubleshooting

### **Problem: "Network bot-network not found"**

```bash
# Solution: Start Redis first (it creates the network)
docker-compose -f docker-compose.redis.yml up -d
```

### **Problem: "Container name already in use"**

```bash
# Check running containers
docker ps -a

# Remove conflicting container
docker rm -f container_name

# Or use unique container name in docker-compose.yml
```

### **Problem: Bot not responding**

```bash
# 1. Check logs
docker logs bot-client-001 --tail 50

# 2. Check if Redis is running
docker ps | grep redis

# 3. Restart bot
docker restart bot-client-001

# 4. Rebuild if code changed
cd clients/client_001
docker-compose up -d --build
```

### **Problem: "Redis DB conflict"**

Two clients using the same REDIS_DB number!

```bash
# Check which DBs are in use
docker exec booking-bot-redis-shared redis-cli INFO keyspace

# Update conflicting client's .env
cd clients/client_002
nano .env  # Change REDIS_DB to unused number
docker-compose restart
```

---

## 📊 Resource Requirements

### **Per Client:**
- **RAM:** ~50-100MB
- **Disk:** ~50MB (code) + ~10-50MB (data/logs)
- **CPU:** <5% average

### **Redis:**
- **RAM:** ~50MB + 5MB per client
- **Disk:** ~10-50MB (persistent data)

### **Server Recommendations:**

| Clients | CPU | RAM | Disk |
|---------|-----|-----|------|
| 1-5 | 2 cores | 2GB | 20GB |
| 5-10 | 2 cores | 4GB | 40GB |
| 10-16 | 4 cores | 8GB | 80GB |

---

## 🔒 Security

### **Redis Password (Optional)**

Add password protection to Redis:

```bash
# Edit docker-compose.redis.yml
command: >
  redis-server
  --requirepass YOUR_STRONG_PASSWORD
  --appendonly yes

# Update all clients' .env
REDIS_PASSWORD=YOUR_STRONG_PASSWORD
```

### **Firewall**

```bash
# Only expose SSH and needed ports
sudo ufw allow 22/tcp
sudo ufw enable

# Redis should NOT be exposed to internet (internal only)
```

---

## 🔄 Updates

### **Update Bot Code**

```bash
# 1. Pull latest changes
git pull origin main

# 2. Update all clients
for client in clients/*/; do
    cd "$client"
    docker-compose down
    
    # Copy new code
    cp -r ../../{handlers,database,services,middlewares,utils,keyboards,main.py,config.py} .
    
    # Rebuild
    docker-compose up -d --build
    cd ../..
done
```

---

## 📞 Support

For issues or questions:
- Check logs: `docker logs bot-client-XXX`
- Review this documentation
- Check [GitHub Issues](https://github.com/balzampsilo-sys/new12_02/issues)

---

## 🎉 Quick Start Checklist

- [ ] Install Docker
- [ ] Clone repository
- [ ] Start shared Redis: `docker-compose -f docker-compose.redis.yml up -d`
- [ ] Deploy first client: `./scripts/deploy_client.sh client_001 "TOKEN" ADMIN_ID 0`
- [ ] Test bot in Telegram
- [ ] Monitor logs: `docker logs bot-client-001 -f`
- [ ] Setup backup cron job (optional)

**Ready to deploy more clients? Use `REDIS_DB` 1, 2, 3... up to 15!**
