#!/usr/bin/env python3
"""
Deploy Worker - Обработчик очереди деплоя

Запускается на ХОСТЕ (не в Docker) и:
- Читает задачи из Redis/PostgreSQL
- Выполняет деплой клиентских ботов
- Обновляет статус задач
- Отправляет уведомления

Запуск:
    python3 automation/deploy_worker.py
    
Или через systemd:
    sudo systemctl start deploy-worker
"""

import os
import sys
import json
import time
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

# Добавить пути
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "automation"))

from deploy_manager import DeploymentManager
from subscription_manager import SubscriptionManager

# Redis для очереди задач
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Redis not installed. Install: pip install redis")

# Telegram для уведомлений
try:
    from aiogram import Bot
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ Aiogram not installed. Install: pip install aiogram")

from dotenv import load_dotenv
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / "logs" / "deploy_worker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "master_bot:")
DEPLOY_QUEUE_KEY = f"{REDIS_KEY_PREFIX}deploy_queue"
DEPLOY_RESULTS_KEY = f"{REDIS_KEY_PREFIX}deploy_results"

MASTER_BOT_TOKEN = os.getenv("MASTER_BOT_TOKEN")
DB_PATH = str(project_root / "subscriptions.db")

# Создать директорию для логов
(project_root / "logs").mkdir(exist_ok=True)


