"""Репозиторий для работы с бронированиями

✅ FIXED: Заменен aiosqlite на db_adapter для PostgreSQL поддержки
"""

import calendar
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from config import (
    CANCELLATION_HOURS,
    MAX_BOOKINGS_PER_USER,
    TIMEZONE,
    WORK_HOURS_END,
    WORK_HOURS_START,
)
from database.db_adapter import db_adapter  # ✅ NEW
from utils.helpers import now_local


class BookingRepository:
    """Репозиторий для управления бронированиями
    
    ✅ FIXED: Использует db_adapter вместо aiosqlite
    """

    @staticmethod
    async def is_slot_free(date_str: str, time_str: str) -> bool:
        """Проверить свободен ли слот (включая блокировки)"""
        try:
            # Проверяем бронирование
            booking_exists = await db_adapter.fetchval(
                "SELECT EXISTS(SELECT 1 FROM bookings WHERE date=$1 AND time=$2)",
                date_str, time_str
            )
            
            # Проверяем блокировку
            blocked_exists = await db_adapter.fetchval(
                "SELECT EXISTS(SELECT 1 FROM blocked_slots WHERE date=$1 AND time=$2)",
                date_str, time_str
            )

            return not booking_exists and not blocked_exists
        except Exception as e:
            logging.error(f"Error checking slot {date_str} {time_str}: {e}")
            return False

    @staticmethod
    async def get_occupied_slots_for_day(date_str: str) -> List[Tuple[str, int]]:
        """Получить все занятые слоты за день с длительностью

        Returns:
            List[Tuple[time_str, duration_minutes]]
            Например: [('10:00', 60), ('14:00', 90), ('16:00', 120)]
        """
        occupied = []
        try:
            # Забронированные с duration из services
            bookings = await db_adapter.fetch(
                """SELECT b.time, COALESCE(s.duration_minutes, 60) as duration
                FROM bookings b
                LEFT JOIN services s ON b.service_id = s.id
                WHERE b.date = $1""",
                date_str
            )
            if bookings:
                occupied.extend((row["time"], row["duration"]) for row in bookings)

            # Заблокированные (длительность 60 мин по умолчанию)
            blocked = await db_adapter.fetch(
                "SELECT time FROM blocked_slots WHERE date = $1",
                date_str
            )
            if blocked:
                occupied.extend((row["time"], 60) for row in blocked)

        except Exception as e:
            logging.error(f"Error getting occupied slots for {date_str}: {e}")

        return occupied

    @staticmethod
    async def get_month_statuses(year: int, month: int) -> Dict[str, str]:
        """Получить статусы всех дней месяца"""
        try:
            first_day = datetime(year, month, 1).date()
            last_day_num = calendar.monthrange(year, month)[1]
            last_day = datetime(year, month, last_day_num).date()

            statuses = {}
            total_slots = WORK_HOURS_END - WORK_HOURS_START

            # Объединенный запрос UNION ALL
            rows = await db_adapter.fetch(
                """SELECT date, SUM(cnt) as total_count FROM (
                    SELECT date, COUNT(*) as cnt FROM bookings
                    WHERE date >= $1 AND date <= $2 GROUP BY date
                    UNION ALL
                    SELECT date, COUNT(*) as cnt FROM blocked_slots
                    WHERE date >= $3 AND date <= $4 GROUP BY date
                ) GROUP BY date""",
                first_day.isoformat(),
                last_day.isoformat(),
                first_day.isoformat(),
                last_day.isoformat(),
            )

            if rows:
                for row in rows:
                    date_str = row["date"]
                    total_count = row["total_count"]
                    
                    if total_count == 0:
                        statuses[date_str] = "🟢"
                    elif total_count < total_slots:
                        statuses[date_str] = "🟡"
                    else:
                        statuses[date_str] = "🔴"

            return statuses
        except Exception as e:
            logging.error(f"Error getting month statuses for {year}-{month}: {e}")
            return {}

    @staticmethod
    async def get_bookings_for_date(date_str: str) -> List[Dict]:
        """Получить все записи на конкретную дату (для напоминаний)

        Args:
            date_str: Дата в формате YYYY-MM-DD

        Returns:
            List[Dict] с полями:
                - user_id: int
                - username: str
                - time: str
                - service_id: int
                - service_name: str
                - duration_minutes: int
                - created_at: str
        """
        try:
            rows = await db_adapter.fetch(
                """SELECT
                    b.user_id,
                    b.username,
                    b.time,
                    b.service_id,
                    COALESCE(s.name, 'Консультация') as service_name,
                    COALESCE(s.duration_minutes, 60) as duration_minutes,
                    b.created_at
                FROM bookings b
                LEFT JOIN services s ON b.service_id = s.id
                WHERE b.date = $1
                ORDER BY b.time""",
                date_str,
            )

            if not rows:
                return []

            # Преобразуем в список словарей
            bookings = []
            for row in rows:
                bookings.append(
                    {
                        "user_id": row["user_id"],
                        "username": row["username"] or f"ID{row['user_id']}",
                        "time": row["time"],
                        "service_id": row["service_id"],
                        "service_name": row["service_name"],
                        "duration_minutes": row["duration_minutes"],
                        "created_at": str(row["created_at"]),
                    }
                )

            return bookings

        except Exception as e:
            logging.error(f"Error getting bookings for date {date_str}: {e}")
            return []

    @staticmethod
    async def get_user_bookings(user_id: int) -> List[Tuple]:
        """Получить активные (будущие) записи пользователя С ИНФОРМАЦИЕЙ ОБ УСЛУГЕ

        Returns:
            List[Tuple[
                booking_id: int,
                date: str,
                time: str,
                username: str,
                created_at: str,
                service_id: int,
                service_name: str,
                duration_minutes: int,
                price: str
            ]]
        """
        try:
            now = now_local()

            rows = await db_adapter.fetch(
                """SELECT
                    b.id,
                    b.date,
                    b.time,
                    b.username,
                    b.created_at,
                    b.service_id,
                    COALESCE(s.name, 'Основная услуга') as service_name,
                    COALESCE(s.duration_minutes, 60) as duration_minutes,
                    COALESCE(s.price, '—') as price
                FROM bookings b
                LEFT JOIN services s ON b.service_id = s.id
                WHERE b.user_id = $1
                ORDER BY b.date, b.time""",
                user_id,
            )

            if not rows:
                return []

            # Фильтруем только будущие
            future_bookings = []
            for row in rows:
                date_str = row["date"]
                time_str = row["time"]

                booking_dt_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                booking_dt = TIMEZONE.localize(booking_dt_naive)

                if booking_dt >= now:
                    # Конвертируем в tuple для совместимости
                    future_bookings.append((
                        row["id"],
                        row["date"],
                        row["time"],
                        row["username"],
                        str(row["created_at"]),
                        row["service_id"],
                        row["service_name"],
                        row["duration_minutes"],
                        row["price"],
                    ))

            return future_bookings
        except Exception as e:
            logging.error(f"Error getting bookings for user {user_id}: {e}")
            return []

    @staticmethod
    async def can_user_book(user_id: int) -> Tuple[bool, int]:
        """Проверить лимит записей пользователя"""
        try:
            bookings = await BookingRepository.get_user_bookings(user_id)
            count = len(bookings)
            return count < MAX_BOOKINGS_PER_USER, count
        except Exception as e:
            logging.error(f"Error checking booking limit for user {user_id}: {e}")
            return False, 0

    @staticmethod
    async def can_cancel_booking(date_str: str, time_str: str) -> Tuple[bool, float]:
        """Проверить возможность отмены (>24ч)"""
        try:
            booking_dt_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            booking_dt = TIMEZONE.localize(booking_dt_naive)
            now = now_local()
            hours_until = (booking_dt - now).total_seconds() / 3600
            return hours_until >= CANCELLATION_HOURS, hours_until
        except Exception as e:
            logging.error(f"Error checking cancel possibility: {e}")
            return False, 0.0

    @staticmethod
    async def get_booking_by_id(booking_id: int, user_id: int) -> Optional[Tuple[str, str, str]]:
        """Получить запись по ID"""
        row = await db_adapter.fetchrow(
            "SELECT date, time, username FROM bookings WHERE id=$1 AND user_id=$2",
            booking_id, user_id
        )
        if row:
            return (row["date"], row["time"], row["username"])
        return None

    @staticmethod
    async def get_booking_service_id(booking_id: int) -> Optional[int]:
        """Получить service_id из бронирования"""
        try:
            return await db_adapter.fetchval(
                "SELECT service_id FROM bookings WHERE id=$1",
                booking_id
            )
        except Exception as e:
            logging.error(f"Error getting booking service_id: {e}")
            return None

    @staticmethod
    async def delete_booking(booking_id: int, user_id: int) -> bool:
        """Удалить запись"""
        try:
            result = await db_adapter.execute(
                "DELETE FROM bookings WHERE id=$1 AND user_id=$2",
                booking_id, user_id
            )
            # PostgreSQL возвращает "DELETE N"
            deleted = "DELETE 1" in result or "DELETE 0" not in result

            if deleted:
                logging.info(f"Booking {booking_id} deleted by user {user_id}")
            else:
                logging.warning(f"Booking {booking_id} not found for user {user_id}")

            return deleted
        except Exception as e:
            logging.error(f"Error deleting booking {booking_id}: {e}")
            return False

    @staticmethod
    async def cleanup_old_bookings(before_date: str) -> int:
        """Удалить старые записи"""
        try:
            result = await db_adapter.execute(
                "DELETE FROM bookings WHERE date < $1",
                before_date
            )
            # Парсим "DELETE N"
            deleted_count = int(result.split()[-1]) if result else 0
            logging.info(f"Cleaned up {deleted_count} old bookings")
            return deleted_count
        except Exception as e:
            logging.error(f"Error cleaning up old bookings: {e}")
            return 0

    @staticmethod
    async def get_week_schedule(start_date: str, days: int = 7) -> List[Tuple]:
        """Получить расписание на N дней с услугами

        Returns:
            List[Tuple[date, time, username, service_name, duration, price]]
        """
        try:
            end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=days)).strftime(
                "%Y-%m-%d"
            )

            rows = await db_adapter.fetch(
                """SELECT
                    b.date,
                    b.time,
                    b.username,
                    COALESCE(s.name, 'Услуга') as service_name,
                    COALESCE(s.duration_minutes, 60) as duration,
                    COALESCE(s.price, '—') as price
                FROM bookings b
                LEFT JOIN services s ON b.service_id = s.id
                WHERE b.date >= $1 AND b.date <= $2
                ORDER BY b.date, b.time""",
                start_date, end_date
            )
            
            if not rows:
                return []
            
            # Конвертируем в tuples
            return [(row["date"], row["time"], row["username"], 
                     row["service_name"], row["duration"], row["price"]) 
                    for row in rows]
        except Exception as e:
            logging.error(f"Error getting week schedule: {e}")
            return []

    @staticmethod
    async def block_slot(date_str: str, time_str: str, admin_id: int, reason: str = None) -> bool:
        """Заблокировать слот"""
        try:
            await db_adapter.execute(
                "INSERT INTO blocked_slots (date, time, reason, blocked_by, blocked_at) "
                "VALUES ($1, $2, $3, $4, $5)",
                date_str, time_str, reason, admin_id, now_local()
            )
            logging.info(f"Slot {date_str} {time_str} blocked by admin {admin_id}")
            return True
        except Exception as e:
            # PostgreSQL unique constraint violation
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                logging.warning(f"Slot {date_str} {time_str} already blocked or booked")
                return False
            logging.error(f"Error blocking slot {date_str} {time_str}: {e}")
            return False

    @staticmethod
    async def block_slot_with_notification(
        date_str: str, time_str: str, admin_id: int, reason: str = None
    ) -> Tuple[bool, List[Dict]]:
        """
        Заблокировать слот с уведомлением пользователей.

        Если слот занят - удаляет бронь и возвращает данные для уведомления.

        Args:
            date_str: Дата в формате YYYY-MM-DD
            time_str: Время в формате HH:MM
            admin_id: ID администратора
            reason: Причина блокировки

        Returns:
            Tuple[success: bool, cancelled_users: List[Dict]]
            cancelled_users = [{
                'user_id': int,
                'username': str,
                'date': str,
                'time': str,
                'reason': str
            }]
        """
        try:
            async with db_adapter.acquire() as conn:
                async with conn.transaction():
                    # Проверяем существующие записи
                    existing_bookings = await conn.fetch(
                        "SELECT user_id, username FROM bookings WHERE date=$1 AND time=$2",
                        date_str, time_str
                    )

                    cancelled_users = []

                    # Если есть записи - удаляем их
                    if existing_bookings:
                        for row in existing_bookings:
                            cancelled_users.append(
                                {
                                    "user_id": row["user_id"],
                                    "username": row["username"] or f"ID{row['user_id']}",
                                    "date": date_str,
                                    "time": time_str,
                                    "reason": reason,
                                }
                            )

                        # Удаляем бронь
                        await conn.execute(
                            "DELETE FROM bookings WHERE date=$1 AND time=$2",
                            date_str, time_str
                        )
                        logging.info(
                            f"Cancelled {len(cancelled_users)} booking(s) for slot {date_str} {time_str}"
                        )

                    # Блокируем слот
                    await conn.execute(
                        "INSERT INTO blocked_slots (date, time, reason, blocked_by, blocked_at) "
                        "VALUES ($1, $2, $3, $4, $5)",
                        date_str, time_str, reason, admin_id, now_local()
                    )

                    logging.info(
                        f"Slot {date_str} {time_str} blocked by admin {admin_id} "
                        f"with {len(cancelled_users)} cancellations"
                    )

                    return True, cancelled_users

        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                logging.warning(f"Slot {date_str} {time_str} already blocked")
                return False, []
            logging.error(f"Error blocking slot with notification {date_str} {time_str}: {e}")
            return False, []

    @staticmethod
    async def unblock_slot(date_str: str, time_str: str) -> bool:
        """Разблокировать слот"""
        try:
            result = await db_adapter.execute(
                "DELETE FROM blocked_slots WHERE date = $1 AND time = $2",
                date_str, time_str
            )
            deleted = "DELETE 1" in result
            if deleted:
                logging.info(f"Slot {date_str} {time_str} unblocked")
            return deleted
        except Exception as e:
            logging.error(f"Error unblocking slot {date_str} {time_str}: {e}")
            return False

    @staticmethod
    async def get_blocked_slots(date_str: str = None) -> List[Tuple]:
        """Получить заблокированные слоты"""
        try:
            if date_str:
                rows = await db_adapter.fetch(
                    "SELECT date, time, reason FROM blocked_slots WHERE date = $1 ORDER BY time",
                    date_str
                )
            else:
                rows = await db_adapter.fetch(
                    "SELECT date, time, reason FROM blocked_slots ORDER BY date, time"
                )
            
            if not rows:
                return []
            
            return [(row["date"], row["time"], row["reason"]) for row in rows]
        except Exception as e:
            logging.error(f"Error getting blocked slots: {e}")
            return []

    @staticmethod
    async def mass_update_service(date_str: str, new_service_id: int) -> int:
        """✅ НОВЫЙ МЕТОД: Массовое обновление услуги для всех записей на дату

        Args:
            date_str: Дата в формате YYYY-MM-DD
            new_service_id: ID новой услуги

        Returns:
            Количество обновленных записей
        """
        try:
            result = await db_adapter.execute(
                "UPDATE bookings SET service_id = $1 WHERE date = $2",
                new_service_id, date_str
            )
            # Парсим "UPDATE N"
            updated_count = int(result.split()[-1]) if result else 0

            logging.info(
                f"Mass service update: {updated_count} bookings on {date_str} "
                f"changed to service_id={new_service_id}"
            )

            return updated_count
        except Exception as e:
            logging.error(f"Error in mass_update_service for {date_str}: {e}")
            return 0
