"""
Redis Storage с поддержкой key prefix для изоляции клиентов

Позволяет использовать неограниченное количество клиентов на одном Redis,
изолируя данные через префиксы ключей вместо разных DB.

Пример:
    client_001:fsm:state:123456789
    client_002:fsm:state:987654321
    
Преимущества:
    - Неограниченное количество клиентов (вместо 16)
    - Лучшая производительность
    - Меньше памяти
    - Рекомендуется Redis
"""

import logging
from typing import Any, Dict, Optional

from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class PrefixedKeyBuilder(DefaultKeyBuilder):
    """
    Key builder с поддержкой префикса для изоляции клиентов
    """
    
    def __init__(self, prefix: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = prefix
        logger.info(f"PrefixedKeyBuilder initialized with prefix: '{prefix}'")
    
    def build(self, key: str, part: str) -> str:
        """
        Построить ключ с префиксом
        
        Args:
            key: Базовый ключ (fsm, data, etc)
            part: Часть ключа (chat_id, user_id, etc)
        
        Returns:
            Полный ключ с префиксом
            
        Example:
            >>> builder = PrefixedKeyBuilder(prefix="client_001:")
            >>> builder.build("fsm", "state:123456789")
            'client_001:fsm:state:123456789'
        """
        base_key = super().build(key, part)
        
        if self.prefix:
            prefixed_key = f"{self.prefix}{base_key}"
            return prefixed_key
        
        return base_key


class PrefixedRedisStorage(RedisStorage):
    """
    Redis Storage с поддержкой key prefix для изоляции клиентов
    
    Использует PrefixedKeyBuilder для автоматического добавления
    префикса ко всем ключам, обеспечивая полную изоляцию данных
    между клиентами.
    
    Example:
        >>> from redis.asyncio import Redis
        >>> 
        >>> redis = Redis(host="localhost", port=6379, db=0)
        >>> storage = PrefixedRedisStorage(
        ...     redis=redis,
        ...     key_prefix="client_001:"
        ... )
        >>> 
        >>> dp = Dispatcher(storage=storage)
    """
    
    def __init__(
        self,
        redis: Redis,
        key_prefix: str = "",
        state_ttl: Optional[int] = None,
        data_ttl: Optional[int] = None,
        **kwargs
    ):
        """
        Args:
            redis: Redis connection
            key_prefix: Префикс для всех ключей (например "client_001:")
            state_ttl: TTL для состояний FSM (секунды)
            data_ttl: TTL для данных FSM (секунды)
        """
        # Создать key builder с префиксом
        key_builder = PrefixedKeyBuilder(
            prefix=key_prefix,
            with_bot_id=kwargs.pop('with_bot_id', False),
            with_destiny=kwargs.pop('with_destiny', False)
        )
        
        super().__init__(
            redis=redis,
            key_builder=key_builder,
            state_ttl=state_ttl,
            data_ttl=data_ttl,
            **kwargs
        )
        
        self.key_prefix = key_prefix
        logger.info(
            f"✅ PrefixedRedisStorage initialized:\n"
            f"   • Prefix: '{key_prefix}'\n"
            f"   • State TTL: {state_ttl}s\n"
            f"   • Data TTL: {data_ttl}s\n"
            f"   • Redis: {redis.connection_pool.connection_kwargs.get('host')}:"
            f"{redis.connection_pool.connection_kwargs.get('port')}"
        )
    
    async def close(self):
        """Закрыть Redis connection"""
        await self.redis.close()
        logger.info(f"Redis storage closed for prefix: '{self.key_prefix}'")


async def create_redis_storage(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None,
    key_prefix: str = "",
    state_ttl: Optional[int] = None,
    data_ttl: Optional[int] = None
) -> PrefixedRedisStorage:
    """
    Фабрика для создания Redis storage с префиксом
    
    Args:
        host: Redis host
        port: Redis port
        db: Redis database (рекомендуется 0 для всех клиентов)
        password: Redis password
        key_prefix: Префикс для изоляции клиента
        state_ttl: TTL для состояний (None = без TTL)
        data_ttl: TTL для данных (None = без TTL)
    
    Returns:
        Настроенный PrefixedRedisStorage
        
    Example:
        >>> storage = await create_redis_storage(
        ...     host="redis-shared",
        ...     port=6379,
        ...     key_prefix="client_001:"
        ... )
    """
    redis = Redis(
        host=host,
        port=port,
        db=db,
        password=password,
        decode_responses=True
    )
    
    storage = PrefixedRedisStorage(
        redis=redis,
        key_prefix=key_prefix,
        state_ttl=state_ttl,
        data_ttl=data_ttl
    )
    
    return storage
