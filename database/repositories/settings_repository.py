"""Репозиторий для работы с настройками системы"""

import logging
from typing import Dict, Optional, Tuple

import aiosqlite

from config import DATABASE_PATH, WORK_HOURS_END, WORK_HOURS_START


class SettingsRepository:
    """Репозиторий для хранения настроек бота"""

    @staticmethod
    async def get_setting(key: str, default: str = None) -> Optional[str]:
        """
        Получить значение настройки
        
        Args:
            key: Ключ настройки
            default: Значение по умолчанию
            
        Returns:
            Значение настройки или default
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.execute(
                    "SELECT value FROM settings WHERE key = ?", (key,)
                ) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else default
        except Exception as e:
            logging.error(f"Error getting setting {key}: {e}")
            return default

    @staticmethod
    async def set_setting(key: str, value: str) -> bool:
        """
        Установить значение настройки
        
        Args:
            key: Ключ настройки
            value: Значение
            
        Returns:
            True если успешно
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    """
                    INSERT INTO settings (key, value) 
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )
                await db.commit()
                return True
        except Exception as e:
            logging.error(f"Error setting {key}={value}: {e}")
            return False

    @staticmethod
    async def get_work_hours() -> Tuple[int, int]:
        """
        Получить рабочие часы
        
        Returns:
            Tuple[start_hour, end_hour]
        """
        start = await SettingsRepository.get_setting(
            "work_hours_start", str(WORK_HOURS_START)
        )
        end = await SettingsRepository.get_setting(
            "work_hours_end", str(WORK_HOURS_END)
        )
        
        try:
            return int(start), int(end)
        except ValueError:
            logging.error(f"Invalid work hours in DB: {start}, {end}")
            return WORK_HOURS_START, WORK_HOURS_END

    @staticmethod
    async def update_work_hours(start_hour: int, end_hour: int) -> bool:
        """
        Обновить рабочие часы
        
        Args:
            start_hour: Начало рабочего дня (0-23)
            end_hour: Конец рабочего дня (0-23)
            
        Returns:
            True если успешно
        """
        # Валидация
        if not (0 <= start_hour < 24 and 0 <= end_hour <= 24):
            logging.error(f"Invalid work hours: {start_hour}-{end_hour}")
            return False
        
        if start_hour >= end_hour:
            logging.error(f"Start hour must be less than end hour: {start_hour} >= {end_hour}")
            return False
        
        success_start = await SettingsRepository.set_setting(
            "work_hours_start", str(start_hour)
        )
        success_end = await SettingsRepository.set_setting(
            "work_hours_end", str(end_hour)
        )
        
        return success_start and success_end

    @staticmethod
    async def get_booking_limit() -> int:
        """
        Получить лимит активных записей на пользователя
        
        Returns:
            Лимит записей
        """
        limit_str = await SettingsRepository.get_setting("booking_limit", "3")
        try:
            return int(limit_str)
        except ValueError:
            logging.error(f"Invalid booking limit in DB: {limit_str}")
            return 3

    @staticmethod
    async def update_booking_limit(limit: int) -> bool:
        """
        Обновить лимит записей
        
        Args:
            limit: Новый лимит (1-10)
            
        Returns:
            True если успешно
        """
        if not (1 <= limit <= 10):
            logging.error(f"Invalid booking limit: {limit}")
            return False
        
        return await SettingsRepository.set_setting("booking_limit", str(limit))

    @staticmethod
    async def get_all_settings() -> Dict[str, str]:
        """
        Получить все настройки
        
        Returns:
            Словарь настроек {key: value}
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.execute("SELECT key, value FROM settings") as cursor:
                    rows = await cursor.fetchall()
                    return {row[0]: row[1] for row in rows}
        except Exception as e:
            logging.error(f"Error getting all settings: {e}")
            return {}

    @staticmethod
    async def initialize_defaults() -> bool:
        """
        Инициализировать настройки по умолчанию
        
        Returns:
            True если успешно
        """
        defaults = {
            "work_hours_start": str(WORK_HOURS_START),
            "work_hours_end": str(WORK_HOURS_END),
            "booking_limit": "3",
        }
        
        try:
            for key, value in defaults.items():
                # Устанавливаем только если ещё нет
                existing = await SettingsRepository.get_setting(key)
                if existing is None:
                    await SettingsRepository.set_setting(key, value)
                    logging.info(f"⚙️ Initialized setting: {key}={value}")
            
            return True
        except Exception as e:
            logging.error(f"Error initializing default settings: {e}")
            return False
