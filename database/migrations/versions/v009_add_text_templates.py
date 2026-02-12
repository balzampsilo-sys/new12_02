"""Migration v009: Add text_templates table for customizable bot texts"""

import aiosqlite

from database.migrations.migration_manager import Migration


class V009AddTextTemplates(Migration):
    """Add text_templates table for hybrid localization system"""

    version = 9
    description = "Add text_templates table for customizable bot texts"

    async def upgrade(self, db: aiosqlite.Connection):
        """Create text_templates table"""
        # Create table for text templates
        await db.execute(
            """CREATE TABLE IF NOT EXISTS text_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                text_ru TEXT NOT NULL,
                text_en TEXT,
                category TEXT DEFAULT 'general',
                description TEXT,
                is_custom INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER,
                FOREIGN KEY (updated_by) REFERENCES admins(user_id) ON DELETE SET NULL
            )"""
        )

        # Create index for faster lookups
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_templates_key ON text_templates(key)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_templates_category ON text_templates(category)"
        )

        # Create trigger to update updated_at
        await db.execute(
            """CREATE TRIGGER IF NOT EXISTS update_text_template_timestamp
            AFTER UPDATE ON text_templates
            FOR EACH ROW
            BEGIN
                UPDATE text_templates
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = NEW.id;
            END"""
        )

        # Insert some default templates (optional - YAML is primary source)
        # These serve as examples and fallbacks
        default_templates = [
            (
                "booking.button",
                "📅 Записаться",
                "📅 Book Appointment",
                "booking",
                "Кнопка записи в главном меню",
            ),
            (
                "booking.my_bookings",
                "📋 Мои записи",
                "📋 My Bookings",
                "booking",
                "Кнопка просмотра записей",
            ),
            (
                "common.back",
                "⬅️ Назад",
                "⬅️ Back",
                "common",
                "Кнопка возврата",
            ),
            (
                "common.cancel",
                "❌ Отмена",
                "❌ Cancel",
                "common",
                "Кнопка отмены",
            ),
            (
                "errors.slot_taken",
                "❌ Это время уже занято",
                "❌ This time slot is already taken",
                "errors",
                "Сообщение об ошибке - слот занят",
            ),
        ]

        for key, text_ru, text_en, category, description in default_templates:
            await db.execute(
                """INSERT OR IGNORE INTO text_templates 
                (key, text_ru, text_en, category, description, is_custom)
                VALUES (?, ?, ?, ?, ?, 0)""",
                (key, text_ru, text_en, category, description),
            )

    async def downgrade(self, db: aiosqlite.Connection):
        """Remove text_templates table"""
        await db.execute("DROP TRIGGER IF EXISTS update_text_template_timestamp")
        await db.execute("DROP INDEX IF EXISTS idx_text_templates_category")
        await db.execute("DROP INDEX IF EXISTS idx_text_templates_key")
        await db.execute("DROP TABLE IF EXISTS text_templates")


if __name__ == "__main__":
    import asyncio
    import logging
    from config import DATABASE_PATH
    from database.migrations.migration_manager import MigrationManager

    logging.basicConfig(level=logging.INFO)

    async def main():
        manager = MigrationManager(DATABASE_PATH)
        manager.register(V009AddTextTemplates)
        await manager.migrate()
        print("✅ Migration v009 applied successfully")

    asyncio.run(main())
