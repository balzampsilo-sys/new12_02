"""Миграция v007: Исправление CHECK constraint в booking_history

Priority: P0 (Critical)

Проблема:
- CHECK constraint ограничивает action старыми значениями
- Новые значения: 'create', 'cancel', 'reschedule'

Решение:
- Пересоздать таблицу без CHECK constraint
"""

import logging

import aiosqlite

from database.migrations.migration_manager import Migration


class FixBookingHistoryConstraints(Migration):
    """Миграция: Удаление CHECK constraint из booking_history"""

    version = 7
    description = "Remove CHECK constraint from booking_history.action"

    async def upgrade(self, db: aiosqlite.Connection) -> None:
        """Применить миграцию"""
        logging.info(f"[v{self.version}] Fixing booking_history constraints...")

        # 1. Проверяем есть ли таблица
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='booking_history'"
        ) as cursor:
            table_exists = await cursor.fetchone()

        if not table_exists:
            logging.info(f"[v{self.version}] Table doesn't exist, skipping")
            return

        # 2. Сохраняем данные
        logging.info(f"[v{self.version}] Backing up data...")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS booking_history_backup AS
            SELECT * FROM booking_history
            """
        )

        # 3. Удаляем индексы
        await db.execute("DROP INDEX IF EXISTS idx_booking_history_booking")
        await db.execute("DROP INDEX IF EXISTS idx_booking_history_action")
        await db.execute("DROP INDEX IF EXISTS idx_booking_history_changed_by")
        await db.execute("DROP INDEX IF EXISTS idx_booking_history_changed_at")

        # 4. Удаляем старую таблицу
        await db.execute("DROP TABLE IF EXISTS booking_history")

        # 5. Создаем новую таблицу БЕЗ CHECK constraint
        logging.info(f"[v{self.version}] Creating new table without constraints...")
        await db.execute(
            """
            CREATE TABLE booking_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                changed_by INTEGER NOT NULL,
                changed_by_type TEXT NOT NULL,
                old_date TEXT,
                old_time TEXT,
                new_date TEXT,
                new_time TEXT,
                old_service_id INTEGER,
                new_service_id INTEGER,
                reason TEXT,
                changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 6. Восстанавливаем данные
        logging.info(f"[v{self.version}] Restoring data...")
        await db.execute(
            """
            INSERT INTO booking_history
            SELECT * FROM booking_history_backup
            """
        )

        # 7. Удаляем backup
        await db.execute("DROP TABLE booking_history_backup")

        # 8. Восстанавливаем индексы
        logging.info(f"[v{self.version}] Recreating indexes...")
        await db.execute(
            "CREATE INDEX idx_booking_history_booking ON booking_history(booking_id)"
        )
        await db.execute(
            "CREATE INDEX idx_booking_history_action ON booking_history(action)"
        )
        await db.execute(
            "CREATE INDEX idx_booking_history_changed_by ON booking_history(changed_by)"
        )
        await db.execute(
            "CREATE INDEX idx_booking_history_changed_at ON booking_history(changed_at)"
        )

        logging.info(f"[v{self.version}] ✅ Constraints fixed successfully")

    async def downgrade(self, db: aiosqlite.Connection) -> None:
        """Откат миграции"""
        logging.info(f"[v{self.version}] Rollback not needed (constraint removal)")
