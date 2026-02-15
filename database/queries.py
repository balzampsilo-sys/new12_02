"""Фасад для работы с базой данных через репозитории

✅ FIXED: Удален legacy SQLite код (_init_sqlite)
✅ FIXED: Только PostgreSQL через SchemaManager
"""

import logging
from typing import Dict, List, Optional, Tuple

from database.repositories import (
    AdminRepository,
    AnalyticsRepository,
    BookingRepository,
    ClientStats,
    UserRepository,
)
from database.repositories.calendar_repository import CalendarRepository
from database.repositories.settings_repository import SettingsRepository
from database.schema_manager import SchemaManager

# Реэкспортируем ClientStats для обратной совместимости
__all__ = ["Database", "ClientStats"]


class Database:
    """
    Фасад для работы с базой данных.
    Делегирует вызовы специализированным репозиториям.
    
    ✅ FIXED: PostgreSQL-only через SchemaManager
    """

    # === ИНИЦИАЛИЗАЦИЯ ===

    @staticmethod
    async def init_db():
        """
        Инициализация БД с таблицами и индексами
        
        ✅ FIXED: PostgreSQL-only, SQLite removed
        """
        from config import PG_SCHEMA
        
        # Используем SchemaManager для PostgreSQL
        await SchemaManager.init_schema(PG_SCHEMA)
        logging.info(
            f"✅ Database initialized with PostgreSQL\n"
            f"   • Schema: {PG_SCHEMA}\n"
            f"   • All tables created with indexes"
        )

        # Инициализация дополнительных таблиц
        await SettingsRepository.init_settings_table()
        await CalendarRepository.init_calendar_tables()
        logging.info("✅ All database tables initialized")

    # === БРОНИРОВАНИЯ (делегирование в BookingRepository) ===

    @staticmethod
    async def is_slot_free(date_str: str, time_str: str) -> bool:
        return await BookingRepository.is_slot_free(date_str, time_str)

    @staticmethod
    async def get_occupied_slots_for_day(date_str: str) -> List[Tuple[str, int]]:
        """Получить занятые слоты с длительностью

        Returns:
            List[Tuple[time_str, duration_minutes]]
        """
        return await BookingRepository.get_occupied_slots_for_day(date_str)

    @staticmethod
    async def get_month_statuses(year: int, month: int) -> Dict[str, str]:
        return await BookingRepository.get_month_statuses(year, month)

    @staticmethod
    async def get_user_bookings(user_id: int) -> List[Tuple]:
        return await BookingRepository.get_user_bookings(user_id)

    @staticmethod
    async def can_user_book(user_id: int) -> Tuple[bool, int]:
        return await BookingRepository.can_user_book(user_id)

    @staticmethod
    async def can_cancel_booking(date_str: str, time_str: str) -> Tuple[bool, float]:
        return await BookingRepository.can_cancel_booking(date_str, time_str)

    @staticmethod
    async def get_booking_by_id(booking_id: int, user_id: int) -> Optional[Tuple[str, str, str]]:
        return await BookingRepository.get_booking_by_id(booking_id, user_id)

    @staticmethod
    async def get_booking_service_id(booking_id: int) -> Optional[int]:
        """Получить service_id из бронирования

        Args:
            booking_id: ID бронирования

        Returns:
            service_id или None если не найдено
        """
        return await BookingRepository.get_booking_service_id(booking_id)

    @staticmethod
    async def delete_booking(booking_id: int, user_id: int) -> bool:
        return await BookingRepository.delete_booking(booking_id, user_id)

    @staticmethod
    async def cleanup_old_bookings(before_date: str) -> int:
        return await BookingRepository.cleanup_old_bookings(before_date)

    @staticmethod
    async def get_week_schedule(start_date: str, days: int = 7) -> List[Tuple]:
        return await BookingRepository.get_week_schedule(start_date, days)

    @staticmethod
    async def block_slot(date_str: str, time_str: str, admin_id: int, reason: str = None) -> bool:
        return await BookingRepository.block_slot(date_str, time_str, admin_id, reason)

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
        return await BookingRepository.block_slot_with_notification(
            date_str, time_str, admin_id, reason
        )

    @staticmethod
    async def unblock_slot(date_str: str, time_str: str) -> bool:
        return await BookingRepository.unblock_slot(date_str, time_str)

    @staticmethod
    async def is_slot_blocked(date_str: str, time_str: str) -> bool:
        """ДЕПРЕСИРОВАНО: Используйте is_slot_free() вместо этого"""
        result = await BookingRepository.is_slot_free(date_str, time_str)
        return not result

    @staticmethod
    async def get_blocked_slots(date_str: str = None) -> List[Tuple]:
        return await BookingRepository.get_blocked_slots(date_str)

    @staticmethod
    async def get_day_status(date_str: str) -> str:
        """Статус загрузки дня (🟢🟡🔴)"""
        occupied = await BookingRepository.get_occupied_slots_for_day(date_str)
        from config import WORK_HOURS_END, WORK_HOURS_START

        total_slots = WORK_HOURS_END - WORK_HOURS_START
        total_occupied = len(occupied)

        if total_occupied == 0:
            return "🟢"
        elif total_occupied < total_slots:
            return "🟡"
        else:
            return "🔴"

    @staticmethod
    async def mass_update_service(date_str: str, new_service_id: int) -> int:
        """✅ НОВЫЙ: Массовое обновление услуги для всех записей на дату

        Args:
            date_str: Дата в формате YYYY-MM-DD
            new_service_id: ID новой услуги

        Returns:
            Количество обновленных записей
        """
        return await BookingRepository.mass_update_service(date_str, new_service_id)

    # === ПОЛЬЗОВАТЕЛИ (делегирование в UserRepository) ===

    @staticmethod
    async def is_new_user(user_id: int) -> bool:
        return await UserRepository.is_new_user(user_id)

    @staticmethod
    async def get_all_users() -> List[int]:
        return await UserRepository.get_all_users()

    @staticmethod
    async def get_total_users_count() -> int:
        return await UserRepository.get_total_users_count()

    @staticmethod
    async def get_favorite_slots(user_id: int) -> Tuple[Optional[str], Optional[int]]:
        return await UserRepository.get_favorite_slots(user_id)

    # === АНАЛИТИКА И ОТЗЫВЫ (делегирование в AnalyticsRepository) ===

    @staticmethod
    async def log_event(user_id: int, event: str, data: str = ""):
        await AnalyticsRepository.log_event(user_id, event, data)

    @staticmethod
    async def get_client_stats(user_id: int) -> ClientStats:
        return await AnalyticsRepository.get_client_stats(user_id)

    @staticmethod
    async def save_feedback(user_id: int, booking_id: int, rating: int) -> bool:
        return await AnalyticsRepository.save_feedback(user_id, booking_id, rating)

    @staticmethod
    async def get_top_clients(limit: int = 10) -> List[Tuple]:
        return await AnalyticsRepository.get_top_clients(limit)

    # === АДМИНИСТРАТОРЫ (делегирование в AdminRepository) ===

    @staticmethod
    async def get_all_admins() -> List[Tuple[int, str, str, str, str]]:
        """Получить всех администраторов

        Returns:
            List[Tuple[user_id, username, added_by, added_at, role]]
        """
        return await AdminRepository.get_all_admins()

    @staticmethod
    async def is_admin_in_db(user_id: int) -> bool:
        """Проверить админа в БД"""
        return await AdminRepository.is_admin(user_id)

    @staticmethod
    async def add_admin(
        user_id: int,
        username: Optional[str] = None,
        added_by: Optional[int] = None,
        role: str = "moderator",
    ) -> bool:
        """Добавить администратора"""
        return await AdminRepository.add_admin(user_id, username, added_by, role)

    @staticmethod
    async def remove_admin(user_id: int) -> bool:
        """Удалить администратора"""
        return await AdminRepository.remove_admin(user_id)

    @staticmethod
    async def get_admin_count() -> int:
        """Количество админов"""
        return await AdminRepository.get_admin_count()

    @staticmethod
    async def get_admin_role(user_id: int) -> Optional[str]:
        """Получить роль админа"""
        return await AdminRepository.get_admin_role(user_id)

    @staticmethod
    async def update_admin_role(user_id: int, role: str) -> bool:
        """Обновить роль админа"""
        return await AdminRepository.update_admin_role(user_id, role)
