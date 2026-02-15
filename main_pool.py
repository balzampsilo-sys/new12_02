#!/usr/bin/env python3
"""Booking Bot - Pool Mode

Два режима работы:
1. WAITING - ожидает конфигурацию от Sales Bot через Redis
2. ACTIVE - работает как бот клиента с токеном и админом
"""

import os
import sys
import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import redis.asyncio as aioredis
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Загрузка переменных окружения
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = os.getenv("BOT_TOKEN", None)
ADMIN_IDS = os.getenv("ADMIN_IDS", "")
CLIENT_ID = os.getenv("CLIENT_ID", "waiting")
BOT_POOL_ID = os.getenv("BOT_POOL_ID", "unknown")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

DATABASE_URL = os.getenv("DATABASE_URL")
PG_SCHEMA = os.getenv("PG_SCHEMA", None)

CONTAINER_ID = os.getenv("HOSTNAME", f"bot-pool-{BOT_POOL_ID}")

redis_client: Optional[aioredis.Redis] = None
bot_instance: Optional[Bot] = None
dp: Optional[Dispatcher] = None


async def connect_to_redis() -> aioredis.Redis:
    """Подключение к Redis"""
    try:
        client = await aioredis.from_url(
            f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
            encoding="utf-8",
            decode_responses=True
        )
        await client.ping()
        logger.info(f"✅ Redis connected: {REDIS_HOST}:{REDIS_PORT}")
        return client
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise


async def wait_for_configuration():
    """Режим ожидания конфигурации от Sales Bot"""
    global redis_client, BOT_TOKEN, ADMIN_IDS, CLIENT_ID, PG_SCHEMA
    
    logger.info("=" * 60)
    logger.info("🕐 BOT CONTAINER STARTED IN WAITING MODE")
    logger.info("=" * 60)
    logger.info(f"📦 Container ID: {CONTAINER_ID}")
    logger.info(f"🔑 Config key: bot_config:{CONTAINER_ID}")
    logger.info(f"📡 Listening on Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
    logger.info("=" * 60)
    
    redis_client = await connect_to_redis()
    
    config_key = f"bot_config:{CONTAINER_ID}"
    
    # Убедиться что контейнер свободен
    await redis_client.delete(config_key)
    await redis_client.set(f"bot_status:{CONTAINER_ID}", "waiting")
    
    logger.info("⏳ Waiting for configuration from Sales Bot...")
    
    check_count = 0
    
    while True:
        try:
            config_json = await redis_client.get(config_key)
            
            if config_json:
                logger.info("📥 Configuration received!")
                
                config = json.loads(config_json)
                
                BOT_TOKEN = config['bot_token']
                ADMIN_IDS = str(config['admin_telegram_id'])
                CLIENT_ID = config['client_id']
                PG_SCHEMA = CLIENT_ID
                
                logger.info("=" * 60)
                logger.info("✅ BOT ACTIVATED!")
                logger.info("=" * 60)
                logger.info(f"🏢 Client ID: {CLIENT_ID}")
                logger.info(f"👤 Admin ID: {ADMIN_IDS}")
                logger.info(f"🤖 Token: {BOT_TOKEN[:20]}...")
                logger.info(f"📂 Schema: {PG_SCHEMA}")
                logger.info("=" * 60)
                
                os.environ['BOT_TOKEN'] = BOT_TOKEN
                os.environ['ADMIN_IDS'] = ADMIN_IDS
                os.environ['CLIENT_ID'] = CLIENT_ID
                os.environ['PG_SCHEMA'] = PG_SCHEMA
                
                await redis_client.delete(config_key)
                
                await redis_client.set(
                    f"bot_status:{CONTAINER_ID}",
                    json.dumps({
                        "status": "active",
                        "client_id": CLIENT_ID,
                        "activated_at": datetime.now().isoformat()
                    })
                )
                
                await start_active_bot()
                break
            
            check_count += 1
            if check_count % 10 == 0:
                logger.info(f"💤 Still waiting... ({check_count * 5} seconds)")
            
            await asyncio.sleep(5)
        
        except asyncio.CancelledError:
            logger.info("⚠️ Waiting cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Error in waiting loop: {e}", exc_info=True)
            await asyncio.sleep(5)


async def start_active_bot():
    """Запуск бота в активном режиме"""
    global bot_instance, dp
    
    if not BOT_TOKEN:
        logger.error("❌ Cannot start bot: BOT_TOKEN not set")
        return
    
    try:
        # Импортируем модуль с полной логикой бота
        from main import start_bot as original_start_bot
        
        logger.info("🚀 Starting bot with full logic...")
        await original_start_bot()
    
    except Exception as e:
        logger.error(f"❌ Error starting active bot: {e}", exc_info=True)
        raise


def is_bot_configured() -> bool:
    """Проверить, настроен ли бот"""
    return BOT_TOKEN is not None and BOT_TOKEN != ""


async def main():
    """Точка входа"""
    try:
        if is_bot_configured():
            logger.info("🟢 Starting in ACTIVE mode")
            await start_active_bot()
        else:
            logger.info("🟡 Starting in WAITING mode")
            await wait_for_configuration()
    
    except KeyboardInterrupt:
        logger.info("⚠️ Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    finally:
        if redis_client:
            await redis_client.close()
        
        logger.info("👋 Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
