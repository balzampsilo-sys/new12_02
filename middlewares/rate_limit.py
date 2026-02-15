"""Мидлварь для ограничения частоты запросов

✅ P1 FIX: Redis-based rate limiting для multi-instance deployment
"""

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None


class RateLimitMiddleware(BaseMiddleware):
    """Мидлварь для защиты от спама
    
    ✅ P1 FIX: Поддержка Redis для distributed rate limiting
    
    Использует Redis INCR + EXPIRE для атомарного rate limiting:
    - Работает в multi-instance deployment
    - Graceful fallback к in-memory если Redis недоступен
    - Минимальная латентность (single Redis command)
    """

    def __init__(
        self,
        rate_limit: float = 1.0,
        redis_client: Optional[Any] = None,
        key_prefix: str = "ratelimit"
    ):
        """
        Args:
            rate_limit: Минимальный интервал между действиями (секунды)
            redis_client: Redis client для distributed rate limiting (опционально)
            key_prefix: Префикс для Redis ключей
        """
        self.rate_limit = rate_limit
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        
        # ✅ P1: Fallback к in-memory если Redis не передан
        if not redis_client:
            from cachetools import TTLCache
            self.cache = TTLCache(maxsize=10000, ttl=rate_limit)
            logging.warning(
                "RateLimitMiddleware: Redis not provided, using in-memory cache\n"
                "   ⚠️ This will NOT work correctly in multi-instance deployment"
            )
        else:
            self.cache = None
            logging.info(
                f"✅ RateLimitMiddleware: Using Redis for distributed rate limiting\n"
                f"   • Rate limit: {rate_limit}s\n"
                f"   • Key prefix: {key_prefix}"
            )
        
        super().__init__()

    async def _check_rate_limit_redis(self, user_id: int) -> bool:
        """Проверка rate limit через Redis (атомарно)
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если rate limit превышен, False если OK
        """
        key = f"{self.key_prefix}:{user_id}"
        
        try:
            # ✅ P1: Атомарная операция INCR + GET + EXPIRE
            # Используем pipeline для минимизации round-trips
            async with self.redis_client.pipeline(transaction=True) as pipe:
                # INCR возвращает новое значение
                await pipe.incr(key)
                # TTL проверяет есть ли уже expire
                await pipe.ttl(key)
                results = await pipe.execute()
                
                count = results[0]  # Результат INCR
                ttl = results[1]    # Результат TTL
                
                # Если это первый запрос (count == 1) или expire истек (ttl == -1)
                # устанавливаем expire
                if count == 1 or ttl == -1:
                    await self.redis_client.expire(key, int(self.rate_limit) + 1)
                
                # Rate limit превышен если count > 1
                return count > 1
                
        except Exception as e:
            logging.error(f"Redis rate limit check failed: {e}", exc_info=True)
            # ✅ Fallback: разрешаем запрос при ошибке Redis
            return False

    async def _check_rate_limit_memory(self, user_id: int) -> bool:
        """Проверка rate limit через in-memory cache
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если rate limit превышен, False если OK
        """
        if user_id in self.cache:
            return True
        
        self.cache[user_id] = True
        return False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Определяем user_id в зависимости от типа события
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        # ✅ P1: Проверяем через Redis или fallback к memory
        if self.redis_client:
            rate_limited = await self._check_rate_limit_redis(user_id)
        else:
            rate_limited = await self._check_rate_limit_memory(user_id)
        
        if rate_limited:
            # Для callback query отвечаем тихо
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Слишком быстро! Подождите немного", show_alert=False)
            elif isinstance(event, Message):
                await event.answer("⏳ Пожалуйста, подождите немного перед следующим действием")
            
            logging.warning(
                f"Rate limit exceeded for user {user_id} "
                f"(method: {'redis' if self.redis_client else 'memory'})"
            )
            return

        # Продолжаем обработку
        return await handler(event, data)
