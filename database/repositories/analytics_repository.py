"""Репозиторий для аналитики и отзывов

✅ FIXED: Заменен aiosqlite на db_adapter для PostgreSQL поддержки
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple

from database.db_adapter import db_adapter  # ✅ NEW
from utils.helpers import now_local


@dataclass
class ClientStats:
    """Статистика клиента"""
    total_bookings: int
    completed_bookings: int
    avg_rating: float
    favorite_time: str
    first_booking: str


class AnalyticsRepository:
    """Репозиторий для аналитики
    
    ✅ FIXED: Использует db_adapter вместо aiosqlite
    """

    @staticmethod
    async def log_event(user_id: int, event: str, data: str = ""):
        """Логировать событие"""
        try:
            await db_adapter.execute(
                "INSERT INTO analytics (user_id, event, data, timestamp) VALUES ($1, $2, $3, $4)",
                user_id, event, data, now_local()
            )
        except Exception as e:
            logging.error(f"Error logging event {event} for user {user_id}: {e}")

    @staticmethod
    async def get_client_stats(user_id: int) -> ClientStats:
        """Получить статистику клиента"""
        try:
            # Total bookings
            total = await db_adapter.fetchval(
                "SELECT COUNT(*) FROM bookings WHERE user_id = $1",
                user_id
            ) or 0

            # Completed bookings (прошедшие)
            now = now_local().date().isoformat()
            completed = await db_adapter.fetchval(
                "SELECT COUNT(*) FROM bookings WHERE user_id = $1 AND date < $2",
                user_id, now
            ) or 0

            # Average rating
            avg_rating = await db_adapter.fetchval(
                "SELECT AVG(rating) FROM feedback WHERE user_id = $1",
                user_id
            )
            avg_rating = float(avg_rating) if avg_rating else 0.0

            # Favorite time
            fav_row = await db_adapter.fetchrow(
                """SELECT time, COUNT(*) as cnt
                FROM bookings
                WHERE user_id = $1
                GROUP BY time
                ORDER BY cnt DESC
                LIMIT 1""",
                user_id
            )
            favorite_time = fav_row["time"] if fav_row else "—"

            # First booking
            first_row = await db_adapter.fetchrow(
                "SELECT date FROM bookings WHERE user_id = $1 ORDER BY date, time LIMIT 1",
                user_id
            )
            first_booking = first_row["date"] if first_row else "—"

            return ClientStats(
                total_bookings=total,
                completed_bookings=completed,
                avg_rating=avg_rating,
                favorite_time=favorite_time,
                first_booking=first_booking,
            )
        except Exception as e:
            logging.error(f"Error getting client stats for user {user_id}: {e}")
            return ClientStats(0, 0, 0.0, "—", "—")

    @staticmethod
    async def save_feedback(user_id: int, booking_id: int, rating: int) -> bool:
        """Сохранить отзыв"""
        try:
            await db_adapter.execute(
                "INSERT INTO feedback (user_id, booking_id, rating, timestamp) VALUES ($1, $2, $3, $4)",
                user_id, booking_id, rating, now_local()
            )
            logging.info(f"Feedback saved: user={user_id}, booking={booking_id}, rating={rating}")
            return True
        except Exception as e:
            logging.error(f"Error saving feedback: {e}")
            return False

    @staticmethod
    async def get_top_clients(limit: int = 10) -> List[Tuple]:
        """Получить топ клиентов по количеству записей"""
        try:
            rows = await db_adapter.fetch(
                """SELECT user_id, COUNT(*) as booking_count
                FROM bookings
                GROUP BY user_id
                ORDER BY booking_count DESC
                LIMIT $1""",
                limit
            )
            
            if not rows:
                return []
            
            return [(row["user_id"], row["booking_count"]) for row in rows]
        except Exception as e:
            logging.error(f"Error getting top clients: {e}")
            return []
