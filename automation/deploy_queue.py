#!/usr/bin/env python3
"""
Deploy Queue Helper
Управление очередью задач деплоя через Redis

Используется в Master Bot для добавления задач
и проверки результатов.
"""

import os
import json
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class DeployQueue:
    """Менеджер очереди задач деплоя"""
    
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        key_prefix: str = "master_bot:"
    ):
        """
        Инициализация
        
        Args:
            redis_host: Redis хост
            redis_port: Redis порт
            redis_db: Redis database number
            key_prefix: Префикс для ключей
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.key_prefix = key_prefix
        
        self.queue_key = f"{key_prefix}deploy_queue"
        self.results_key = f"{key_prefix}deploy_results"
        
        if REDIS_AVAILABLE:
            try:
                self.redis = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True
                )
                # Проверка соединения
                self.redis.ping()
                logger.info(f"✅ Deploy Queue connected to Redis: {redis_host}:{redis_port}/{redis_db}")
            except Exception as e:
                logger.error(f"❌ Redis connection failed: {e}")
                self.redis = None
        else:
            logger.warning("⚠️ Redis not available. Queue functionality disabled.")
            self.redis = None
    
    def is_available(self) -> bool:
        """Проверить доступность Redis"""
        return self.redis is not None
    
    def add_deploy_task(
        self,
        bot_token: str,
        admin_telegram_id: int,
        company_name: Optional[str] = None,
        bot_username: Optional[str] = None,
        subscription_days: int = 30,
        created_by: Optional[int] = None
    ) -> Optional[str]:
        """
        Добавить задачу деплоя в очередь
        
        Args:
            bot_token: Токен бота
            admin_telegram_id: Telegram ID администратора
            company_name: Название компании
            bot_username: Username бота
            subscription_days: Количество дней подписки
            created_by: Telegram ID создателя задачи
        
        Returns:
            Task ID или None при ошибке
        """
        if not self.redis:
            logger.error("❌ Cannot add task: Redis not available")
            return None
        
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "bot_token": bot_token,
            "admin_telegram_id": admin_telegram_id,
            "company_name": company_name,
            "bot_username": bot_username,
            "subscription_days": subscription_days,
            "created_by": created_by,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        
        try:
            # Добавить в очередь (LPUSH - добавляет в начало)
            self.redis.lpush(self.queue_key, json.dumps(task_data))
            logger.info(f"✅ Task added to queue: {task_id} for {company_name}")
            return task_id
        except Exception as e:
            logger.error(f"❌ Failed to add task: {e}")
            return None
    
    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить результат выполнения задачи
        
        Args:
            task_id: ID задачи
        
        Returns:
            Словарь с результатом или None
        """
        if not self.redis:
            return None
        
        try:
            result_key = f"{self.results_key}:{task_id}"
            result_json = self.redis.get(result_key)
            
            if result_json:
                return json.loads(result_json)
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get result: {e}")
            return None
    
    def get_queue_length(self) -> int:
        """Получить количество задач в очереди"""
        if not self.redis:
            return 0
        
        try:
            return self.redis.llen(self.queue_key)
        except Exception as e:
            logger.error(f"❌ Failed to get queue length: {e}")
            return 0


if __name__ == "__main__":
    # Тест
    import sys
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    from dotenv import load_dotenv
    load_dotenv()
    
    logging.basicConfig(level=logging.INFO)
    
    # Создать очередь
    queue = DeployQueue(
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_db=int(os.getenv("REDIS_DB", "0"))
    )
    
    if queue.is_available():
        print("✅ Deploy Queue is ready")
        print(f"📋 Tasks in queue: {queue.get_queue_length()}")
    else:
        print("❌ Deploy Queue not available")
