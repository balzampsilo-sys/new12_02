"""Database adapter для поддержки PostgreSQL и SQLite

Предоставляет unified interface для работы с разными типами БД.
Автоматически определяет тип БД из конфигурации.

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
    """Unified interface для работы с PostgreSQL и SQLite"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.db_type = None
        self._initialized = False

    async def init_pool(self) -> None:
        """Инициализация connection pool

        Reads config from imported module to avoid circular imports.
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
            DB_TYPE,
        )

        self.db_type = DB_TYPE

        if self.db_type == "postgresql":
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=DATABASE_URL,
                    min_size=DB_POOL_MIN_SIZE,
                    max_size=DB_POOL_MAX_SIZE,
                    timeout=DB_POOL_TIMEOUT,
                    command_timeout=DB_COMMAND_TIMEOUT,
                    # Production-ready опции
                    server_settings={
                        "application_name": "booking_bot",
                        "jit": "off",  # Отключить JIT для предсказуемости
                    },
                )
                logger.info(
                    f"✅ PostgreSQL pool created: "
                    f"{DB_POOL_MIN_SIZE}-{DB_POOL_MAX_SIZE} connections"
                )
                self._initialized = True
            except Exception as e:
                logger.critical(f"❌ Failed to create PostgreSQL pool: {e}")
                raise
        else:
            logger.info("SQLite mode - using direct connections (legacy)")
            self._initialized = True

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
            Connection wrapper (PostgreSQLConnection or SQLiteConnection)
        """
        if not self._initialized:
            raise RuntimeError("DatabaseAdapter not initialized. Call init_pool() first.")

        if self.db_type == "postgresql":
            async with self.pool.acquire() as conn:
                yield PostgreSQLConnection(conn)
        else:
            # Legacy SQLite fallback
            import aiosqlite
            from config import DATABASE_PATH

            async with aiosqlite.connect(DATABASE_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                yield SQLiteConnection(conn)

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
    """Wrapper для asyncpg connection"""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

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


class SQLiteConnection:
    """Wrapper для aiosqlite connection (legacy)"""

    def __init__(self, conn):
        self.conn = conn

    async def execute(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> str:
        # SQLite использует ? вместо $1, $2
        # Конвертируем параметры
        sqlite_query = self._convert_placeholders(query)
        cursor = await self.conn.execute(sqlite_query, args)
        await self.conn.commit()
        return f"Rows affected: {cursor.rowcount}"

    async def fetch(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> List[Dict]:
        sqlite_query = self._convert_placeholders(query)
        cursor = await self.conn.execute(sqlite_query, args)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def fetchrow(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> Optional[Dict]:
        sqlite_query = self._convert_placeholders(query)
        cursor = await self.conn.execute(sqlite_query, args)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetchval(
        self, query: str, *args, column: int = 0, timeout: Optional[float] = None
    ) -> Any:
        row = await self.fetchrow(query, *args)
        return list(row.values())[column] if row else None

    @asynccontextmanager
    async def transaction(self):
        """Эмуляция транзакции для SQLite"""
        try:
            yield
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    @staticmethod
    def _convert_placeholders(query: str) -> str:
        """Конвертирует PostgreSQL placeholders ($1, $2) в SQLite (?)

        Args:
            query: SQL запрос с $1, $2, ...

        Returns:
            SQL запрос с ?
        """
        import re

        # Заменяем $1, $2, ... на ?
        converted = re.sub(r"\$\d+", "?", query)
        return converted


# Global instance
db_adapter = DatabaseAdapter()
