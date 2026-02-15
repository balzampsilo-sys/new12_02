#!/usr/bin/env python3
"""
Bot Pool Manager
Управление пулом готовых контейнеров
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class BotPoolManager:
    """Менеджер пула ботов"""
    
    def __init__(
        self,
        redis_host: str = "redis",
        redis_port: int = 6379,
        redis_db: int = 0,
        pool_size: int = 10
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.pool_size = pool_size
        self.redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Подключиться к Redis"""
        if not self.redis:
            self.redis = await aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}",
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("✅ BotPoolManager connected to Redis")
    
    async def close(self):
        """Закрыть соединение"""
        if self.redis:
            await self.redis.close()
    
    async def find_free_bot(self) -> Optional[Dict[str, str]]:
        """Найти свободный контейнер"""
        await self.connect()
        
        for i in range(1, self.pool_size + 1):
            container_id = f"booking-bot-pool-{i}"
            status_key = f"bot_status:{container_id}"
            
            status_json = await self.redis.get(status_key)
            
            if not status_json:
                continue
            
            try:
                status = json.loads(status_json)
                if status.get("status") == "waiting":
                    logger.info(f"✅ Found free bot: {container_id}")
                    return {
                        "container_id": container_id,
                        "pool_id": str(i)
                    }
            except json.JSONDecodeError:
                if status_json == "waiting":
                    return {
                        "container_id": container_id,
                        "pool_id": str(i)
                    }
        
        logger.warning("⚠️ No free bots available")
        return None
    
    async def activate_bot(
        self,
        container_id: str,
        bot_token: str,
        admin_telegram_id: int,
        client_id: str,
        company_name: str
    ) -> bool:
        """Активировать контейнер"""
        await self.connect()
        
        config_key = f"bot_config:{container_id}"
        
        existing_config = await self.redis.get(config_key)
        if existing_config:
            logger.error(f"❌ Container {container_id} already configured!")
            return False
        
        config = {
            "bot_token": bot_token,
            "admin_telegram_id": admin_telegram_id,
            "client_id": client_id,
            "company_name": company_name,
            "activated_at": datetime.now().isoformat()
        }
        
        await self.redis.set(config_key, json.dumps(config), ex=300)
        
        logger.info(f"✅ Configuration sent to {container_id}")
        return True
    
    async def get_pool_status(self) -> Dict:
        """Получить статус пула"""
        await self.connect()
        
        status = {
            "total": self.pool_size,
            "waiting": 0,
            "active": 0,
            "unknown": 0,
            "bots": []
        }
        
        for i in range(1, self.pool_size + 1):
            container_id = f"booking-bot-pool-{i}"
            status_key = f"bot_status:{container_id}"
            
            status_json = await self.redis.get(status_key)
            
            bot_info = {
                "pool_id": i,
                "container_id": container_id,
                "status": "unknown",
                "client_id": None,
                "activated_at": None
            }
            
            if status_json:
                try:
                    status_data = json.loads(status_json)
                    bot_info["status"] = status_data.get("status", "unknown")
                    bot_info["client_id"] = status_data.get("client_id")
                    bot_info["activated_at"] = status_data.get("activated_at")
                except json.JSONDecodeError:
                    bot_info["status"] = status_json
            
            if bot_info["status"] == "waiting":
                status["waiting"] += 1
            elif bot_info["status"] == "active":
                status["active"] += 1
            else:
                status["unknown"] += 1
            
            status["bots"].append(bot_info)
        
        return status
