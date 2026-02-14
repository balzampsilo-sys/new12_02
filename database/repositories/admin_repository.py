"""Репозиторий для работы с администраторами

✅ FIXED: Заменен aiosqlite на db_adapter для PostgreSQL поддержки
"""

import logging
from typing import List, Optional, Tuple

from database.db_adapter import db_adapter  # ✅ NEW
from utils.helpers import now_local


class AdminRepository:
    """Репозиторий для управления администраторами
    
    ✅ FIXED: Использует db_adapter вместо aiosqlite
    """

    @staticmethod
    async def is_admin(user_id: int) -> bool:
        """Проверить является ли пользователь админом"""
        try:
            exists = await db_adapter.fetchval(
                "SELECT EXISTS(SELECT 1 FROM admins WHERE user_id=$1)",
                user_id
            )
            return exists or False
        except Exception as e:
            logging.error(f"Error checking admin status for {user_id}: {e}")
            return False

    @staticmethod
    async def get_all_admins() -> List[Tuple[int, str, str, str, str]]:
        """Получить всех администраторов

        Returns:
            List[Tuple[user_id, username, added_by, added_at, role]]
        """
        try:
            rows = await db_adapter.fetch(
                "SELECT user_id, username, added_by, added_at, role FROM admins ORDER BY added_at"
            )
            
            if not rows:
                return []
            
            return [
                (
                    row["user_id"],
                    row["username"] or "—",
                    str(row["added_by"]) if row["added_by"] else "System",
                    str(row["added_at"]),
                    row["role"] or "moderator"
                )
                for row in rows
            ]
        except Exception as e:
            logging.error(f"Error getting all admins: {e}")
            return []

    @staticmethod
    async def add_admin(
        user_id: int,
        username: Optional[str] = None,
        added_by: Optional[int] = None,
        role: str = "moderator",
    ) -> bool:
        """Добавить администратора"""
        try:
            await db_adapter.execute(
                "INSERT INTO admins (user_id, username, added_by, added_at, role) "
                "VALUES ($1, $2, $3, $4, $5)",
                user_id, username, added_by, now_local(), role
            )
            logging.info(f"Admin added: {user_id} (role={role})")
            return True
        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                logging.warning(f"Admin {user_id} already exists")
            else:
                logging.error(f"Error adding admin {user_id}: {e}")
            return False

    @staticmethod
    async def remove_admin(user_id: int) -> bool:
        """Удалить администратора"""
        try:
            result = await db_adapter.execute(
                "DELETE FROM admins WHERE user_id=$1",
                user_id
            )
            deleted = "DELETE 1" in result
            if deleted:
                logging.info(f"Admin removed: {user_id}")
            return deleted
        except Exception as e:
            logging.error(f"Error removing admin {user_id}: {e}")
            return False

    @staticmethod
    async def get_admin_count() -> int:
        """Получить количество администраторов"""
        try:
            count = await db_adapter.fetchval("SELECT COUNT(*) FROM admins")
            return count or 0
        except Exception as e:
            logging.error(f"Error getting admin count: {e}")
            return 0

    @staticmethod
    async def get_admin_role(user_id: int) -> Optional[str]:
        """Получить роль администратора"""
        try:
            role = await db_adapter.fetchval(
                "SELECT role FROM admins WHERE user_id=$1",
                user_id
            )
            return role
        except Exception as e:
            logging.error(f"Error getting admin role for {user_id}: {e}")
            return None

    @staticmethod
    async def update_admin_role(user_id: int, role: str) -> bool:
        """Обновить роль администратора"""
        try:
            result = await db_adapter.execute(
                "UPDATE admins SET role=$1 WHERE user_id=$2",
                role, user_id
            )
            updated = "UPDATE 1" in result
            if updated:
                logging.info(f"Admin role updated: {user_id} -> {role}")
            return updated
        except Exception as e:
            logging.error(f"Error updating admin role for {user_id}: {e}")
            return False
