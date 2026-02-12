"""Миграция v008: Добавление колонки slot_interval_minutes в services

Priority: P0 (Critical)
Reason: Необходимо для гибкой настройки интервалов слотов для каждой услуги
"""

import aiosqlite

from database.migrations.migration_manager import Migration


class AddSlotInterval(Migration):
    """Добавление slot_interval_minutes в таблицу services"""

    version = 8
    description = "Add slot_interval_minutes column to services table"

    async def up(self, db: aiosqlite.Connection) -> None:
        """Применение миграции"""
        # Проверяем, есть ли уже колонка
        cursor = await db.execute("PRAGMA table_info(services)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if "slot_interval_minutes" in column_names:
            print(f"  ✅ Column slot_interval_minutes already exists, skipping")
            return

        # Добавляем колонку с значением по умолчанию 60 минут
        await db.execute(
            "ALTER TABLE services ADD COLUMN slot_interval_minutes INTEGER DEFAULT 60 NOT NULL"
        )
        
        # Обновляем существующие записи
        await db.execute("UPDATE services SET slot_interval_minutes = 60 WHERE slot_interval_minutes IS NULL")
        
        await db.commit()
        print(f"  ✅ Added column slot_interval_minutes with default value 60")

    async def down(self, db: aiosqlite.Connection) -> None:
        """Откат миграции
        
        ⚠️ SQLite не поддерживает DROP COLUMN до версии 3.35.0
        Поэтому требуется пересоздание таблицы
        """
        # 1. Создаем временную таблицу без колонки
        await db.execute(
            """
            CREATE TABLE services_backup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER NOT NULL,
                price TEXT NOT NULL,
                color TEXT,
                display_order INTEGER NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT 1
            )
            """
        )

        # 2. Копируем данные без slot_interval_minutes
        await db.execute(
            """
            INSERT INTO services_backup 
            (id, name, description, duration_minutes, price, color, display_order, is_active)
            SELECT id, name, description, duration_minutes, price, color, display_order, is_active
            FROM services
            """
        )

        # 3. Удаляем старую таблицу
        await db.execute("DROP TABLE services")

        # 4. Переименовываем временную таблицу
        await db.execute("ALTER TABLE services_backup RENAME TO services")

        await db.commit()
        print(f"  ✅ Removed column slot_interval_minutes")
