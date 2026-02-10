"""Миграция: Добавление услуг с обратной совместимостью"""

import logging
from database.migrations.migration_manager import Migration


class AddServicesBackwardCompatible(Migration):
    version = 4
    description = "Add services and schedule settings with backward compatibility"
    
    async def upgrade(self, db):
        """Применение миграции (идемпотентно)"""
        
        # 1. Создаем таблицу услуг
        logging.info("Creating services table...")
        await db.execute(
            """CREATE TABLE IF NOT EXISTS services
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             name TEXT NOT NULL,
             description TEXT,
             duration_minutes INTEGER NOT NULL,
             price TEXT,
             color TEXT DEFAULT '#4CAF50',
             is_active BOOLEAN DEFAULT 1,
             display_order INTEGER DEFAULT 0,
             created_at TEXT DEFAULT CURRENT_TIMESTAMP,
             UNIQUE(name))"""
        )
        
        # 2. Создаем таблицу настроек расписания
        logging.info("Creating schedule_settings table...")
        await db.execute(
            """CREATE TABLE IF NOT EXISTS schedule_settings
            (id INTEGER PRIMARY KEY CHECK (id = 1),
             work_hours_start INTEGER DEFAULT 9,
             work_hours_end INTEGER DEFAULT 19,
             max_bookings_per_day INTEGER DEFAULT 8,
             updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"""
        )
        
        # 3. Создаем индексы
        logging.info("Creating indexes...")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_services_active ON services(is_active, display_order)"
        )
        
        # 4. Вставляем дефолтные настройки
        logging.info("Inserting default schedule settings...")
        await db.execute(
            """INSERT OR IGNORE INTO schedule_settings (id, work_hours_start, work_hours_end)
            VALUES (1, 9, 19)"""
        )
        
        # 5. Проверяем структуру таблицы bookings
        logging.info("Checking bookings table structure...")
        async with db.execute("PRAGMA table_info(bookings)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        # 6. Добавляем колонки если их нет
        if 'service_id' not in column_names:
            logging.info("Adding service_id column to bookings...")
            try:
                await db.execute("ALTER TABLE bookings ADD COLUMN service_id INTEGER")
                logging.info("service_id column added successfully")
            except Exception as e:
                # Колонка может уже существовать
                logging.warning(f"Could not add service_id column (might already exist): {e}")
        else:
            logging.info("service_id column already exists")
        
        if 'duration_minutes' not in column_names:
            logging.info("Adding duration_minutes column to bookings...")
            try:
                await db.execute(
                    "ALTER TABLE bookings ADD COLUMN duration_minutes INTEGER DEFAULT 60"
                )
                logging.info("duration_minutes column added successfully")
            except Exception as e:
                logging.warning(f"Could not add duration_minutes column (might already exist): {e}")
        else:
            logging.info("duration_minutes column already exists")
        
        # 7. Добавляем индекс на service_id
        logging.info("Creating index on service_id...")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_bookings_service ON bookings(service_id)"
        )
        
        # 8. Вставляем дефолтную услугу
        logging.info("Inserting default service...")
        await db.execute(
            """INSERT OR IGNORE INTO services (name, description, duration_minutes, price, display_order)
            VALUES ('Консультация', 'Стандартная консультация', 60, '3000 ₽', 1)"""
        )
        
        # 9. Обновляем существующие записи (только где service_id NULL)
        logging.info("Updating existing bookings with default service...")
        async with db.execute(
            """UPDATE bookings 
            SET service_id = (SELECT id FROM services WHERE name='Консультация' LIMIT 1),
                duration_minutes = 60
            WHERE service_id IS NULL"""
        ) as cursor:
            updated_rows = cursor.rowcount
            logging.info(f"Updated {updated_rows} existing bookings")
        
        logging.info("Migration v004 completed successfully")
    
    async def downgrade(self, db):
        """Откат миграции"""
        logging.info("Rolling back migration v004...")
        
        # Удаляем таблицы
        await db.execute("DROP TABLE IF EXISTS services")
        await db.execute("DROP TABLE IF EXISTS schedule_settings")
        
        # SQLite не поддерживает DROP COLUMN напрямую
        # Для production лучше оставить колонки или пересоздать таблицу
        try:
            # Пересоздаем таблицу без колонок service_id и duration_minutes
            await db.execute(
                """CREATE TABLE bookings_backup AS 
                SELECT id, date, time, user_id, username, created_at 
                FROM bookings"""
            )
            await db.execute("DROP TABLE bookings")
            await db.execute("ALTER TABLE bookings_backup RENAME TO bookings")
            
            # Восстанавливаем индексы
            await db.execute(
                "CREATE UNIQUE INDEX idx_bookings_date_time ON bookings(date, time)"
            )
            logging.info("Migration v004 rolled back successfully")
        except Exception as e:
            logging.error(f"Error during rollback: {e}")
            raise
