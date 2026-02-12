"""Репозиторий для истории изменений записей

Priority: P0 (High)
Функции:
- Запись истории создания/изменения/отмены
- Получение истории конкретной записи
- Аудит действий пользователей и админов
"""

import logging
from typing import Dict, List, Optional

import aiosqlite

from config import DATABASE_PATH
from database.base_repository import BaseRepository
from utils.helpers import now_local


class BookingHistoryRepository(BaseRepository):
    """Репозиторий для управления историей изменений записей"""

    @staticmethod
    async def log_booking_created(
        booking_id: int, user_id: int, date: str, time: str, service_id: int
    ) -> bool:
        """Залогировать создание записи

        Args:
            booking_id: ID записи
            user_id: ID пользователя
            date: Дата записи
            time: Время записи
            service_id: ID услуги

        Returns:
            bool: Успешно ли залогировано
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    """INSERT INTO booking_history (
                        booking_id, changed_by, changed_by_type, action,
                        new_date, new_time, new_service_id, changed_at
                    ) VALUES (?, ?, 'user', 'created', ?, ?, ?, ?)""",
                    (booking_id, user_id, date, time, service_id, now_local().isoformat()),
                )
                await db.commit()

                logging.info(f"Logged booking creation: booking_id={booking_id} by user={user_id}")
                return True

        except Exception as e:
            logging.error(f"Error logging booking creation: {e}")
            return False

    @staticmethod
    async def log_booking_updated(
        booking_id: int,
        changed_by: int,
        changed_by_type: str,
        old_date: Optional[str] = None,
        old_time: Optional[str] = None,
        new_date: Optional[str] = None,
        new_time: Optional[str] = None,
        old_service_id: Optional[int] = None,
        new_service_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Залогировать изменение записи

        Args:
            booking_id: ID записи
            changed_by: ID пользователя/админа
            changed_by_type: 'user' или 'admin'
            old_date: Старая дата
            old_time: Старое время
            new_date: Новая дата
            new_time: Новое время
            old_service_id: Старая услуга
            new_service_id: Новая услуга
            reason: Причина изменения

        Returns:
            bool: Успешно ли залогировано
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    """INSERT INTO booking_history (
                        booking_id, changed_by, changed_by_type, action,
                        old_date, old_time, new_date, new_time,
                        old_service_id, new_service_id, reason, changed_at
                    ) VALUES (?, ?, ?, 'updated', ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        booking_id,
                        changed_by,
                        changed_by_type,
                        old_date,
                        old_time,
                        new_date,
                        new_time,
                        old_service_id,
                        new_service_id,
                        reason,
                        now_local().isoformat(),
                    ),
                )
                await db.commit()

                logging.info(
                    f"Logged booking update: booking_id={booking_id} by {changed_by_type}={changed_by}"
                )
                return True

        except Exception as e:
            logging.error(f"Error logging booking update: {e}")
            return False

    @staticmethod
    async def log_booking_cancelled(
        booking_id: int,
        cancelled_by: int,
        cancelled_by_type: str,
        date: str,
        time: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Залогировать отмену записи

        Args:
            booking_id: ID записи
            cancelled_by: ID пользователя/админа
            cancelled_by_type: 'user' или 'admin'
            date: Дата отмененной записи
            time: Время отмененной записи
            reason: Причина отмены

        Returns:
            bool: Успешно ли залогировано
        """
        try:
            action = "admin_cancelled" if cancelled_by_type == "admin" else "cancelled"

            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    """INSERT INTO booking_history (
                        booking_id, changed_by, changed_by_type, action,
                        old_date, old_time, reason, changed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        booking_id,
                        cancelled_by,
                        cancelled_by_type,
                        action,
                        date,
                        time,
                        reason,
                        now_local().isoformat(),
                    ),
                )
                await db.commit()

                logging.info(
                    f"Logged booking cancellation: booking_id={booking_id} by {cancelled_by_type}={cancelled_by}"
                )
                return True

        except Exception as e:
            logging.error(f"Error logging booking cancellation: {e}")
            return False

    @staticmethod
    async def get_booking_history(booking_id: int) -> List[Dict]:
        """Получить историю изменений конкретной записи

        Args:
            booking_id: ID записи

        Returns:
            List[Dict] с полями:
                - changed_by: int
                - changed_by_type: str ('user' или 'admin')
                - action: str
                - old_date, old_time, new_date, new_time: Optional[str]
                - old_service_id, new_service_id: Optional[int]
                - reason: Optional[str]
                - changed_at: str
        """
        try:
            rows = await BookingHistoryRepository._execute_query(
                """SELECT
                    changed_by,
                    changed_by_type,
                    action,
                    old_date,
                    old_time,
                    new_date,
                    new_time,
                    old_service_id,
                    new_service_id,
                    reason,
                    changed_at
                FROM booking_history
                WHERE booking_id = ?
                ORDER BY changed_at ASC""",
                (booking_id,),
                fetch_all=True,
            )

            if not rows:
                return []

            history = []
            for row in rows:
                history.append(
                    {
                        "changed_by": row[0],
                        "changed_by_type": row[1],
                        "action": row[2],
                        "old_date": row[3],
                        "old_time": row[4],
                        "new_date": row[5],
                        "new_time": row[6],
                        "old_service_id": row[7],
                        "new_service_id": row[8],
                        "reason": row[9],
                        "changed_at": row[10],
                    }
                )

            return history

        except Exception as e:
            logging.error(f"Error getting booking history for booking_id={booking_id}: {e}")
            return []

    @staticmethod
    async def get_user_booking_history(user_id: int, limit: int = 20) -> List[Dict]:
        """Получить историю всех записей пользователя

        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей

        Returns:
            List[Dict] с историей изменений
        """
        try:
            rows = await BookingHistoryRepository._execute_query(
                """SELECT
                    booking_id,
                    action,
                    new_date,
                    new_time,
                    changed_at
                FROM booking_history
                WHERE changed_by = ? AND changed_by_type = 'user'
                ORDER BY changed_at DESC
                LIMIT ?""",
                (user_id, limit),
                fetch_all=True,
            )

            if not rows:
                return []

            history = []
            for row in rows:
                history.append(
                    {
                        "booking_id": row[0],
                        "action": row[1],
                        "date": row[2],
                        "time": row[3],
                        "changed_at": row[4],
                    }
                )

            return history

        except Exception as e:
            logging.error(f"Error getting user booking history for user_id={user_id}: {e}")
            return []

    @staticmethod
    async def get_admin_actions(admin_id: int, limit: int = 50) -> List[Dict]:
        """Получить действия администратора с записями

        Args:
            admin_id: ID администратора
            limit: Максимальное количество записей

        Returns:
            List[Dict] с действиями
        """
        try:
            rows = await BookingHistoryRepository._execute_query(
                """SELECT
                    booking_id,
                    action,
                    old_date,
                    old_time,
                    new_date,
                    new_time,
                    reason,
                    changed_at
                FROM booking_history
                WHERE changed_by = ? AND changed_by_type = 'admin'
                ORDER BY changed_at DESC
                LIMIT ?""",
                (admin_id, limit),
                fetch_all=True,
            )

            if not rows:
                return []

            actions = []
            for row in rows:
                actions.append(
                    {
                        "booking_id": row[0],
                        "action": row[1],
                        "old_date": row[2],
                        "old_time": row[3],
                        "new_date": row[4],
                        "new_time": row[5],
                        "reason": row[6],
                        "changed_at": row[7],
                    }
                )

            return actions

        except Exception as e:
            logging.error(f"Error getting admin actions for admin_id={admin_id}: {e}")
            return []

    @staticmethod
    async def get_recent_changes(limit: int = 100) -> List[Dict]:
        """Получить последние изменения в системе

        Args:
            limit: Максимальное количество записей

        Returns:
            List[Dict] с последними изменениями
        """
        try:
            rows = await BookingHistoryRepository._execute_query(
                """SELECT
                    booking_id,
                    changed_by,
                    changed_by_type,
                    action,
                    changed_at
                FROM booking_history
                ORDER BY changed_at DESC
                LIMIT ?""",
                (limit,),
                fetch_all=True,
            )

            if not rows:
                return []

            changes = []
            for row in rows:
                changes.append(
                    {
                        "booking_id": row[0],
                        "changed_by": row[1],
                        "changed_by_type": row[2],
                        "action": row[3],
                        "changed_at": row[4],
                    }
                )

            return changes

        except Exception as e:
            logging.error(f"Error getting recent changes: {e}")
            return []
