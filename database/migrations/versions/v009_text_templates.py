"""Migration v009: Таблица для хранения текстов бота (i18n)"""

import aiosqlite

from database.migrations.migration_manager import Migration


class V009TextTemplates(Migration):
    """Migration v009: Добавление таблицы text_templates для локализации"""

    version = 9
    description = "Add text_templates table for i18n support"

    async def upgrade(self, db: aiosqlite.Connection):
        """Apply migration"""
        # Создаем таблицу для текстовых шаблонов
        await db.execute(
            """CREATE TABLE IF NOT EXISTS text_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                text_ru TEXT NOT NULL,
                text_en TEXT,
                category TEXT DEFAULT 'general',
                description TEXT,
                is_custom BOOLEAN DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER,
                FOREIGN KEY (updated_by) REFERENCES users(id)
            )"""
        )

        # Создаем индексы для быстрого поиска
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_templates_key ON text_templates(key)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_templates_category ON text_templates(category)"
        )

        # Создаем таблицу истории изменений текстов
        await db.execute(
            """CREATE TABLE IF NOT EXISTS text_changes_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_by INTEGER,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (changed_by) REFERENCES users(id)
            )"""
        )

        # Индекс для истории
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_changes_key ON text_changes_log(key)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_changes_date ON text_changes_log(changed_at)"
        )

        # Добавляем несколько базовых текстов для примера
        base_texts = [
            (
                "common.back",
                "⬅️ Назад",
                "⬅️ Back",
                "common",
                "Кнопка возврата",
            ),
            (
                "common.confirm",
                "✅ Подтвердить",
                "✅ Confirm",
                "common",
                "Кнопка подтверждения",
            ),
            (
                "common.cancel",
                "❌ Отмена",
                "❌ Cancel",
                "common",
                "Кнопка отмены",
            ),
            (
                "booking.button",
                "📅 Записаться",
                "📅 Book Appointment",
                "booking",
                "Кнопка записи",
            ),
            (
                "booking.select_date",
                "📅 Выберите дату",
                "📅 Select Date",
                "booking",
                "Заголовок выбора даты",
            ),
            (
                "booking.select_time",
                "🕒 Выберите время",
                "🕒 Select Time",
                "booking",
                "Заголовок выбора времени",
            ),
        ]

        await db.executemany(
            """INSERT OR IGNORE INTO text_templates 
            (key, text_ru, text_en, category, description) 
            VALUES (?, ?, ?, ?, ?)""",
            base_texts,
        )

    async def downgrade(self, db: aiosqlite.Connection):
        """Rollback migration"""
        await db.execute("DROP INDEX IF EXISTS idx_text_templates_key")
        await db.execute("DROP INDEX IF EXISTS idx_text_templates_category")
        await db.execute("DROP TABLE IF EXISTS text_templates")

        await db.execute("DROP INDEX IF EXISTS idx_text_changes_key")
        await db.execute("DROP INDEX IF EXISTS idx_text_changes_date")
        await db.execute("DROP TABLE IF EXISTS text_changes_log")


# Регистрация миграции
if __name__ == "__main__":
    import asyncio
    import sys
    from pathlib import Path

    # Добавляем корневую директорию в sys.path
    root_dir = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(root_dir))

    from config import DATABASE_PATH
    from database.migrations.migration_manager import MigrationManager

    async def main():
        manager = MigrationManager(DATABASE_PATH)
        manager.register(V009TextTemplates)
        await manager.migrate()
        print("✅ Migration v009 applied successfully")

    asyncio.run(main())
