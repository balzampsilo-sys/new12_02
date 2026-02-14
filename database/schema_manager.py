"""Менеджер схем PostgreSQL для multi-tenant архитектуры

✅ NEW: Автоматическое создание schema и таблиц для каждого клиента

Examples:
    >>> from database.schema_manager import SchemaManager
    >>> 
    >>> # Инициализация схемы для клиента
    >>> await SchemaManager.init_schema("client_001")
    >>> # ✅ Schema client_001 создана
    >>> # ✅ Все таблицы созданы в client_001
"""

import logging
from typing import List

from database.db_adapter import db_adapter

logger = logging.getLogger(__name__)


class SchemaManager:
    """
    Менеджер схем PostgreSQL
    
    Отвечает за:
    - Создание schema для клиента
    - Создание всех таблиц
    - Создание индексов
    """

    @staticmethod
    async def init_schema(schema_name: str) -> None:
        """
        Инициализация schema с таблицами и индексами
        
        Args:
            schema_name: Имя schema (например, "client_001")
        """
        logger.info(f"📦 Initializing schema: {schema_name}")
        
        # 1. Создать schema
        await SchemaManager._create_schema(schema_name)
        
        # 2. Создать таблицы
        await SchemaManager._create_tables(schema_name)
        
        # 3. Создать индексы
        await SchemaManager._create_indexes(schema_name)
        
        logger.info(f"✅ Schema {schema_name} initialized successfully")

    @staticmethod
    async def _create_schema(schema_name: str) -> None:
        """Создать schema если не существует"""
        await db_adapter.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        logger.info(f"  ✅ Schema created: {schema_name}")

    @staticmethod
    async def _create_tables(schema_name: str) -> None:
        """Создать все таблицы в schema"""
        tables = [
            # Users
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                first_seen TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )""",
            
            # Services
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.services (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER NOT NULL DEFAULT 60,
                price TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )""",
            
            # Bookings
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.bookings (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                service_id INTEGER REFERENCES {schema_name}.services(id),
                duration_minutes INTEGER DEFAULT 60,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT bookings_date_time_unique UNIQUE (date, time)
            )""",
            
            # Admins
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.admins (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                role TEXT DEFAULT 'moderator',
                added_by BIGINT,
                added_at TIMESTAMP DEFAULT NOW()
            )""",
            
            # Blocked slots
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.blocked_slots (
                id SERIAL PRIMARY KEY,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                reason TEXT,
                blocked_by BIGINT NOT NULL,
                blocked_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT blocked_slots_date_time_unique UNIQUE (date, time)
            )""",
            
            # Analytics
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.analytics (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                event TEXT NOT NULL,
                data TEXT,
                timestamp TIMESTAMP DEFAULT NOW()
            )""",
            
            # Feedback
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.feedback (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                booking_id INTEGER,
                rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                comment TEXT,
                timestamp TIMESTAMP DEFAULT NOW()
            )""",
            
            # Admin sessions
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.admin_sessions (
                user_id BIGINT PRIMARY KEY,
                message_id INTEGER,
                updated_at TIMESTAMP DEFAULT NOW()
            )""",
            
            # Audit log
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.audit_log (
                id SERIAL PRIMARY KEY,
                admin_id BIGINT NOT NULL,
                action TEXT NOT NULL,
                target_id TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT NOW()
            )""",
            
            # Booking history
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.booking_history (
                id SERIAL PRIMARY KEY,
                booking_id INTEGER NOT NULL,
                changed_by BIGINT NOT NULL,
                changed_by_type TEXT NOT NULL,
                action TEXT NOT NULL,
                old_date TEXT,
                old_time TEXT,
                new_date TEXT,
                new_time TEXT,
                old_service_id INTEGER,
                new_service_id INTEGER,
                reason TEXT,
                changed_at TIMESTAMP DEFAULT NOW()
            )""",
            
            # Settings
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            )""",
            
            # Text templates (i18n)
            f"""CREATE TABLE IF NOT EXISTS {schema_name}.text_templates (
                id SERIAL PRIMARY KEY,
                key TEXT NOT NULL UNIQUE,
                text TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            )""",
        ]
        
        for table_sql in tables:
            await db_adapter.execute(table_sql)
        
        logger.info(f"  ✅ Created {len(tables)} tables")

    @staticmethod
    async def _create_indexes(schema_name: str) -> None:
        """Создать индексы для производительности"""
        indexes = [
            # Bookings indexes
            f"CREATE INDEX IF NOT EXISTS idx_bookings_date ON {schema_name}.bookings(date, time)",
            f"CREATE INDEX IF NOT EXISTS idx_bookings_user ON {schema_name}.bookings(user_id)",
            f"CREATE INDEX IF NOT EXISTS idx_bookings_service ON {schema_name}.bookings(service_id)",
            f"CREATE INDEX IF NOT EXISTS idx_bookings_status ON {schema_name}.bookings(status)",
            f"CREATE INDEX IF NOT EXISTS idx_bookings_created ON {schema_name}.bookings(created_at)",
            
            # Analytics indexes
            f"CREATE INDEX IF NOT EXISTS idx_analytics_user ON {schema_name}.analytics(user_id, event)",
            f"CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON {schema_name}.analytics(timestamp)",
            
            # Blocked slots indexes
            f"CREATE INDEX IF NOT EXISTS idx_blocked_date ON {schema_name}.blocked_slots(date, time)",
            
            # Feedback indexes
            f"CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON {schema_name}.feedback(timestamp)",
            f"CREATE INDEX IF NOT EXISTS idx_feedback_user ON {schema_name}.feedback(user_id)",
            
            # Admins indexes
            f"CREATE INDEX IF NOT EXISTS idx_admins_added ON {schema_name}.admins(added_at)",
            
            # Audit log indexes
            f"CREATE INDEX IF NOT EXISTS idx_audit_admin ON {schema_name}.audit_log(admin_id)",
            f"CREATE INDEX IF NOT EXISTS idx_audit_action ON {schema_name}.audit_log(action)",
            f"CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON {schema_name}.audit_log(timestamp)",
            
            # Booking history indexes
            f"CREATE INDEX IF NOT EXISTS idx_booking_history_booking ON {schema_name}.booking_history(booking_id)",
            f"CREATE INDEX IF NOT EXISTS idx_booking_history_changed_by ON {schema_name}.booking_history(changed_by)",
            f"CREATE INDEX IF NOT EXISTS idx_booking_history_timestamp ON {schema_name}.booking_history(changed_at)",
        ]
        
        for index_sql in indexes:
            await db_adapter.execute(index_sql)
        
        logger.info(f"  ✅ Created {len(indexes)} indexes")

    @staticmethod
    async def schema_exists(schema_name: str) -> bool:
        """
        Проверить существование schema
        
        Args:
            schema_name: Имя schema
            
        Returns:
            True если schema существует
        """
        result = await db_adapter.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata 
                WHERE schema_name = $1
            )
            """,
            schema_name
        )
        return result

    @staticmethod
    async def list_schemas() -> List[str]:
        """
        Получить список всех client schemas
        
        Returns:
            Список имен schemas
        """
        rows = await db_adapter.fetch(
            """
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name LIKE 'client_%'
            ORDER BY schema_name
            """
        )
        return [row["schema_name"] for row in rows]
