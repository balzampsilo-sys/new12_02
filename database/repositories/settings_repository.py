"""Repository для управления настройками системы"""

import logging
from typing import Optional, Tuple

import aiosqlite

from config import DATABASE_PATH, WORK_HOURS_END, WORK_HOURS_START


class SettingsRepository:
    """Репозиторий для работы с настройками"""

    # Кэш для рабочих часов (обновляется при изменении)
    _work_hours_cache: Optional[Tuple[int, int]] = None
    # ✅ ДОБАВЛЕНО: Кэш для интервала слотов
    _slot_interval_cache: Optional[int] = None

    @classmethod
    async def init_settings_table(cls):
        """Инициализация таблицы настроек"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Проверяем есть ли настройки рабочих часов
            cursor = await db.execute(
                "SELECT COUNT(*) FROM settings WHERE key IN ('work_hours_start', 'work_hours_end', 'slot_interval_minutes')"
            )
            count = (await cursor.fetchone())[0]

            # Если нет - создаем дефолтные из config.py
            if count == 0:
                await db.execute(
                    """
                    INSERT INTO settings (key, value) VALUES
                    ('work_hours_start', ?),
                    ('work_hours_end', ?),
                    ('slot_interval_minutes', '60')
                    """,
                    (str(WORK_HOURS_START), str(WORK_HOURS_END)),
                )
                await db.commit()
                logging.info(
                    f"Settings table initialized with default work hours: {WORK_HOURS_START}-{WORK_HOURS_END}, slot interval: 60 min"
                )
            else:
                # ✅ МИГРАЦИЯ: Добавляем slot_interval_minutes если его нет
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM settings WHERE key = 'slot_interval_minutes'"
                )
                interval_exists = (await cursor.fetchone())[0]
                
                if interval_exists == 0:
                    await db.execute(
                        "INSERT INTO settings (key, value) VALUES ('slot_interval_minutes', '60')"
                    )
                    await db.commit()
                    logging.info("Added default slot_interval_minutes: 60")

    @classmethod
    async def get_work_hours(cls) -> Tuple[int, int]:
        """
        Получить рабочие часы (начало, конец)

        Returns:
            Tuple[start_hour, end_hour]
        """
        # Проверяем кэш
        if cls._work_hours_cache is not None:
            return cls._work_hours_cache

        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute(
                    """
                    SELECT key, value FROM settings 
                    WHERE key IN ('work_hours_start', 'work_hours_end')
                    """
                )
                rows = await cursor.fetchall()

                if not rows:
                    # Fallback к config.py
                    logging.warning("No work hours in DB, using config.py defaults")
                    cls._work_hours_cache = (WORK_HOURS_START, WORK_HOURS_END)
                    return cls._work_hours_cache

                settings = {row[0]: int(row[1]) for row in rows}
                start = settings.get("work_hours_start", WORK_HOURS_START)
                end = settings.get("work_hours_end", WORK_HOURS_END)

                cls._work_hours_cache = (start, end)
                return cls._work_hours_cache

        except Exception as e:
            logging.error(f"Error getting work hours from DB: {e}")
            # Fallback к config.py
            return (WORK_HOURS_START, WORK_HOURS_END)

    @classmethod
    async def update_work_hours(cls, start_hour: int, end_hour: int) -> bool:
        """
        Обновить рабочие часы

        Args:
            start_hour: Начало рабочего дня (0-23)
            end_hour: Конец рабочего дня (1-24)

        Returns:
            True если успешно
        """
        # Валидация
        if not (0 <= start_hour <= 23):
            logging.error(f"Invalid start_hour: {start_hour}")
            return False

        if not (1 <= end_hour <= 24):
            logging.error(f"Invalid end_hour: {end_hour}")
            return False

        if start_hour >= end_hour:
            logging.error(f"start_hour ({start_hour}) >= end_hour ({end_hour})")
            return False

        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO settings (key, value, updated_at) 
                    VALUES ('work_hours_start', ?, CURRENT_TIMESTAMP)
                    """,
                    (str(start_hour),),
                )

                await db.execute(
                    """
                    INSERT OR REPLACE INTO settings (key, value, updated_at) 
                    VALUES ('work_hours_end', ?, CURRENT_TIMESTAMP)
                    """,
                    (str(end_hour),),
                )

                await db.commit()

            # Обновляем кэш
            cls._work_hours_cache = (start_hour, end_hour)

            logging.info(f"Work hours updated: {start_hour}:00 - {end_hour}:00")
            return True

        except Exception as e:
            logging.error(f"Error updating work hours: {e}")
            return False

    # ✅ НОВОЕ: Методы для интервала слотов
    
    @classmethod
    async def get_slot_interval(cls) -> int:
        """
        Получить интервал слотов в минутах
        
        Returns:
            Интервал в минутах (15, 30, 45, или 60)
        """
        # Проверяем кэш
        if cls._slot_interval_cache is not None:
            return cls._slot_interval_cache
        
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute(
                    "SELECT value FROM settings WHERE key = 'slot_interval_minutes'"
                )
                row = await cursor.fetchone()
                
                if not row:
                    # Дефолт: 60 минут (часовые слоты)
                    logging.warning("No slot_interval in DB, using default: 60")
                    cls._slot_interval_cache = 60
                    return 60
                
                interval = int(row[0])
                cls._slot_interval_cache = interval
                return interval
                
        except Exception as e:
            logging.error(f"Error getting slot_interval from DB: {e}")
            return 60  # Дефолт
    
    @classmethod
    async def update_slot_interval(cls, interval_minutes: int) -> bool:
        """
        Обновить интервал слотов
        
        Args:
            interval_minutes: Интервал в минутах (15, 30, 45, 60)
        
        Returns:
            True если успешно
        """
        # Валидация: только разрешенные интервалы
        valid_intervals = [15, 30, 45, 60]
        if interval_minutes not in valid_intervals:
            logging.error(f"Invalid interval: {interval_minutes}. Must be one of {valid_intervals}")
            return False
        
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES ('slot_interval_minutes', ?, CURRENT_TIMESTAMP)
                    """,
                    (str(interval_minutes),)
                )
                await db.commit()
            
            # Обновляем кэш
            cls._slot_interval_cache = interval_minutes
            
            logging.info(f"Slot interval updated to {interval_minutes} minutes")
            return True
            
        except Exception as e:
            logging.error(f"Error updating slot_interval: {e}")
            return False

    @classmethod
    def clear_cache(cls):
        """Очистить кэш (для тестирования)"""
        cls._work_hours_cache = None
        cls._slot_interval_cache = None  # ✅ ДОБАВЛЕНО
