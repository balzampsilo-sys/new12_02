"""Repository для управления настройками системы"""

import logging
from typing import Optional, Tuple

import aiosqlite

from config import DATABASE_PATH, WORK_HOURS_END, WORK_HOURS_START


class SettingsRepository:
    """Репозиторий для работы с настройками"""

    # Кэш для рабочих часов (обновляется при изменении)
    _work_hours_cache: Optional[Tuple[int, int]] = None

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
                "SELECT COUNT(*) FROM settings WHERE key IN ('work_hours_start', 'work_hours_end')"
            )
            count = (await cursor.fetchone())[0]

            # Если нет - создаем дефолтные из config.py
            if count == 0:
                await db.execute(
                    """
                    INSERT INTO settings (key, value) VALUES
                    ('work_hours_start', ?),
                    ('work_hours_end', ?)
                    """,
                    (str(WORK_HOURS_START), str(WORK_HOURS_END)),
                )
                await db.commit()
                logging.info(
                    f"Settings table initialized with default work hours: {WORK_HOURS_START}-{WORK_HOURS_END}"
                )

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

    @classmethod
    def clear_cache(cls):
        """Очистить кэш (для тестирования)"""
        cls._work_hours_cache = None
