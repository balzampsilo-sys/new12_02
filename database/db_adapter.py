"""Адаптер базы данных для PostgreSQL

Предоставляет unified interface для работы с PostgreSQL.
✅ FIXED: Удалена поддержка SQLite (legacy)
✅ FIXED: Только PostgreSQL с multi-tenant изоляцией

Examples:
    >>> # Инициализация
    >>> await db_adapter.init_pool()
    
    >>> # Простые запросы
    >>> row = await db_adapter.fetchrow(
    ...     "SELECT * FROM bookings WHERE id = $1",
    ...     booking_id
    ... )
    
    >>> # Транзакции
    >>> async with db_adapter.acquire() as conn:
    ...     async with conn.transaction():
    ...         await conn.execute("UPDATE ...")
    ...         await conn.execute("INSERT ...")
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class DatabaseAdapter:
    """PostgreSQL database adapter with connection pooling
    
    ✅ FIXED: PostgreSQL-only (SQLite legacy removed)
    ✅ FIXED: Multi-tenant isolation via search_path
    """

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.schema = None
        self._initialized = False

    async def init_pool(self) -> None:
        """Инициализация connection pool
        
        ✅ FIXED: PostgreSQL-only, SQLite removed
        """
        if self._initialized:
            logger.warning("DatabaseAdapter already initialized")
            return

        # Import здесь чтобы избежать circular imports
        from config import (
            DATABASE_URL,
            DB_COMMAND_TIMEOUT,
            DB_POOL_MAX_SIZE,
            DB_POOL_MIN_SIZE,
            DB_POOL_TIMEOUT,
            PG_SCHEMA,
        )

        self.schema = PG_SCHEMA

        try:
            self.pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=DB_POOL_MIN_SIZE,
                max_size=DB_POOL_MAX_SIZE,
                timeout=DB_POOL_TIMEOUT,
                command_timeout=DB_COMMAND_TIMEOUT,
                # ✅ CRITICAL: Multi-tenant isolation
                server_settings={
                    "search_path": PG_SCHEMA,
                    "application_name": "booking_bot",
                    "jit": "off",
                },
            )
            logger.info(
                f"✅ PostgreSQL pool created: "
                f"{DB_POOL_MIN_SIZE}-{DB_POOL_MAX_SIZE} connections\n"
                f"   • Schema: {PG_SCHEMA} (search_path set)"
            )
            self._initialized = True
        except Exception as e:
            logger.critical(f"❌ Failed to create PostgreSQL pool: {e}")
            raise

    async def close_pool(self) -> None:
        """Закрытие connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL pool closed")
            self._initialized = False

    @asynccontextmanager
    async def acquire(self):
        """Получение connection из pool

        Yields:
            PostgreSQLConnection wrapper
        """
        if not self._initialized:
            raise RuntimeError("DatabaseAdapter not initialized. Call init_pool() first.")

        async with self.pool.acquire() as conn:
            yield PostgreSQLConnection(conn, self.schema)

    async def execute(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> str:
        """Выполнение INSERT/UPDATE/DELETE с возвратом status

        Args:
            query: SQL запрос
            *args: Параметры запроса
            timeout: Таймаут выполнения

        Returns:
            Status string (например, "INSERT 0 1")
        """
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)

    async def fetch(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Выполнение SELECT с возвратом всех строк

        Args:
            query: SQL запрос
            *args: Параметры запроса
            timeout: Таймаут выполнения

        Returns:
            Список словарей с данными
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)

    async def fetchrow(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Выполнение SELECT с возвратом одной строки

        Args:
            query: SQL запрос
            *args: Параметры запроса
            timeout: Таймаут выполнения

        Returns:
            Словарь с данными или None
        """
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)

    async def fetchval(
        self, query: str, *args, column: int = 0, timeout: Optional[float] = None
    ) -> Any:
        """Выполнение SELECT с возвратом одного значения

        Args:
            query: SQL запрос
            *args: Параметры запроса
            column: Индекс колонки (0-based)
            timeout: Таймаут выполнения

        Returns:
            Значение или None
        """
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, column=column, timeout=timeout)


class PostgreSQLConnection:
    """Wrapper для asyncpg connection
    
    ✅ FIXED: Schema-aware connection
    """

    def __init__(self, conn: asyncpg.Connection, schema: str):
        self.conn = conn
        self.schema = schema

    async def execute(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> str:
        return await self.conn.execute(query, *args, timeout=timeout)

    async def fetch(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> List[Dict]:
        rows = await self.conn.fetch(query, *args, timeout=timeout)
        return [dict(row) for row in rows]

    async def fetchrow(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> Optional[Dict]:
        row = await self.conn.fetchrow(query, *args, timeout=timeout)
        return dict(row) if row else None

    async def fetchval(
        self, query: str, *args, column: int = 0, timeout: Optional[float] = None
    ) -> Any:
        return await self.conn.fetchval(query, *args, column=column, timeout=timeout)

    def transaction(self):
        """Начать транзакцию

        Returns:
            Transaction context manager
        """
        return self.conn.transaction()


# Global instance
db_adapter = DatabaseAdapter()
