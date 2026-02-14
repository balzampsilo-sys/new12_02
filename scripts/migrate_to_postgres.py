#!/usr/bin/env python3
"""
Migration script: SQLite → PostgreSQL

Мигрирует данные всех клиентов из SQLite в PostgreSQL.
Каждый клиент получает свою схему (schema) для изоляции данных.

Usage:
    python3 scripts/migrate_to_postgres.py

Environment:
    DATABASE_URL - PostgreSQL connection string
                   Example: postgresql://user:pass@localhost:5432/booking_saas
"""

import asyncio
import os
import sys
from pathlib import Path
import logging

import asyncpg
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# PostgreSQL connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://booking_user:SecurePass2026!@localhost:5432/booking_saas"
)


async def create_schema_tables(conn: asyncpg.Connection, schema: str):
    """
    Создать таблицы в схеме PostgreSQL
    """
    await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    
    # Users table
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Services table
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.services (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            duration_minutes INTEGER NOT NULL,
            price TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Bookings table
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.bookings (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            service_id INTEGER REFERENCES {schema}.services(id),
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT bookings_date_time_unique UNIQUE (date, time)
        )
    """)
    
    # Admins table
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.admins (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            role TEXT DEFAULT 'moderator',
            added_by BIGINT,
            added_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Blocked slots table
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.blocked_slots (
            id SERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT blocked_slots_date_time_unique UNIQUE (date, time)
        )
    """)
    
    # Audit log table
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.audit_log (
            id SERIAL PRIMARY KEY,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            old_data JSONB,
            new_data JSONB,
            performed_by BIGINT NOT NULL,
            performed_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Settings table
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    logger.info(f"✅ Created tables in schema: {schema}")


async def migrate_table(
    sqlite_conn,
    pg_conn: asyncpg.Connection,
    schema: str,
    table_name: str,
    column_mapping: dict
):
    """
    Мигрировать данные из одной таблицы
    
    Args:
        sqlite_conn: SQLite connection
        pg_conn: PostgreSQL connection
        schema: PostgreSQL schema name
        table_name: Table name
        column_mapping: Dict mapping SQLite columns to PostgreSQL columns
    """
    try:
        cursor = await sqlite_conn.execute(f"SELECT * FROM {table_name}")
        rows = await cursor.fetchall()
        
        if not rows:
            logger.info(f"  ⚪ {table_name}: No data")
            return 0
        
        # Get column names from first row
        column_names = [desc[0] for desc in cursor.description]
        
        # Prepare INSERT statement
        pg_columns = [column_mapping.get(col, col) for col in column_names]
        placeholders = ', '.join([f'${i+1}' for i in range(len(pg_columns))])
        
        insert_query = f"""
            INSERT INTO {schema}.{table_name} ({', '.join(pg_columns)})
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING
        """
        
        # Insert rows
        migrated_count = 0
        for row in rows:
            try:
                await pg_conn.execute(insert_query, *row)
                migrated_count += 1
            except Exception as e:
                logger.warning(f"  ⚠️ Error migrating row in {table_name}: {e}")
                continue
        
        logger.info(f"  ✅ {table_name}: {migrated_count} rows")
        return migrated_count
    
    except Exception as e:
        logger.error(f"  ❌ Error migrating {table_name}: {e}")
        return 0


async def migrate_client(
    client_id: str,
    sqlite_path: str,
    pg_conn: asyncpg.Connection
):
    """
    Мигрировать одного клиента
    """
    logger.info(f"\n📦 Migrating {client_id}...")
    
    schema = client_id
    
    # Create schema and tables
    await create_schema_tables(pg_conn, schema)
    
    # Connect to SQLite
    async with aiosqlite.connect(sqlite_path) as sqlite_conn:
        sqlite_conn.row_factory = aiosqlite.Row
        
        # Column mappings (SQLite -> PostgreSQL)
        # Most columns are the same, but we can customize if needed
        default_mapping = {}
        
        # Migrate each table
        stats = {}
        
        tables = [
            'users',
            'services',
            'bookings',
            'admins',
            'blocked_slots',
            'audit_log',
            'settings'
        ]
        
        for table in tables:
            try:
                count = await migrate_table(
                    sqlite_conn,
                    pg_conn,
                    schema,
                    table,
                    default_mapping
                )
                stats[table] = count
            except Exception as e:
                logger.warning(f"  ⚠️ Table {table} not found in SQLite: {e}")
                stats[table] = 0
    
    logger.info(
        f"✅ Migrated {client_id}: "
        f"{stats.get('bookings', 0)} bookings, "
        f"{stats.get('services', 0)} services, "
        f"{stats.get('users', 0)} users"
    )
    
    return stats


async def main():
    """
    Главная функция миграции
    """
    logger.info("🚀 Starting migration: SQLite → PostgreSQL")
    logger.info(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    
    # Connect to PostgreSQL
    try:
        pg_conn = await asyncpg.connect(DATABASE_URL)
        logger.info("✅ Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
        logger.error("Make sure PostgreSQL is running and DATABASE_URL is correct")
        sys.exit(1)
    
    # Find all clients
    clients_dir = Path("clients")
    
    if not clients_dir.exists():
        logger.error(f"❌ Directory not found: {clients_dir}")
        logger.error("Run this script from the project root directory")
        sys.exit(1)
    
    client_dirs = [d for d in clients_dir.iterdir() if d.is_dir()]
    
    if not client_dirs:
        logger.warning("⚠️ No clients found in clients/ directory")
        await pg_conn.close()
        return
    
    logger.info(f"Found {len(client_dirs)} clients")
    
    # Migrate each client
    total_stats = {
        'clients': 0,
        'bookings': 0,
        'services': 0,
        'users': 0
    }
    
    for client_dir in client_dirs:
        client_id = client_dir.name
        sqlite_path = client_dir / "data" / "bookings.db"
        
        if not sqlite_path.exists():
            logger.warning(f"⚠️ SQLite database not found: {sqlite_path}")
            continue
        
        try:
            stats = await migrate_client(client_id, str(sqlite_path), pg_conn)
            
            total_stats['clients'] += 1
            total_stats['bookings'] += stats.get('bookings', 0)
            total_stats['services'] += stats.get('services', 0)
            total_stats['users'] += stats.get('users', 0)
            
        except Exception as e:
            logger.error(f"❌ Error migrating {client_id}: {e}", exc_info=True)
            continue
    
    # Close connection
    await pg_conn.close()
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("🎉 MIGRATION COMPLETED")
    logger.info("="*60)
    logger.info(f"Clients migrated: {total_stats['clients']}")
    logger.info(f"Total bookings: {total_stats['bookings']}")
    logger.info(f"Total services: {total_stats['services']}")
    logger.info(f"Total users: {total_stats['users']}")
    logger.info("="*60)
    
    logger.info("\n👉 Next steps:")
    logger.info("1. Update .env files with PostgreSQL configuration")
    logger.info("2. Add PG_SCHEMA to each client's .env")
    logger.info("3. Restart all client bots")
    logger.info("4. Verify data in PostgreSQL")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)
