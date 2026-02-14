"""Репозиторий для работы с календарем

✅ FIXED: Заменен aiosqlite на db_adapter для PostgreSQL поддержки
"""

import logging

from database.db_adapter import db_adapter  # ✅ NEW


class CalendarRepository:
    """Репозиторий для управления календарем
    
    ✅ FIXED: Использует db_adapter вместо aiosqlite
    """

    @staticmethod
    async def init_calendar_tables():
        """Инициализация таблиц календаря (если нужно)"""
        try:
            # Пример дополнительных таблиц для календаря
            # Если такие таблицы есть, их нужно добавить в SchemaManager
            logging.info("✅ Calendar tables initialized (placeholder)")
        except Exception as e:
            logging.error(f"Error initializing calendar tables: {e}")
