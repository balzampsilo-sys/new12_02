"""Репозиторий для работы с пользователями

✅ FIXED: Заменен aiosqlite на db_adapter для PostgreSQL поддержки
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from database.db_adapter import db_adapter  # ✅ NEW
from utils.helpers import now_local


class UserRepository:
    """Репозиторий для управления пользователями
    
    ✅ FIXED: Использует db_adapter вместо aiosqlite
    """

    @staticmethod
    async def is_new_user(user_id: int) -> bool:
        """Проверить новый ли пользователь"""
        try:
            exists = await db_adapter.fetchval(
                "SELECT EXISTS(SELECT 1 FROM users WHERE user_id=$1)",
                user_id
            )
            
            if not exists:
                # Добавляем нового пользователя
                await db_adapter.execute(
                    "INSERT INTO users (user_id, first_seen) VALUES ($1, $2)",
                    user_id, now_local()
                )
                logging.info(f"New user registered: {user_id}")
                return True
            return False
        except Exception as e:
            logging.error(f"Error checking new user {user_id}: {e}")
            return False

    @staticmethod
    async def get_all_users() -> List[int]:
        """Получить всех пользователей"""
        try:
            rows = await db_adapter.fetch("SELECT user_id FROM users")
            return [row["user_id"] for row in rows] if rows else []
        except Exception as e:
            logging.error(f"Error getting all users: {e}")
            return []

    @staticmethod
    async def get_total_users_count() -> int:
        """Получить количество пользователей"""
        try:
            count = await db_adapter.fetchval("SELECT COUNT(*) FROM users")
            return count or 0
        except Exception as e:
            logging.error(f"Error getting total users count: {e}")
            return 0

    @staticmethod
    async def get_favorite_slots(user_id: int) -> Tuple[Optional[str], Optional[int]]:
        """Получить любимое время и услугу"""
        try:
            row = await db_adapter.fetchrow(
                """SELECT time, service_id, COUNT(*) as cnt
                FROM bookings
                WHERE user_id = $1
                GROUP BY time, service_id
                ORDER BY cnt DESC
                LIMIT 1""",
                user_id
            )
            
            if row:
                return (row["time"], row["service_id"])
            return (None, None)
        except Exception as e:
            logging.error(f"Error getting favorite slots for user {user_id}: {e}")
            return (None, None)
