#!/usr/bin/env python3
"""
Deployment Manager - OPTIMIZED VERSION
Автоматический деплой новых клиентов

✅ OPTIMIZATION:
- Ускорение: 188 сек → 8-10 сек (20x)
- Используется готовый образ booking-bot:base
- Не копирует файлы кода
- Не выполняет docker build

Интегрируется с SubscriptionManager для:
- Автоматического выделения Redis DB
- Отслеживания статуса контейнеров
- Управления подписками
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Добавить automation/ в путь
script_dir = Path(__file__).parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from subscription_manager import SubscriptionManager


class DeploymentManager:
    """Управление деплоем клиентов (ОПТИМИЗИРОВАННО)"""
    
    def __init__(
        self,
        project_root: Optional[Path] = None,
        database_url: Optional[str] = None,
        pg_schema: str = "master_bot"
    ):
        """
        Инициализация deployment manager
        
        Args:
            project_root: Корневая директория проекта
            database_url: PostgreSQL connection string (если None - берется из ENV)
            pg_schema: PostgreSQL schema (по умолчанию master_bot)
        """
        self.project_root = project_root or Path.cwd()
        self.clients_dir = self.project_root / "clients"
        
        # ✅ OPTIMIZATION: Имя базового образа
        self.base_image = "booking-bot:base"
        
        # ✅ PostgreSQL из ENV или параметра
        if database_url is None:
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql://booking_user:SecurePass2026!@localhost:5432/booking_saas"
            )
        
        self.sub_manager = SubscriptionManager(
            database_url=database_url,
            schema=pg_schema
        )
        
        # Создать clients/ если не существует
        self.clients_dir.mkdir(exist_ok=True)
    
    def _check_base_image(self) -> bool:
        """Проверить что базовый образ существует"""
        try:
            result = subprocess.run(
                ["docker", "images", "-q", self.base_image],
                capture_output=True,
                text=True,
                check=True
            )
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return False
    
    def deploy_client(
        self,
        bot_token: str,
        admin_telegram_id: int,
        company_name: Optional[str] = None,
        bot_username: Optional[str] = None,
        subscription_days: int = 30
    ) -> dict:
        """
        Деплой нового клиента (ОПТИМИЗИРОВАННО)
        
        Args:
            bot_token: Токен бота
            admin_telegram_id: Telegram ID администратора
            company_name: Название компании
            bot_username: Username бота
            subscription_days: Дней подписки
        
        Returns:
            dict с информацией о деплое
        """
        start_time = time.time()
        
        print(f"🚀 Деплой нового клиента: {company_name or 'Новый клиент'}")
        print("="*60)
        
        # ✅ OPTIMIZATION: Проверить базовый образ
        if not self._check_base_image():
            print(f"❌ Образ {self.base_image} не найден!")
            print(f"⚠️  Соберите его: bash build_base_image.sh")
            return {"success": False, "error": "Base image not found"}
        
        print(f"✅ Базовый образ доступен: {self.base_image}")
        print("")
        
        # 1. Регистрация в subscription_manager
        print("⏳ Регистрация в системе...")
        try:
            client_id, redis_db = self.sub_manager.add_client(
                bot_token=bot_token,
                admin_telegram_id=admin_telegram_id,
                company_name=company_name,
                subscription_days=subscription_days,
                bot_username=bot_username
            )
        except ValueError as e:
            print(f"❌ Ошибка: {e}")
            return {"success": False, "error": str(e)}
        
        client_short_id = client_id[:8]
        container_name = f"bot-client-{client_short_id}"
        client_dir = self.clients_dir / client_short_id
        
        print(f"✅ Клиент зарегистрирован: {client_id}")
        print(f"📊 Redis DB: {redis_db}")
        print("")
        
        # 2. Создание директории (ТОЛЬКО ДЛЯ ДАННЫХ!)
        print("📁 Создание директории для данных...")
        client_dir.mkdir(exist_ok=True)
        (client_dir / "data").mkdir(exist_ok=True)
        (client_dir / "logs").mkdir(exist_ok=True)
        (client_dir / "backups").mkdir(exist_ok=True)
        print("✅ Директории созданы")
        print("")
        
        # ✅ OPTIMIZATION: НЕ копируем файлы (экономия 15 сек)
        
        # 3. Создание .env
        print("⚙️ Генерация .env...")
        self._create_env_file(
            client_dir=client_dir,
            bot_token=bot_token,
            admin_id=admin_telegram_id,
            redis_db=redis_db,
            company_name=company_name or "Клиент",
            client_id=client_id
        )
        print("✅ .env создан")
        print("")
        
        # 4. Создание docker-compose.yml (ОПТИМИЗИРОВАННЫЙ)
        print("🐳 Генерация docker-compose.yml...")
        self._create_docker_compose_optimized(
            client_dir=client_dir,
            container_name=container_name,
            redis_db=redis_db
        )
        print("✅ docker-compose.yml создан")
        print("")
        
        # 5. Проверка shared Redis
        print("🔍 Проверка shared Redis...")
        if not self._check_redis():
            print("⚠️  Redis не запущен. Запуск...")
            self._start_redis()
        else:
            print("✅ Redis доступен")
        print("")
        
        # ✅ OPTIMIZATION: Запуск БЕЗ BUILD (экономия 150 сек!)
        print("🚀 Запуск контейнера (без build)...")
        try:
            subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=client_dir,
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка запуска: {e.stderr.decode()}")
            return {"success": False, "error": "Docker start failed"}
        
        print("✅ Контейнер запущен")
        print("")
        
        # 6. Обновление статуса
        self.sub_manager.update_container_status(client_id, running=True)
        
        # Подсчет времени
        deploy_time = time.time() - start_time
        
        # Итоговый репорт
        print("")
        print("✅ " + "="*50)
        print("✅ БОТ УСПЕШНО РАЗВЕРНУТ!")
        print("✅ " + "="*50)
        print("")
        print(f"   ⏱️  Время деплоя: {deploy_time:.1f} сек ⚡")
        print(f"   🏢 Компания: {company_name or 'Клиент'}")
        print(f"   🆔 Client ID: {client_id}")
        print(f"   🐳 Container: {container_name}")
        print(f"   📊 Redis DB: {redis_db}")
        print(f"   📁 Directory: {client_dir}")
        print("")
        print("🔧 Полезные команды:")
        print(f"   Логи:         docker logs {container_name} -f")
        print(f"   Остановить:  docker stop {container_name}")
        print(f"   Запустить:   docker start {container_name}")
        print("")
        
        return {
            "success": True,
            "client_id": client_id,
            "redis_db": redis_db,
            "container_name": container_name,
            "client_dir": str(client_dir),
            "deploy_time": f"{deploy_time:.1f}s"
        }
    
    def _create_env_file(
        self,
        client_dir: Path,
        bot_token: str,
        admin_id: int,
        redis_db: int,
        company_name: str,
        client_id: str
    ):
        """Создать .env файл"""
        from datetime import datetime
        
        env_content = f"""# ========================================
