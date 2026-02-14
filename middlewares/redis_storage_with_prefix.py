"""
PrefixedRedisStorage - Redis storage with key prefix isolation

Позволяет использовать неограниченное количество клиентов
на одном Redis инстансе через префиксы ключей.

Вместо:
    REDIS_DB=0  # client_001
    REDIS_DB=1  # client_002
    ...
    REDIS_DB=15 # client_016  ❌ Лимит!

Используем:
    REDIS_DB=0
    CLIENT_ID=client_001  # Префикс: client_001:
    CLIENT_ID=client_002  # Префикс: client_002:
    ...
    CLIENT_ID=client_999  # ✅ Неограничено!

Usage:
    from redis.asyncio import Redis
    from middlewares.redis_storage_with_prefix import PrefixedRedisStorage
    
    redis_client = Redis(host='localhost', port=6379, db=0)
    
    storage = PrefixedRedisStorage(
        redis=redis_client,
        key_prefix="client_001:"  # Уникальный префикс
    )
    
    dp = Dispatcher(storage=storage)

Keys in Redis:
    client_001:fsm:state:123456789
    client_001:fsm:data:123456789
    client_002:fsm:state:987654321
    client_002:fsm:data:987654321
"""

from typing import Optional, Dict, Any
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram.fsm.storage.base import StorageKey
from redis.asyncio import Redis


class PrefixedKeyBuilder(DefaultKeyBuilder):
    """
    Key builder с поддержкой префиксов
    """
    
    def __init__(self, prefix: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = prefix
    
    def build(self, key: StorageKey, part: str) -> str:
        """
        Построить ключ с префиксом
        
        Examples:
            Without prefix: fsm:state:123456789:*
            With prefix:    client_001:fsm:state:123456789:*
        """
        base_key = super().build(key, part)
        return f"{self.prefix}{base_key}" if self.prefix else base_key


class PrefixedRedisStorage(RedisStorage):
    """
    Redis Storage с поддержкой key prefix для изоляции клиентов
    
    Args:
        redis: Redis client instance
        key_prefix: Префикс для всех ключей (например: "client_001:")
        state_ttl: TTL для state (в секундах)
        data_ttl: TTL для data (в секундах)
    
    Examples:
        >>> redis = Redis(host='localhost', port=6379, db=0)
        >>> storage = PrefixedRedisStorage(
        ...     redis=redis,
        ...     key_prefix="client_001:"
        ... )
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
    
    async def close(self) -> None:
        """
        Закрыть Redis соединение
        """
        await self.redis.close()
    
    def __repr__(self) -> str:
        return (
            f"PrefixedRedisStorage("
            f"prefix={self.key_prefix!r}, "
            f"state_ttl={self.state_ttl}, "
            f"data_ttl={self.data_ttl}"
            f")"
        )


# Convenience function
def create_prefixed_storage(
    host: str = 'localhost',
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None,
    key_prefix: str = "",
    **kwargs
) -> PrefixedRedisStorage:
    """
    Создать PrefixedRedisStorage с автоматическим подключением
    
    Args:
        host: Redis host
        port: Redis port
        db: Redis database (recommended: 0 for all clients)
        password: Redis password
        key_prefix: Key prefix for isolation
        **kwargs: Additional arguments for PrefixedRedisStorage
    
    Returns:
        PrefixedRedisStorage instance
    
    Examples:
        >>> storage = create_prefixed_storage(
        ...     host='redis-shared',
        ...     port=6379,
        ...     db=0,
        ...     key_prefix="client_001:"
        ... )
    """
    redis_client = Redis(
        host=host,
        port=port,
        db=db,
        password=password,
        decode_responses=True
    )
    
    return PrefixedRedisStorage(
        redis=redis_client,
        key_prefix=key_prefix,
        **kwargs
    )