class DeployWorker:
    """Worker для обработки задач деплоя"""
    
    def __init__(self):
        self.deploy_manager = DeploymentManager(
            project_root=project_root,
            subscription_db=DB_PATH
        )
        self.sub_manager = SubscriptionManager(DB_PATH)
        
        # Redis клиент
        if REDIS_AVAILABLE:
            try:
                self.redis = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    decode_responses=True
                )
                # Проверка соединения
                self.redis.ping()
                logger.info(f"✅ Connected to Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
            except Exception as e:
                logger.error(f"❌ Redis connection failed: {e}")
                self.redis = None
        else:
            self.redis = None
        
        # Telegram бот для уведомлений
        if TELEGRAM_AVAILABLE and MASTER_BOT_TOKEN:
            self.bot = Bot(token=MASTER_BOT_TOKEN)
        else:
            self.bot = None
    
    async def send_notification(self, chat_id: int, message: str):
        """Отправить уведомление в Telegram"""
        if not self.bot:
            logger.warning("Telegram bot not available for notifications")
            return
        
        try:
            await self.bot.send_message(chat_id, message, parse_mode="Markdown")
            logger.info(f"✅ Notification sent to {chat_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send notification: {e}")
    
    def process_task(self, task_data: dict) -> dict:
        """
        Обработать задачу деплоя
        
        Args:
            task_data: Словарь с данными задачи
        
        Returns:
            dict с результатом выполнения
        """
        task_id = task_data.get('task_id', 'unknown')
        logger.info(f"📦 Processing task: {task_id}")
        logger.info(f"📋 Task data: {json.dumps(task_data, indent=2)}")
        
        try:
            # Извлечь данные
            bot_token = task_data['bot_token']
            admin_telegram_id = task_data['admin_telegram_id']
            company_name = task_data.get('company_name', 'Новый клиент')
            bot_username = task_data.get('bot_username')
            subscription_days = task_data.get('subscription_days', 30)
            
            # Выполнить деплой
            logger.info(f"🚀 Deploying bot for: {company_name}")
            result = self.deploy_manager.deploy_client(
                bot_token=bot_token,
                admin_telegram_id=admin_telegram_id,
                company_name=company_name,
                bot_username=bot_username,
                subscription_days=subscription_days
            )
            
            if result['success']:
                logger.info(f"✅ Deploy successful: {result['client_id']}")
                
                # Подготовить результат
                deploy_result = {
                    'task_id': task_id,
                    'status': 'completed',
                    'success': True,
                    'client_id': result['client_id'],
                    'redis_db': result['redis_db'],
                    'container_name': result['container_name'],
                    'client_dir': result['client_dir'],
                    'company_name': company_name,
                    'admin_telegram_id': admin_telegram_id,
                    'completed_at': datetime.now().isoformat()
                }
                
                return deploy_result
            else:
                logger.error(f"❌ Deploy failed: {result.get('error')}")
                return {
                    'task_id': task_id,
                    'status': 'failed',
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'company_name': company_name,
                    'admin_telegram_id': admin_telegram_id,
                    'completed_at': datetime.now().isoformat()
                }
        
        except Exception as e:
            logger.error(f"❌ Task processing error: {e}", exc_info=True)
            return {
                'task_id': task_id,
                'status': 'failed',
                'success': False,
                'error': str(e),
                'company_name': task_data.get('company_name', 'Unknown'),
                'admin_telegram_id': task_data.get('admin_telegram_id'),
                'completed_at': datetime.now().isoformat()
            }
    
    async def send_result_notification(self, result: dict):
        """Отправить уведомление о результате деплоя"""
        admin_id = result.get('admin_telegram_id')
        if not admin_id:
            return
        
        if result['success']:
            message = f"""
✅ **БОТ УСПЕШНО РАЗВЕРНУТ!**

🏢 Компания: **{result['company_name']}**
🆔 Client ID: `{result['client_id']}`
💾 Redis DB: **{result['redis_db']}**
🐳 Container: `{result['container_name']}`

✅ Бот работает 24/7
✅ Вы можете начать использовать

📱 Найдите вашего бота в Telegram и нажмите /start
            """
        else:
            message = f"""
❌ **ОШИБКА ДЕПЛОЯ**

🏢 Компания: **{result['company_name']}**
❌ Причина: {result.get('error', 'Unknown')}

Обратитесь в техподдержку.
            """
        
        await self.send_notification(admin_id, message)
    
    def save_result(self, result: dict):
        """Сохранить результат в Redis"""
        if not self.redis:
            return
        
        try:
            task_id = result['task_id']
            # Сохранить результат с TTL 24 часа
            self.redis.setex(
                f"{DEPLOY_RESULTS_KEY}:{task_id}",
                86400,  # 24 hours
                json.dumps(result)
            )
            logger.info(f"💾 Result saved for task: {task_id}")
        except Exception as e:
            logger.error(f"❌ Failed to save result: {e}")
    
    async def run(self):
        """Основной цикл worker'а"""
        logger.info("🚀 Deploy Worker started")
        logger.info(f"📂 Project root: {project_root}")
        logger.info(f"💾 Database: {DB_PATH}")
        logger.info(f"🔄 Queue key: {DEPLOY_QUEUE_KEY}")
        
        if not self.redis:
            logger.error("❌ Redis not available. Worker cannot start.")
            logger.info("Install Redis: pip install redis")
            logger.info("Or start Redis server: docker-compose up -d redis")
            return
        
        logger.info("")
        logger.info("="*60)
        logger.info("✅ WORKER READY - Waiting for deploy tasks...")
        logger.info("="*60)
        logger.info("")
        
        while True:
            try:
                # BRPOP - блокирующее чтение из очереди (ждёт до 5 секунд)
                task = self.redis.brpop(DEPLOY_QUEUE_KEY, timeout=5)
                
                if task:
                    queue_name, task_json = task
                    logger.info(f"📥 New task received from {queue_name}")
                    
                    try:
                        task_data = json.loads(task_json)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Invalid task JSON: {e}")
                        continue
                    
                    # Обработать задачу
                    result = self.process_task(task_data)
                    
                    # Сохранить результат
                    self.save_result(result)
                    
                    # Отправить уведомление
                    await self.send_result_notification(result)
                    
                    logger.info("")
                    logger.info("✅ Task completed. Waiting for next task...")
                    logger.info("")
                else:
                    # Таймаут - задач нет
                    pass
            
            except KeyboardInterrupt:
                logger.info("\n⚠️ Shutting down worker...")
                break
            
            except Exception as e:
                logger.error(f"❌ Worker error: {e}", exc_info=True)
                time.sleep(5)  # Пауза при ошибке
        
        logger.info("👋 Deploy Worker stopped")
        
        # Закрыть соединения
        if self.bot:
            await self.bot.session.close()


async def main():
    """Точка входа"""
    worker = DeployWorker()
    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Stopped by user")