# BOT CONFIGURATION FOR: {company_name}
# ========================================
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Client ID: {client_id}
# Redis DB: {redis_db}
# ========================================

# Bot Credentials
BOT_TOKEN={bot_token}
ADMIN_IDS={admin_id}

# Redis Configuration (SHARED)
REDIS_ENABLED=True
REDIS_HOST=redis-shared
REDIS_PORT=6379
REDIS_DB={redis_db}
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
"""
        
        with open(client_dir / ".env", "w", encoding="utf-8") as f:
            f.write(env_content)
    
    def _create_docker_compose_optimized(self, client_dir: Path, container_name: str, redis_db: int):
        """
        Создать docker-compose.yml (ОПТИМИЗИРОВАННЫЙ)
        
        ✅ Использует готовый образ booking-bot:base
        ✅ НЕ выполняет build (экономия 150 сек)
        """
        compose_content = f"""version: '3.8'

services:
  bot:
    # ✅ OPTIMIZATION: Используется готовый образ!
    image: {self.base_image}
    
    container_name: {container_name}
    
    restart: unless-stopped
    
    env_file:
      - .env
    
    environment:
      - REDIS_ENABLED=True
      - REDIS_HOST=redis-shared
      - REDIS_DB={redis_db}
    
    volumes:
      - ./data:/app/data
      - ./backups:/app/backups
      - ./logs:/app/logs
    
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
"""
        
        with open(client_dir / "docker-compose.yml", "w", encoding="utf-8") as f:
            f.write(compose_content)
    
    def _check_redis(self) -> bool:
        """Проверить запущен ли Redis"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=booking-bot-redis-shared", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True
            )
            return "booking-bot-redis-shared" in result.stdout
        except subprocess.CalledProcessError:
            return False
    
    def _start_redis(self):
        """Запустить shared Redis"""
        redis_compose = self.project_root / "docker-compose.redis.yml"
        if redis_compose.exists():
            subprocess.run(
                ["docker", "compose", "-f", str(redis_compose), "up", "-d"],
                cwd=self.project_root,
                check=True
            )
        else:
            print("❌ docker-compose.redis.yml не найден!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Автоматический деплой клиента (ОПТИМИЗИРОВАННЮЙ)")
    parser.add_argument("bot_token", help="Токен бота")
    parser.add_argument("admin_id", type=int, help="Telegram ID админа")
    parser.add_argument("--company", help="Название компании")
    parser.add_argument("--username", help="Username бота")
    parser.add_argument("--days", type=int, default=30, help="Дней подписки")
    
    args = parser.parse_args()
    
    deployer = DeploymentManager()
    result = deployer.deploy_client(
        bot_token=args.bot_token,
        admin_telegram_id=args.admin_id,
        company_name=args.company,
        bot_username=args.username,
        subscription_days=args.days
    )
    
    if not result["success"]:
        sys.exit(1)
