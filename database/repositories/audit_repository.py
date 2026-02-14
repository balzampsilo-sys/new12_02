"""Репозиторий для аудита действий администраторов

✅ FIXED: Заменен aiosqlite на db_adapter для PostgreSQL поддержки
"""

import logging
from typing import Dict, List, Optional

from database.db_adapter import db_adapter  # ✅ NEW
from utils.helpers import now_local


class AuditRepository:
    """Репозиторий для аудита действий
    
    ✅ FIXED: Использует db_adapter вместо aiosqlite
    """

    @staticmethod
    async def log_action(
        admin_id: int,
        action: str,
        target_id: Optional[str] = None,
        details: Optional[str] = None,
    ) -> bool:
        """Залогировать действие администратора"""
        try:
            await db_adapter.execute(
                """INSERT INTO audit_log (admin_id, action, target_id, details, timestamp)
                VALUES ($1, $2, $3, $4, $5)""",
                admin_id, action, target_id, details, now_local()
            )
            logging.debug(f"Audit log: admin={admin_id}, action={action}")
            return True
        except Exception as e:
            logging.error(f"Error logging audit action: {e}")
            return False

    @staticmethod
    async def get_recent_logs(limit: int = 50) -> List[Dict]:
        """Получить последние записи аудита"""
        try:
            rows = await db_adapter.fetch(
                """SELECT id, admin_id, action, target_id, details, timestamp
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT $1""",
                limit
            )
            
            if not rows:
                return []
            
            return [
                {
                    "id": row["id"],
                    "admin_id": row["admin_id"],
                    "action": row["action"],
                    "target_id": row["target_id"] or "",
                    "details": row["details"] or "",
                    "timestamp": str(row["timestamp"]),
                }
                for row in rows
            ]
        except Exception as e:
            logging.error(f"Error getting recent audit logs: {e}")
            return []

    @staticmethod
    async def get_admin_logs(admin_id: int, limit: int = 50) -> List[Dict]:
        """Получить логи конкретного администратора"""
        try:
            rows = await db_adapter.fetch(
                """SELECT id, admin_id, action, target_id, details, timestamp
                FROM audit_log
                WHERE admin_id = $1
                ORDER BY timestamp DESC
                LIMIT $2""",
                admin_id, limit
            )
            
            if not rows:
                return []
            
            return [
                {
                    "id": row["id"],
                    "admin_id": row["admin_id"],
                    "action": row["action"],
                    "target_id": row["target_id"] or "",
                    "details": row["details"] or "",
                    "timestamp": str(row["timestamp"]),
                }
                for row in rows
            ]
        except Exception as e:
            logging.error(f"Error getting admin logs for {admin_id}: {e}")
            return []

    @staticmethod
    async def search_logs(action: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Поиск логов по действию"""
        try:
            if action:
                rows = await db_adapter.fetch(
                    """SELECT id, admin_id, action, target_id, details, timestamp
                    FROM audit_log
                    WHERE action = $1
                    ORDER BY timestamp DESC
                    LIMIT $2""",
                    action, limit
                )
            else:
                rows = await db_adapter.fetch(
                    """SELECT id, admin_id, action, target_id, details, timestamp
                    FROM audit_log
                    ORDER BY timestamp DESC
                    LIMIT $1""",
                    limit
                )
            
            if not rows:
                return []
            
            return [
                {
                    "id": row["id"],
                    "admin_id": row["admin_id"],
                    "action": row["action"],
                    "target_id": row["target_id"] or "",
                    "details": row["details"] or "",
                    "timestamp": str(row["timestamp"]),
                }
                for row in rows
            ]
        except Exception as e:
            logging.error(f"Error searching audit logs: {e}")
            return []
