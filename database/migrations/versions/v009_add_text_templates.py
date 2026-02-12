"""Migration v009: Добавление таблицы text_templates для локализации

Цель: Система управления текстами бота с поддержкой многоязычности
"""

import logging

import aiosqlite

from database.migrations.migration_manager import Migration


class Migration009AddTextTemplates(Migration):
    """Migration v009: Text Templates table for i18n"""

    version = 9
    description = "Add text_templates table for localization"

    async def upgrade(self, db: aiosqlite.Connection):
        """Применить миграцию"""
        logging.info("Creating text_templates table...")

        # Создаём таблицу
        await db.execute(
            """CREATE TABLE IF NOT EXISTS text_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                text_ru TEXT NOT NULL,
                text_en TEXT,
                category TEXT DEFAULT 'general',
                description TEXT,
                is_customized INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER,
                FOREIGN KEY (updated_by) REFERENCES admins(user_id) ON DELETE SET NULL
            )"""
        )

        # Индексы для быстрого поиска
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_templates_key ON text_templates(key)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_templates_category ON text_templates(category)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_templates_customized ON text_templates(is_customized)"
        )

        # Таблица истории изменений (для audit)
        await db.execute(
            """CREATE TABLE IF NOT EXISTS text_changes_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                lang TEXT DEFAULT 'ru',
                changed_by INTEGER NOT NULL,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (changed_by) REFERENCES admins(user_id) ON DELETE CASCADE
            )"""
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_changes_key ON text_changes_log(key)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_text_changes_date ON text_changes_log(changed_at)"
        )

        # Добавляем несколько примеров текстов для теста
        sample_texts = [
            (
                "common.back",
                "⬅️ Назад",
                "⬅️ Back",
                "common",
                "Кнопка возврата",
            ),
            (
                "booking.button",
                "📅 Записаться",
                "📅 Book Appointment",
                "booking",
                "Главная кнопка записи",
            ),
            (
                "booking.success",
                "✅ Вы успешно записаны!",
                "✅ Successfully booked!",
                "booking",
                "Подтверждение записи",
            ),
            (
                "booking.errors.slot_taken",
                "❌ Это время уже занято",
                "❌ This time is already taken",
                "booking",
                "Ошибка: слот занят",
            ),
            (
                "admin.menu",
                "👨‍💼 АДМИН-ПАНЕЛЬ",
                "👨‍💼 ADMIN PANEL",
                "admin",
                "Заголовок админ-панели",
            ),
        ]

        for key, text_ru, text_en, category, description in sample_texts:
            await db.execute(
                """INSERT OR IGNORE INTO text_templates
                (key, text_ru, text_en, category, description, is_customized)
                VALUES (?, ?, ?, ?, ?, 0)""",
                (key, text_ru, text_en, category, description),
            )

        logging.info("✅ text_templates table created with sample data")

    async def downgrade(self, db: aiosqlite.Connection):
        """Откатить миграцию"""
        logging.info("Dropping text_templates tables...")

        await db.execute("DROP TABLE IF EXISTS text_changes_log")
        await db.execute("DROP TABLE IF EXISTS text_templates")

        logging.info("✅ text_templates tables dropped")


if __name__ == "__main__":
    # Прямое применение миграции
    import asyncio

    from config import DATABASE_PATH

    async def apply_migration():
        migration = Migration009AddTextTemplates()
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("BEGIN")
            try:
                await migration.upgrade(db)
                await db.commit()
                print("✅ Migration v009 applied successfully")
            except Exception as e:
                await db.rollback()
                print(f"❌ Migration v009 failed: {e}")
                raise

    asyncio.run(apply_migration())
