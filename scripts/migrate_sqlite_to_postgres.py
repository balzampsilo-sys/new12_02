#!/usr/bin/env python3
"""Миграция данных из SQLite в PostgreSQL

Использование:
    python scripts/migrate_sqlite_to_postgres.py \\
        --sqlite bookings.db \\
        --postgres "postgresql://user:pass@localhost/booking_db"

Или с переменными окружения:
    export DATABASE_PATH=bookings.db
    export DATABASE_URL="postgresql://user:pass@localhost/booking_db"
    python scripts/migrate_sqlite_to_postgres.py
"""

import argparse
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List

import aiosqlite
import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Порядок миграции важен из-за foreign keys
TABLE_ORDER = [
    "users",
    "services",
    "admins",
    "bookings",
    "blocked_slots",
    "analytics",
    "feedback",
    "audit_log",
    "booking_history",
    "admin_sessions",
    "settings",
    "calendar_settings",
    "slot_intervals",
    "text_templates",
]


async def get_table_columns(sqlite_conn: aiosqlite.Connection, table_name: str) -> List[str]:
    """Получить список колонок таблицы
    
    Args:
        sqlite_conn: SQLite connection
        table_name: Имя таблицы
    
    Returns:
        Список имен колонок
    """
    cursor = await sqlite_conn.execute(f"PRAGMA table_info({table_name})")
    rows = await cursor.fetchall()
    return [row[1] for row in rows]


async def migrate_table(
    sqlite_path: str,
    postgres_url: str,
    table_name: str,
    batch_size: int = 500,
    skip_on_conflict: bool = True
) -> tuple[int, int]:
    """Миграция одной таблицы
    
    Args:
        sqlite_path: Путь к SQLite файлу
        postgres_url: URL PostgreSQL
        table_name: Имя таблицы
        batch_size: Размер батча
        skip_on_conflict: Пропускать конфликты
    
    Returns:
        Tuple[migrated_count, total_count]
    """
    logger.info(f"🔄 Migrating table: {table_name}")
    
    # Читаем из SQLite
    async with aiosqlite.connect(sqlite_path) as sqlite_conn:
        sqlite_conn.row_factory = aiosqlite.Row
        
        # Проверяем существование таблицы
        cursor = await sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        table_exists = await cursor.fetchone()
        
        if not table_exists:
            logger.warning(f"⚠️  Table {table_name} doesn't exist in SQLite - skipping")
            return 0, 0
        
        # Читаем все данные
        cursor = await sqlite_conn.execute(f"SELECT * FROM {table_name}")
        rows = await cursor.fetchall()
        data = [dict(row) for row in rows]
    
    total_count = len(data)
    
    if total_count == 0:
        logger.info(f"ℹ️  Table {table_name} is empty - nothing to migrate")
        return 0, 0
    
    # Записываем в PostgreSQL батчами
    postgres_conn = await asyncpg.connect(postgres_url)
    
    try:
        columns = list(data[0].keys())
        placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
        
        # ON CONFLICT для безопасности
        conflict_clause = "ON CONFLICT DO NOTHING" if skip_on_conflict else ""
        
        insert_query = f"""
            INSERT INTO {table_name} ({', '.join(columns)})
            VALUES ({placeholders})
            {conflict_clause}
        """
        
        migrated_count = 0
        
        for i in range(0, total_count, batch_size):
            batch = data[i:i+batch_size]
            
            async with postgres_conn.transaction():
                for row in batch:
                    try:
                        await postgres_conn.execute(
                            insert_query,
                            *[row[col] for col in columns]
                        )
                        migrated_count += 1
                    except Exception as e:
                        if not skip_on_conflict:
                            logger.error(f"❌ Error inserting row: {e}")
                            raise
            
            progress = min(i + batch_size, total_count)
            logger.info(f"  ➜ {progress}/{total_count} rows processed...")
        
        logger.info(f"✅ Table {table_name} migrated: {migrated_count}/{total_count} rows")
        
        # Сброс sequences для SERIAL колонок
        if "id" in columns:
            try:
                max_id_query = f"SELECT MAX(id) FROM {table_name}"
                max_id = await postgres_conn.fetchval(max_id_query)
                
                if max_id is not None:
                    sequence_name = f"{table_name}_id_seq"
                    await postgres_conn.execute(
                        f"SELECT setval('{sequence_name}', $1)",
                        max_id
                    )
                    logger.info(f"  ➜ Sequence {sequence_name} set to {max_id}")
            except Exception as e:
                logger.warning(f"  ⚠️  Failed to reset sequence: {e}")
        
        return migrated_count, total_count
        
    finally:
        await postgres_conn.close()


