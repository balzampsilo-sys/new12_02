"""Тесты для проверки PostgreSQL миграции

Запуск:
    pytest tests/test_postgresql_migration.py -v
    pytest tests/test_postgresql_migration.py -v --cov=database
"""

import asyncio
import os
from datetime import datetime

import pytest
import pytest_asyncio

# Set test environment
os.environ["DB_TYPE"] = "postgresql"
os.environ["DATABASE_URL"] = "postgresql://test_user:test_pass@localhost:5432/test_db"

from database.db_adapter import db_adapter


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    """Setup database before tests"""
    try:
        await db_adapter.init_pool()
        yield
    finally:
        await db_adapter.close_pool()


@pytest.mark.asyncio
async def test_connection_pool(setup_db):
    """Тест connection pool"""
    result = await db_adapter.fetchval("SELECT 1")
    assert result == 1, "Connection pool should work"


@pytest.mark.asyncio
async def test_placeholder_syntax(setup_db):
    """Тест корректности PostgreSQL placeholders ($1, $2)"""
    # Создаем временную таблицу
    await db_adapter.execute("""
        CREATE TEMP TABLE test_placeholders (
            id SERIAL PRIMARY KEY,
            name TEXT,
            value INTEGER
        )
    """)

    # Вставляем данные с $1, $2
    await db_adapter.execute(
        "INSERT INTO test_placeholders (name, value) VALUES ($1, $2)",
        "test_name",
        42
    )

    # Проверяем
    row = await db_adapter.fetchrow(
        "SELECT * FROM test_placeholders WHERE name = $1",
        "test_name"
    )

    assert row is not None
    assert row["name"] == "test_name"
    assert row["value"] == 42


@pytest.mark.asyncio
async def test_transaction_commit(setup_db):
    """Тест коммита транзакции"""
    await db_adapter.execute("""
        CREATE TEMP TABLE test_transaction (
            id SERIAL PRIMARY KEY,
            data TEXT
        )
    """)

    # Транзакция
    async with db_adapter.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO test_transaction (data) VALUES ($1)",
                "committed_data"
            )

    # Проверяем что данные сохранились
    result = await db_adapter.fetchval(
        "SELECT data FROM test_transaction WHERE data = $1",
        "committed_data"
    )

    assert result == "committed_data", "Transaction should be committed"


@pytest.mark.asyncio
async def test_transaction_rollback(setup_db):
    """Тест отката транзакции при ошибке"""
    await db_adapter.execute("""
        CREATE TEMP TABLE test_rollback (
            id SERIAL PRIMARY KEY,
            data TEXT UNIQUE
        )
    """)

    try:
        async with db_adapter.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO test_rollback (data) VALUES ($1)",
                    "test_data"
                )
                # Намеренно вызываем ошибку
                raise Exception("Intentional error")

    except Exception:
        pass

    # Проверяем, что данные не сохранились (rollback сработал)
    result = await db_adapter.fetchval(
        "SELECT COUNT(*) FROM test_rollback WHERE data = $1",
        "test_data"
    )

    assert result == 0, "Transaction should be rolled back"


@pytest.mark.asyncio
async def test_concurrent_inserts(setup_db):
    """Тест конкурентных вставок (преимущество PostgreSQL перед SQLite)"""
    await db_adapter.execute("""
        CREATE TEMP TABLE test_concurrent (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Запускаем 10 конкурентных вставок
    async def insert_row(user_id: int):
        await db_adapter.execute(
            "INSERT INTO test_concurrent (user_id) VALUES ($1)",
            user_id
        )

    tasks = [insert_row(i) for i in range(10)]
    await asyncio.gather(*tasks)

    # Проверяем, что все 10 записей вставлены
    count = await db_adapter.fetchval(
        "SELECT COUNT(*) FROM test_concurrent"
    )

    assert count == 10, "All concurrent inserts should succeed"


@pytest.mark.asyncio
async def test_connection_pool_limits(setup_db):
    """Тест лимитов connection pool"""
    # Запускаем больше запросов, чем max_size (20)
    async def query():
        return await db_adapter.fetchval("SELECT pg_sleep(0.1), 1")

    tasks = [query() for _ in range(30)]  # > max_size

    # Не должно быть ошибок, pool должен ожидать
    results = await asyncio.gather(*tasks)
    assert all(r == 1 for r in results), "All queries should complete successfully"


@pytest.mark.asyncio
async def test_batch_insert(setup_db):
    """Тест батчовой вставки"""
    await db_adapter.execute("""
        CREATE TEMP TABLE test_batch (
            id SERIAL PRIMARY KEY,
            value INTEGER
        )
    """)

    # Вставляем 1000 записей
    async with db_adapter.acquire() as conn:
        await conn.conn.executemany(
            "INSERT INTO test_batch (value) VALUES ($1)",
            [(i,) for i in range(1000)]
        )

    count = await db_adapter.fetchval("SELECT COUNT(*) FROM test_batch")
    assert count == 1000, "Batch insert should insert all rows"


@pytest.mark.asyncio
async def test_fetch_methods(setup_db):
    """Тест различных методов fetch"""
    await db_adapter.execute("""
        CREATE TEMP TABLE test_fetch (
            id SERIAL PRIMARY KEY,
            name TEXT,
            value INTEGER
        )
    """)

    # Вставляем тестовые данные
    for i in range(5):
        await db_adapter.execute(
            "INSERT INTO test_fetch (name, value) VALUES ($1, $2)",
            f"name_{i}",
            i * 10
        )

    # Тест fetch (all rows)
    all_rows = await db_adapter.fetch("SELECT * FROM test_fetch ORDER BY id")
    assert len(all_rows) == 5
    assert all_rows[0]["name"] == "name_0"

    # Тест fetchrow (single row)
    row = await db_adapter.fetchrow(
        "SELECT * FROM test_fetch WHERE name = $1",
        "name_2"
    )
    assert row["value"] == 20

    # Тест fetchval (single value)
    count = await db_adapter.fetchval("SELECT COUNT(*) FROM test_fetch")
    assert count == 5

    max_value = await db_adapter.fetchval(
        "SELECT MAX(value) FROM test_fetch"
    )
    assert max_value == 40


@pytest.mark.asyncio
async def test_null_handling(setup_db):
    """Тест обработки NULL значений"""
    await db_adapter.execute("""
        CREATE TEMP TABLE test_null (
            id SERIAL PRIMARY KEY,
            nullable_field TEXT
        )
    """)

    # Вставляем NULL
    await db_adapter.execute(
        "INSERT INTO test_null (nullable_field) VALUES ($1)",
        None
    )

    # Проверяем
    row = await db_adapter.fetchrow("SELECT * FROM test_null WHERE id = 1")
    assert row["nullable_field"] is None


@pytest.mark.asyncio
async def test_timestamp_handling(setup_db):
    """Тест работы с TIMESTAMP"""
    await db_adapter.execute("""
        CREATE TEMP TABLE test_timestamp (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db_adapter.execute("INSERT INTO test_timestamp DEFAULT VALUES")

    row = await db_adapter.fetchrow("SELECT * FROM test_timestamp WHERE id = 1")
    assert row["created_at"] is not None
    assert isinstance(row["created_at"], datetime)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
