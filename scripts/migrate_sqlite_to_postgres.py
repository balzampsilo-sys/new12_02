#!/usr/bin/env python3
"""Скрипт миграции данных из SQLite в PostgreSQL

Usage:
    python scripts/migrate_sqlite_to_postgres.py --client client_001
    python scripts/migrate_sqlite_to_postgres.py --client client_001 --sqlite-path bookings.db
    python scripts/migrate_sqlite_to_postgres.py --all  # миграция всех клиентов

REQUIRES:
    - PostgreSQL server running
    - Target database already created
    - User credentials configured
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import aiosqlite
import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Список таблиц для миграции (в порядке зависимостей)
TABLES_TO_MIGRATE = [
    "users",
    "services",
    "admins",
    "settings",
    "text_templates",
    "blocked_slots",
    "bookings",
    "booking_history",
    "audit_log",
    "broadcast_messages",
    "feedback",
]


class MigrationError(Exception):
    """Ошибка миграции"""
    pass


class SQLiteToPostgresMigration:
    """Миграция данных из SQLite в PostgreSQL"""

    def __init__(
        self,
        sqlite_path: str,
        postgres_url: str,
        batch_size: int = 500,
    ):
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        self.batch_size = batch_size
        self.stats = {
            "total_tables": 0,
            "migrated_tables": 0,
            "total_rows": 0,
            "errors": [],
        }

    async def migrate_table(
        self,
        table_name: str,
        sqlite_conn: aiosqlite.Connection,
        postgres_conn: asyncpg.Connection,
    ) -> int:
        """Миграция одной таблицы

        Args:
            table_name: Имя таблицы
            sqlite_conn: SQLite connection
            postgres_conn: PostgreSQL connection

        Returns:
            Количество мигрированных строк
        """
        logger.info(f"Migrating table: {table_name}")

        try:
            # Проверяем существование таблицы в SQLite
            cursor = await sqlite_conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            table_exists = await cursor.fetchone()

            if not table_exists:
                logger.warning(f"  ⚠️  Table {table_name} not found in SQLite, skipping")
                return 0

            # Читаем все данные
            sqlite_conn.row_factory = aiosqlite.Row
            cursor = await sqlite_conn.execute(f"SELECT * FROM {table_name}")
            rows = await cursor.fetchall()

            if not rows:
                logger.info(f"  ℹ️  Table {table_name} is empty, skipping")
                return 0

            # Получаем имена колонок
            data = [dict(row) for row in rows]
            columns = list(data[0].keys())

            logger.info(f"  Found {len(data)} rows with {len(columns)} columns")

            # Очищаем целевую таблицу (опционально)
            # await postgres_conn.execute(f"TRUNCATE TABLE {table_name} CASCADE")

            # Генерируем INSERT запрос
            placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
            insert_query = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """

            # Вставляем данные батчами
            migrated_count = 0

            for i in range(0, len(data), self.batch_size):
                batch = data[i:i+self.batch_size]

                async with postgres_conn.transaction():
                    try:
                        await postgres_conn.executemany(
                            insert_query,
                            [tuple(row.values()) for row in batch]
                        )
                        migrated_count += len(batch)
                        logger.info(f"  ✅ Migrated {migrated_count}/{len(data)} rows")

                    except asyncpg.UniqueViolationError:
                        # Пропускаем дубликаты
                        logger.warning(f"  ⚠️  Duplicate rows found, skipping batch")
                        continue

            logger.info(f"✅ Table {table_name} migrated: {migrated_count} rows")
            return migrated_count

        except Exception as e:
            error_msg = f"Error migrating table {table_name}: {e}"
            logger.error(f"❌ {error_msg}")
            self.stats["errors"].append(error_msg)
            raise MigrationError(error_msg) from e

    async def run(self) -> Dict[str, Any]:
        """Запуск миграции

        Returns:
            Статистика миграции
        """
        start_time = datetime.now()

        logger.info("="*60)
        logger.info("Starting SQLite to PostgreSQL migration")
        logger.info(f"SQLite: {self.sqlite_path}")
        logger.info(f"PostgreSQL: {self.postgres_url.split('@')[1]}")
        logger.info("="*60)

        # Проверяем существование SQLite файла
        if not Path(self.sqlite_path).exists():
            raise MigrationError(f"SQLite file not found: {self.sqlite_path}")

        # Подключаемся к БД
        sqlite_conn = await aiosqlite.connect(self.sqlite_path)
        postgres_conn = await asyncpg.connect(self.postgres_url)

        try:
            # Мигрируем каждую таблицу
            self.stats["total_tables"] = len(TABLES_TO_MIGRATE)

            for table_name in TABLES_TO_MIGRATE:
                try:
                    rows_migrated = await self.migrate_table(
                        table_name,
                        sqlite_conn,
                        postgres_conn
                    )
                    self.stats["total_rows"] += rows_migrated
                    self.stats["migrated_tables"] += 1

                except MigrationError:
                    # Продолжаем с следующей таблицей
                    continue

            # Сбрасываем последовательности (sequences) для auto-increment
            logger.info("\nResetting PostgreSQL sequences...")
            for table_name in TABLES_TO_MIGRATE:
                try:
                    # Находим primary key column
                    pk_query = f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = '{table_name}'
                        AND column_default LIKE 'nextval%'
                    """
                    pk_column = await postgres_conn.fetchval(pk_query)

                    if pk_column:
                        # Сбрасываем sequence
                        await postgres_conn.execute(f"""
                            SELECT setval(
                                pg_get_serial_sequence('{table_name}', '{pk_column}'),
                                COALESCE(MAX({pk_column}), 1)
                            ) FROM {table_name}
                        """)
                        logger.info(f"  ✅ Reset sequence for {table_name}.{pk_column}")

                except Exception as e:
                    logger.warning(f"  ⚠️  Could not reset sequence for {table_name}: {e}")

        finally:
            await sqlite_conn.close()
            await postgres_conn.close()

        duration = (datetime.now() - start_time).total_seconds()
        self.stats["duration_seconds"] = duration

        # Вывод статистики
        logger.info("\n" + "="*60)
        logger.info("✅ Migration completed!")
        logger.info(f"Tables migrated: {self.stats['migrated_tables']}/{self.stats['total_tables']}")
        logger.info(f"Total rows: {self.stats['total_rows']}")
        logger.info(f"Duration: {duration:.2f} seconds")

        if self.stats["errors"]:
            logger.warning(f"\n⚠️  Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats["errors"]:
                logger.warning(f"  - {error}")

        logger.info("="*60)

        return self.stats


async def migrate_client(
    client_id: str,
    sqlite_path: str = None,
    postgres_password: str = None,
):
    """Миграция одного клиента

    Args:
        client_id: ID клиента (например, 'client_001')
        sqlite_path: Путь к SQLite файлу (автоопределение)
        postgres_password: Пароль PostgreSQL
    """
    # Автоопределение путей
    if not sqlite_path:
        sqlite_path = f"clients/{client_id}/bookings.db"

    # Формирование PostgreSQL URL
    if not postgres_password:
        postgres_password = input(f"Enter PostgreSQL password for {client_id}_user: ")

    postgres_url = (
        f"postgresql://{client_id}_user:{postgres_password}@"
        f"localhost:5432/{client_id}_db"
    )

    # Запуск миграции
    migration = SQLiteToPostgresMigration(sqlite_path, postgres_url)
    stats = await migration.run()

    return stats


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Migrate SQLite data to PostgreSQL"
    )
    parser.add_argument(
        "--client",
        help="Client ID (e.g., client_001)",
    )
    parser.add_argument(
        "--sqlite-path",
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--postgres-url",
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrate all clients (client_001, client_002, client_003)",
    )

    args = parser.parse_args()

    if args.all:
        # Миграция всех клиентов
        for i in range(1, 4):
            client_id = f"client_{i:03d}"
            try:
                asyncio.run(migrate_client(client_id))
            except Exception as e:
                logger.error(f"Failed to migrate {client_id}: {e}")
                continue
    elif args.client:
        # Миграция одного клиента
        asyncio.run(migrate_client(
            args.client,
            sqlite_path=args.sqlite_path,
        ))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
