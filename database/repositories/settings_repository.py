"""Репозиторий для работы с настройками

✅ FIXED: Заменен aiosqlite на db_adapter для PostgreSQL поддержки
"""

import logging
from typing import Dict, Optional

from database.db_adapter import db_adapter  # ✅ NEW
from utils.helpers import now_local


class SettingsRepository:
    """Репозиторий для управления настройками
    
    ✅ FIXED: Использует db_adapter вместо aiosqlite
    """

    @staticmethod
    async def init_settings_table():
        """Инициализация таблицы settings (уже создана в SchemaManager)"""
        try:
            logging.info("✅ Settings table initialized (already created by SchemaManager)")
        except Exception as e:
            logging.error(f"Error initializing settings table: {e}")

    @staticmethod
    async def get_setting(key: str) -> Optional[str]:
        """Получить значение настройки"""
        try:
            value = await db_adapter.fetchval(
                "SELECT value FROM settings WHERE key = $1",
                key
            )
            return value
        except Exception as e:
            logging.error(f"Error getting setting {key}: {e}")
            return None

    @staticmethod
    async def set_setting(key: str, value: str, description: str = "") -> bool:
        """Установить значение настройки"""
        try:
            # PostgreSQL UPSERT
            await db_adapter.execute(
                """INSERT INTO settings (key, value, description, updated_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at""",
                key, value, description, now_local()
            )
            logging.info(f"Setting updated: {key} = {value}")
            return True
        except Exception as e:
            logging.error(f"Error setting {key}: {e}")
            return False

    @staticmethod
    async def get_all_settings() -> Dict[str, str]:
        """Получить все настройки"""
        try:
            rows = await db_adapter.fetch(
                "SELECT key, value FROM settings"
            )
            
            if not rows:
                return {}
            
            return {row["key"]: row["value"] for row in rows}
        except Exception as e:
            logging.error(f"Error getting all settings: {e}")
            return {}

    @staticmethod
    async def delete_setting(key: str) -> bool:
        """Удалить настройку"""
        try:
            result = await db_adapter.execute(
                "DELETE FROM settings WHERE key = $1",
                key
            )
            deleted = "DELETE 1" in result
            
            if deleted:
                logging.info(f"Setting deleted: {key}")
            
            return deleted
        except Exception as e:
            logging.error(f"Error deleting setting {key}: {e}")
            return False
