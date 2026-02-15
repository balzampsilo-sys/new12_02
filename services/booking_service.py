"""Сервис управления бронированием

✅ FIXED: Удален legacy SQLite код, используется db_adapter
✅ FIXED: Multi-tenant изоляция через PostgreSQL schemas
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncpg.exceptions

from config import (
    FEEDBACK_HOURS_AFTER,
    MAX_BOOKINGS_PER_USER,
    REMINDER_HOURS_BEFORE_1H,
    REMINDER_HOURS_BEFORE_2H,
    REMINDER_HOURS_BEFORE_24H,
    TIMEZONE,
)
from database.db_adapter import db_adapter
from database.queries import Database
from database.repositories.booking_history_repository import BookingHistoryRepository
from utils.helpers import now_local

# Transaction timeout
DB_TRANSACTION_TIMEOUT = 30.0  # секунд


class BookingService:
    """Сервис для работы с бронированием
    
    ✅ FIXED: Использует db_adapter для PostgreSQL multi-tenant support
    """

    def __init__(self, scheduler: AsyncIOScheduler, bot):
        self.scheduler = scheduler
        self.bot = bot

    async def _get_default_service(self) -> Optional[Tuple[int, int]]:
        """Получить дефолтную активную услугу

        Returns:
            Tuple[service_id, duration] или None если услуг нет
        """
        from database.repositories.service_repository import ServiceRepository

        services = await ServiceRepository.get_all_services(active_only=True)

        if not services:
            logging.error("No active services available for booking")
            return None

        # Берем первую активную услугу по display_order
        default_service = services[0]
        logging.info(
            f"Using default service: {default_service.name} "
            f"(id={default_service.id}, duration={default_service.duration_minutes}min)"
        )

        return (default_service.id, default_service.duration_minutes)

    async def create_booking(
        self,
        date_str: str,
        time_str: str,
        user_id: int,
        username: str,
        service_id: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Создание записи с атомарной проверкой и поддержкой услуг
        
        ✅ FIXED: Использует db_adapter вместо aiosqlite
        ✅ FIXED: PostgreSQL placeholders ($1, $2) вместо SQLite (?)

        Args:
            date_str: Дата в формате YYYY-MM-DD
            time_str: Время в формате HH:MM
            user_id: ID пользователя
            username: Имя пользователя
            service_id: ID услуги (опционально)

        Returns:
            Tuple[bool, str]: (success, error_code)
        """
        # Если service_id не передан, используем дефолтную услугу
        if service_id is None:
            default = await self._get_default_service()
            if default is None:
                logging.error("Cannot create booking: no active services")
                return False, "no_services"

            service_id, duration = default
        else:
            # Проверяем что услуга существует и активна
            from database.repositories.service_repository import ServiceRepository

            service = await ServiceRepository.get_service_by_id(service_id)
            if not service:
                logging.warning(f"Service {service_id} not found")
                return False, "service_not_available"

            if not service.is_active:
                logging.warning(f"Service {service_id} is inactive")
                return False, "service_not_available"

            duration = service.duration_minutes

        # ✅ FIXED: Используем db_adapter с timeout
        try:
            async with asyncio.timeout(DB_TRANSACTION_TIMEOUT):
                async with db_adapter.acquire() as conn:
                    async with conn.transaction():
                        # Проверяем лимит пользователя
                        user_count = await conn.fetchval(
                            "SELECT COUNT(*) FROM bookings WHERE user_id=$1 AND date >= CURRENT_DATE",
                            user_id,
                        )

                        if user_count >= MAX_BOOKINGS_PER_USER:
                            logging.warning(
                                f"User {user_id} exceeded booking limit: {user_count}/{MAX_BOOKINGS_PER_USER}"
                            )
                            return False, "limit_exceeded"

                        # Проверяем пересечения с учетом длительности
                        is_available = await self._check_slot_availability_in_transaction(
                            conn, date_str, time_str, duration
                        )

                        if not is_available:
                            logging.info(f"Slot {date_str} {time_str} not available (race condition prevented)")
                            return False, "slot_taken"

                        # Создаем запись
                        booking_id = await conn.fetchval(
                            """INSERT INTO bookings (date, time, user_id, username, service_id, duration_minutes, created_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            RETURNING id""",
                            date_str,
                            time_str,
                            user_id,
                            username,
                            service_id,
                            duration,
                            now_local(),
                        )

                        # ✅ Записываем в историю (вне транзакции, чтобы не блокировать)
                        await BookingHistoryRepository.record_create(
                            booking_id=booking_id,
                            user_id=user_id,
                            date=date_str,
                            time=time_str,
                            service_id=service_id,
                        )

                        logging.info(
                            f"Booking created: {booking_id} for user {user_id}, "
                            f"service {service_id}, duration {duration}min"
                        )

                # Планируем напоминание (вне транзакции)
                await self._schedule_reminder(booking_id, date_str, time_str, user_id)
                await Database.log_event(
                    user_id, "booking_created", f"{date_str} {time_str} service_id={service_id}"
                )

                return True, "success"

        except asyncpg.exceptions.UniqueViolationError:
            logging.warning(f"Unique constraint violation creating booking: {date_str} {time_str}")
            return False, "slot_taken"
        except asyncio.TimeoutError:
            logging.error(
                f"Transaction timeout ({DB_TRANSACTION_TIMEOUT}s) creating booking "
                f"{date_str} {time_str} for user {user_id}"
            )
            return False, "timeout_error"
        except Exception as e:
            logging.error(f"Error in create_booking: {e}", exc_info=True)
            return False, "unknown_error"

    async def _check_slot_availability_in_transaction(
        self, conn, date_str: str, time_str: str, duration_minutes: int
    ) -> bool:
        """Проверка доступности с учетом пересечений (внутри транзакции)
        
        ✅ FIXED: PostgreSQL syntax

        Args:
            conn: Database connection (внутри транзакции)
            date_str: Дата в формате YYYY-MM-DD
            time_str: Время в формате HH:MM
            duration_minutes: Длительность в минутах

        Returns:
            True если слот свободен, False если занят
        """
        # Парсим время начала
        start_time = datetime.strptime(time_str, "%H:%M")
        end_time = start_time + timedelta(minutes=duration_minutes)

        # Получаем все записи на этот день
        existing = await conn.fetch(
            "SELECT time, duration_minutes FROM bookings WHERE date=$1",
            date_str,
        )

        # Проверяем заблокированные слоты
        blocked = await conn.fetch(
            "SELECT time FROM blocked_slots WHERE date=$1",
            date_str,
        )

        # Проверяем пересечения с существующими записями
        for row in existing:
            booking_time_str = row["time"]
            booking_duration = row["duration_minutes"] or 60
            
            booking_start = datetime.strptime(booking_time_str, "%H:%M")
            booking_end = booking_start + timedelta(minutes=booking_duration)

            # Интервалы пересекаются если:
            # start_time < booking_end AND end_time > booking_start
            if start_time < booking_end and end_time > booking_start:
                logging.debug(
                    f"Slot conflict: {time_str}-{end_time.strftime('%H:%M')} overlaps with "
                    f"{booking_time_str}-{booking_end.strftime('%H:%M')}"
                )
                return False

        # Проверяем заблокированные слоты
        for row in blocked:
            if row["time"] == time_str:
                logging.debug(f"Slot {time_str} is blocked")
                return False

        return True

    async def reschedule_booking(
        self,
        booking_id: int,
        old_date_str: str,
        old_time_str: str,
        new_date_str: str,
        new_time_str: str,
        user_id: int,
        username: str,
    ) -> bool:
        """Перенос записи в одной транзакции
        
        ✅ FIXED: Используем db_adapter

        Args:
            booking_id: ID записи для переноса
            old_date_str: Старая дата
            old_time_str: Старое время
            new_date_str: Новая дата
            new_time_str: Новое время
            user_id: ID пользователя
            username: Имя пользователя

        Returns:
            True если перенос успешен, False иначе
        """
        try:
            async with asyncio.timeout(DB_TRANSACTION_TIMEOUT):
                async with db_adapter.acquire() as conn:
                    async with conn.transaction():
                        # 1. Проверяем что старая запись существует
                        old_booking = await conn.fetchrow(
                            "SELECT id, duration_minutes, service_id FROM bookings WHERE id=$1 AND user_id=$2",
                            booking_id,
                            user_id,
                        )

                        if not old_booking:
                            logging.warning(f"Booking {booking_id} not found for user {user_id}")
                            return False

                        duration = old_booking["duration_minutes"] or 60
                        old_service_id = old_booking["service_id"]

                        # 2. Проверяем что новый слот свободен
                        is_available = await self._check_slot_availability_in_transaction(
                            conn, new_date_str, new_time_str, duration
                        )

                        if not is_available:
                            logging.info(f"Slot {new_date_str} {new_time_str} not available")
                            return False

                        # 3. Обновляем запись
                        await conn.execute(
                            """UPDATE bookings
                            SET date=$1, time=$2, created_at=$3
                            WHERE id=$4""",
                            new_date_str,
                            new_time_str,
                            now_local(),
                            booking_id,
                        )

                        # ✅ Записываем в историю
                        await BookingHistoryRepository.record_reschedule(
                            booking_id=booking_id,
                            user_id=user_id,
                            changed_by_type="user",
                            old_date=old_date_str,
                            old_time=old_time_str,
                            new_date=new_date_str,
                            new_time=new_time_str,
                            old_service_id=old_service_id,
                            new_service_id=old_service_id,
                        )

                # Перепланируем напоминания (вне транзакции)
                self._remove_job_safe(f"reminder_{booking_id}")
                self._remove_job_safe(f"feedback_{booking_id}")
                await self._schedule_reminder(booking_id, new_date_str, new_time_str, user_id)

                await Database.log_event(
                    user_id,
                    "booking_rescheduled",
                    f"{old_date_str} {old_time_str} -> {new_date_str} {new_time_str}",
                )

                logging.info(f"Booking {booking_id} rescheduled successfully")
                return True

        except asyncio.TimeoutError:
            logging.error(
                f"Transaction timeout ({DB_TRANSACTION_TIMEOUT}s) rescheduling booking {booking_id}"
            )
            return False
        except Exception as e:
            logging.error(f"Error in reschedule_booking: {e}", exc_info=True)
            return False

    def _remove_job_safe(self, job_id: str) -> None:
        """Безопасное удаление задачи из scheduler"""
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

    async def _schedule_reminder(
        self, booking_id: int, date_str: str, time_str: str, user_id: int
    ) -> None:
        """Планирование напоминаний"""
        try:
            booking_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            booking_datetime = TIMEZONE.localize(booking_datetime)
            now = now_local()
            time_until_booking = booking_datetime - now

            # Напоминание
            if time_until_booking > timedelta(hours=REMINDER_HOURS_BEFORE_24H):
                reminder_time = booking_datetime - timedelta(hours=REMINDER_HOURS_BEFORE_24H)
                self.scheduler.add_job(
                    self._send_reminder,
                    "date",
                    run_date=reminder_time,
                    args=[user_id, date_str, time_str],
                    id=f"reminder_{booking_id}",
                    replace_existing=True,
                )
            elif time_until_booking > timedelta(hours=REMINDER_HOURS_BEFORE_2H):
                reminder_time = booking_datetime - timedelta(hours=REMINDER_HOURS_BEFORE_2H)
                self.scheduler.add_job(
                    self._send_reminder,
                    "date",
                    run_date=reminder_time,
                    args=[user_id, date_str, time_str],
                    id=f"reminder_{booking_id}",
                    replace_existing=True,
                )
            elif time_until_booking > timedelta(hours=REMINDER_HOURS_BEFORE_1H):
                reminder_time = booking_datetime - timedelta(hours=REMINDER_HOURS_BEFORE_1H)
                self.scheduler.add_job(
                    self._send_reminder,
                    "date",
                    run_date=reminder_time,
                    args=[user_id, date_str, time_str],
                    id=f"reminder_{booking_id}",
                    replace_existing=True,
                )

            # Запрос обратной связи
            feedback_time = booking_datetime + timedelta(hours=FEEDBACK_HOURS_AFTER)
            self.scheduler.add_job(
                self._send_feedback_request,
                "date",
                run_date=feedback_time,
                args=[user_id, booking_id, date_str, time_str],
                id=f"feedback_{booking_id}",
                replace_existing=True,
            )
        except Exception as e:
            logging.error(f"Error scheduling reminder: {e}", exc_info=True)

    async def cancel_booking(
        self, date_str: str, time_str: str, user_id: int, admin_id: Optional[int] = None
    ) -> Tuple[bool, int]:
        """Отмена записи
        
        ✅ FIXED: Использует db_adapter
        """
        try:
            async with db_adapter.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT id, service_id FROM bookings WHERE date=$1 AND time=$2 AND user_id=$3",
                    date_str,
                    time_str,
                    user_id,
                )
                
                if not result:
                    return False, 0

                booking_id = result["id"]
                service_id = result["service_id"]

                await conn.execute(
                    "DELETE FROM bookings WHERE id=$1",
                    booking_id,
                )

            # Записываем в историю
            changed_by = admin_id if admin_id else user_id
            changed_by_type = "admin" if admin_id else "user"

            await BookingHistoryRepository.record_cancel(
                booking_id=booking_id,
                user_id=changed_by,
                changed_by_type=changed_by_type,
                date=date_str,
                time=time_str,
                service_id=service_id,
                reason="Cancelled by user" if not admin_id else "Cancelled by admin",
            )

            # Удаляем напоминания
            self._remove_job_safe(f"reminder_{booking_id}")
            self._remove_job_safe(f"feedback_{booking_id}")

            await Database.log_event(user_id, "booking_cancelled", f"{date_str} {time_str}")
            logging.info(
                f"Booking {booking_id} cancelled by {changed_by_type} (id={changed_by})"
            )
            return True, booking_id
        except Exception as e:
            logging.error(f"Error cancelling booking: {e}", exc_info=True)
            return False, 0

    async def restore_reminders(self, batch_size: int = 50) -> None:
        """Восстановить напоминания после рестарта
        
        ✅ FIXED: Использует db_adapter
        """
        try:
            now = now_local()
            
            all_bookings = await db_adapter.fetch(
                "SELECT id, date, time, user_id FROM bookings ORDER BY date, time"
            )

            total_bookings = len(all_bookings)
            restored_count = 0
            processed_count = 0

            logging.info(f"Starting reminder restoration for {total_bookings} bookings...")

            # Обработка батчами
            for i in range(0, total_bookings, batch_size):
                batch = all_bookings[i : i + batch_size]

                for row in batch:
                    try:
                        booking_id = row["id"]
                        date_str = row["date"]
                        time_str = row["time"]
                        user_id = row["user_id"]
                        
                        booking_datetime = datetime.strptime(
                            f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
                        )
                        booking_datetime = TIMEZONE.localize(booking_datetime)

                        # Восстановить напоминание
                        reminder_time = booking_datetime - timedelta(
                            hours=REMINDER_HOURS_BEFORE_24H
                        )
                        if reminder_time > now:
                            self.scheduler.add_job(
                                self._send_reminder,
                                "date",
                                run_date=reminder_time,
                                args=[user_id, date_str, time_str],
                                id=f"reminder_{booking_id}",
                                replace_existing=True,
                            )
                            restored_count += 1

                        # Восстановить запрос обратной связи
                        feedback_time = booking_datetime + timedelta(hours=FEEDBACK_HOURS_AFTER)
                        if feedback_time > now:
                            self.scheduler.add_job(
                                self._send_feedback_request,
                                "date",
                                run_date=feedback_time,
                                args=[user_id, booking_id, date_str, time_str],
                                id=f"feedback_{booking_id}",
                                replace_existing=True,
                            )

                    except Exception as e:
                        logging.warning(
                            f"Failed to restore reminders for booking {booking_id}: {e}"
                        )
                    finally:
                        processed_count += 1

                # Логируем прогресс
                logging.info(
                    f"Reminder restoration progress: {processed_count}/{total_bookings} processed, "
                    f"{restored_count} restored"
                )

            logging.info(
                f"Reminder restoration completed: {restored_count} reminders restored from "
                f"{total_bookings} bookings"
            )
        except Exception as e:
            logging.error(f"Error restoring reminders: {e}", exc_info=True)

    async def _send_reminder(self, user_id: int, date_str: str, time_str: str) -> None:
        """Отправка напоминания"""
        try:
            from config import DAY_NAMES, SERVICE_LOCATION

            date_obj = datetime.strptime(date_str, "%Y-%m-%d")

            await self.bot.send_message(
                user_id,
                "⏰ НАПОМИНАНИЕ!\n\n"
                "У вас запись ЗАВТРА:\n"
                f"📅 {date_obj.strftime('%d.%m.%Y')} ({DAY_NAMES[date_obj.weekday()]})\n"
                f"🕒 {time_str}\n"
                f"📍 {SERVICE_LOCATION}\n\n"
                "Если нужно отменить → '📋 Мои записи'",
            )
            await Database.log_event(user_id, "reminder_sent", f"{date_str} {time_str}")
        except Exception as e:
            logging.error(f"Error sending reminder: {e}", exc_info=True)

    async def _send_feedback_request(
        self, user_id: int, booking_id: int, date_str: str, time_str: str
    ) -> None:
        """Запрос обратной связи"""
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        feedback_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⭐⭐⭐⭐⭐", callback_data=f"feedback:{booking_id}:5"
                    ),
                    InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"feedback:{booking_id}:4"),
                ],
                [
                    InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"feedback:{booking_id}:3"),
                    InlineKeyboardButton(text="⭐⭐", callback_data=f"feedback:{booking_id}:2"),
                    InlineKeyboardButton(text="⭐", callback_data=f"feedback:{booking_id}:1"),
                ],
            ]
        )

        try:
            await self.bot.send_message(
                user_id,
                "💬 Как прошла встреча?\n\nОцените качество услуги:",
                reply_markup=feedback_kb,
            )
            await Database.log_event(user_id, "feedback_request_sent", f"{date_str} {time_str}")
        except Exception as e:
            logging.error(f"Error sending feedback request: {e}", exc_info=True)
