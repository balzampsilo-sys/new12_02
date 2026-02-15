#!/usr/bin/env python3
"""
Pool Monitor - Автоматическое пополнение пула ботов

Отслеживает количество свободных ботов и автоматически запускает новые контейнеры
когда свободных остаётся меньше порогового значения.
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime
from typing import Dict, List

from bot_pool_manager import BotPoolManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PoolMonitor:
    """Монитор пула с автоматическим масштабированием"""
    
    def __init__(
        self,
        pool_manager: BotPoolManager,
        min_free_bots: int = 3,  # Минимум свободных ботов
        max_total_bots: int = 100,  # Максимум ботов в системе
        scale_batch: int = 5,  # Сколько ботов добавлять за раз
        check_interval: int = 30  # Проверка каждые 30 секунд
    ):
        self.pool_manager = pool_manager
        self.min_free_bots = min_free_bots
        self.max_total_bots = max_total_bots
        self.scale_batch = scale_batch
        self.check_interval = check_interval
        self.current_pool_size = pool_manager.pool_size
    
    async def start_monitoring(self):
        """Запустить непрерывный мониторинг пула"""
        logger.info("=" * 60)
        logger.info("🔍 POOL MONITOR STARTED")
        logger.info("=" * 60)
        logger.info(f"⚙️  Settings:")
        logger.info(f"   • Min free bots: {self.min_free_bots}")
        logger.info(f"   • Max total bots: {self.max_total_bots}")
        logger.info(f"   • Scale batch: {self.scale_batch}")
        logger.info(f"   • Check interval: {self.check_interval}s")
        logger.info("=" * 60)
        
        while True:
            try:
                await self.check_and_scale()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("⚠️ Monitor stopped")
                break
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)
    
    async def check_and_scale(self):
        """Проверить пул и масштабировать если нужно"""
        
        # Получить статус пула
        status = await self.pool_manager.get_pool_status()
        
        free_bots = status['waiting']
        total_bots = status['total']
        active_bots = status['active']
        
        logger.info(
            f"📊 Pool status: {free_bots} free / {active_bots} active / {total_bots} total"
        )
        
        # Проверить нужно ли масштабирование
        if free_bots < self.min_free_bots and total_bots < self.max_total_bots:
            # Сколько ботов нужно добавить
            bots_to_add = min(
                self.scale_batch,
                self.max_total_bots - total_bots
            )
            
            logger.warning(
                f"⚠️  Low free bots detected: {free_bots} < {self.min_free_bots}"
            )
            logger.info(f"🚀 Scaling up: adding {bots_to_add} bots...")
            
            success = await self.scale_up(bots_to_add)
            
            if success:
                logger.info(f"✅ Successfully added {bots_to_add} bots")
                self.current_pool_size += bots_to_add
                self.pool_manager.pool_size = self.current_pool_size
            else:
                logger.error(f"❌ Failed to add bots")
        
        elif free_bots >= self.min_free_bots:
            logger.debug(f"✅ Pool healthy: {free_bots} free bots available")
    
    async def scale_up(self, count: int) -> bool:
        """Добавить новые контейнеры в пул"""
        
        try:
            # Текущий максимальный ID
            current_max_id = self.current_pool_size
            
            # Создать новые контейнеры
            for i in range(1, count + 1):
                new_id = current_max_id + i
                container_name = f"booking-bot-pool-{new_id}"
                
                logger.info(f"📦 Creating container: {container_name}")
                
                # Запустить контейнер через docker-compose scale
                # Или через docker run
                success = await self._start_new_container(new_id)
                
                if not success:
                    logger.error(f"❌ Failed to start {container_name}")
                    return False
                
                # Инициализировать статус в Redis
                await self._init_bot_status(container_name)
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Scale up failed: {e}", exc_info=True)
            return False
    
    async def _start_new_container(self, pool_id: int) -> bool:
        """Запустить новый контейнер бота"""
        
        container_name = f"booking-bot-pool-{pool_id}"
        
        try:
            # Получить настройки из .env
            postgres_password = os.getenv('POSTGRES_PASSWORD', 'SecurePass2026!')
            
            # Docker run команда
            cmd = [
                'docker', 'run',
                '-d',  # detached mode
                '--name', container_name,
                '--hostname', container_name,
                '--network', 'new12_02_booking-network',  # Сеть из docker-compose
                '--restart', 'unless-stopped',
                '-e', f'BOT_POOL_ID={pool_id}',
                '-e', 'CLIENT_ID=waiting',
                '-e', f'DATABASE_URL=postgresql://booking_user:{postgres_password}@postgres:5432/booking_saas',
                '-e', 'REDIS_HOST=redis',
                '-e', 'REDIS_PORT=6379',
                '-e', 'REDIS_DB=0',
                'new12_02:latest',  # Образ из docker-compose build
                'python', 'main_pool.py'
            ]
            
            # Запустить контейнер
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Container {container_name} started")
                return True
            else:
                logger.error(
                    f"❌ Failed to start {container_name}: {result.stderr}"
                )
                return False
        
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Timeout starting {container_name}")
            return False
        except Exception as e:
            logger.error(f"❌ Error starting {container_name}: {e}")
            return False
    
    async def _init_bot_status(self, container_id: str):
        """Инициализировать статус бота в Redis"""
        await self.pool_manager.connect()
        
        status_key = f"bot_status:{container_id}"
        await self.pool_manager.redis.set(status_key, "waiting")
        
        logger.info(f"✅ Initialized status for {container_id}")


# === ОСНОВНАЯ ФУНКЦИЯ ===
async def main():
    """Запуск монитора пула"""
    
    # Настройки из переменных окружения
    redis_host = os.getenv('REDIS_HOST', 'redis')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_db = int(os.getenv('REDIS_DB', '0'))
    initial_pool_size = int(os.getenv('INITIAL_POOL_SIZE', '10'))
    
    min_free_bots = int(os.getenv('MIN_FREE_BOTS', '3'))
    max_total_bots = int(os.getenv('MAX_TOTAL_BOTS', '100'))
    scale_batch = int(os.getenv('SCALE_BATCH', '5'))
    check_interval = int(os.getenv('CHECK_INTERVAL', '30'))
    
    # Создать менеджер пула
    pool_manager = BotPoolManager(
        redis_host=redis_host,
        redis_port=redis_port,
        redis_db=redis_db,
        pool_size=initial_pool_size
    )
    
    # Создать монитор
    monitor = PoolMonitor(
        pool_manager=pool_manager,
        min_free_bots=min_free_bots,
        max_total_bots=max_total_bots,
        scale_batch=scale_batch,
        check_interval=check_interval
    )
    
    # Запустить мониторинг
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("👋 Pool monitor stopped by user")
    except Exception as e:
        logger.error(f"❌ Pool monitor crashed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