async def verify_migration(
    sqlite_path: str,
    postgres_url: str,
    table_name: str
) -> bool:
    """Проверка миграции
    
    Args:
        sqlite_path: Путь к SQLite файлу
        postgres_url: URL PostgreSQL
        table_name: Имя таблицы
    
    Returns:
        True если количество строк совпадает
    """
    async with aiosqlite.connect(sqlite_path) as sqlite_conn:
        cursor = await sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        if not await cursor.fetchone():
            return True  # Таблица не существует в SQLite
        
        cursor = await sqlite_conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        sqlite_count = (await cursor.fetchone())[0]
    
    postgres_conn = await asyncpg.connect(postgres_url)
    try:
        postgres_count = await postgres_conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
    finally:
        await postgres_conn.close()
    
    match = sqlite_count == postgres_count
    
    if match:
        logger.info(f"✅ Verification passed for {table_name}: {sqlite_count} rows")
    else:
        logger.error(
            f"❌ Verification FAILED for {table_name}: "
            f"SQLite={sqlite_count}, PostgreSQL={postgres_count}"
        )
    
    return match


async def main(
    sqlite_path: str,
    postgres_url: str,
    verify: bool = True,
    batch_size: int = 500
):
    """Главная функция миграции
    
    Args:
        sqlite_path: Путь к SQLite файлу
        postgres_url: URL PostgreSQL
        verify: Проверять миграцию
        batch_size: Размер батча
    """
    logger.info("="*80)
    logger.info("🚀 Starting SQLite to PostgreSQL migration")
    logger.info("="*80)
    logger.info(f"Source (SQLite): {sqlite_path}")
    logger.info(f"Target (PostgreSQL): {postgres_url.split('@')[1] if '@' in postgres_url else postgres_url}")
    logger.info(f"Batch size: {batch_size}")
    logger.info("="*80)
    
    if not os.path.exists(sqlite_path):
        logger.error(f"❌ SQLite database not found: {sqlite_path}")
        sys.exit(1)
    
    total_migrated = 0
    total_rows = 0
    failed_tables = []
    
    for table_name in TABLE_ORDER:
        try:
            migrated, total = await migrate_table(
                sqlite_path,
                postgres_url,
                table_name,
                batch_size
            )
            total_migrated += migrated
            total_rows += total
        except Exception as e:
            logger.error(f"❌ Failed to migrate table {table_name}: {e}", exc_info=True)
            failed_tables.append(table_name)
    
    logger.info("="*80)
    logger.info("🎉 Migration completed!")
    logger.info("="*80)
    logger.info(f"Total rows migrated: {total_migrated}/{total_rows}")
    
    if failed_tables:
        logger.warning(f"⚠️  Failed tables: {', '.join(failed_tables)}")
    
    # Проверка
    if verify:
        logger.info("\n" + "="*80)
        logger.info("🔍 Verifying migration...")
        logger.info("="*80)
        
        verification_passed = True
        for table_name in TABLE_ORDER:
            if table_name not in failed_tables:
                if not await verify_migration(sqlite_path, postgres_url, table_name):
                    verification_passed = False
        
        if verification_passed:
            logger.info("\n✅ ✅ ✅ All tables verified successfully! ✅ ✅ ✅")
        else:
            logger.error("\n❌ ❌ ❌ Verification FAILED - check logs above ❌ ❌ ❌")
            sys.exit(1)
    
    logger.info("\n" + "="*80)
    logger.info("🚀 Migration complete! You can now switch to PostgreSQL.")
    logger.info("="*80)
    logger.info("\nNext steps:")
    logger.info("  1. Set DB_TYPE=postgresql in your .env")
    logger.info("  2. Set DATABASE_URL to your PostgreSQL connection string")
    logger.info("  3. Restart the bot")
    logger.info("="*80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate data from SQLite to PostgreSQL"
    )
    parser.add_argument(
        "--sqlite",
        default=os.getenv("DATABASE_PATH", "bookings.db"),
        help="Path to SQLite database file"
    )
    parser.add_argument(
        "--postgres",
        default=os.getenv(
            "DATABASE_URL",
            "postgresql://booking_user:password@localhost:5432/booking_db"
        ),
        help="PostgreSQL connection URL"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for inserts (default: 500)"
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip verification after migration"
    )
    
    args = parser.parse_args()
    
    asyncio.run(main(
        sqlite_path=args.sqlite,
        postgres_url=args.postgres,
        verify=not args.no_verify,
        batch_size=args.batch_size
    ))
