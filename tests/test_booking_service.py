"""Тесты для BookingService

✅ P0: Критические сценарии бронирования
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.booking_service import BookingService
from utils.helpers import now_local


@pytest.fixture
def mock_scheduler():
    """Mock scheduler"""
    scheduler = MagicMock()
    scheduler.add_job = MagicMock()
    scheduler.remove_job = MagicMock()
    return scheduler


@pytest.fixture
def mock_bot():
    """Mock bot"""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def booking_service(mock_scheduler, mock_bot):
    """BookingService instance"""
    return BookingService(mock_scheduler, mock_bot)


class TestCreateBooking:
    """Тесты создания бронирования"""

    @pytest.mark.asyncio
    async def test_create_booking_success(self, booking_service):
        """Успешное создание записи"""
        with patch("services.booking_service.db_adapter") as mock_db, \
             patch("services.booking_service.BookingHistoryRepository") as mock_history, \
             patch("services.booking_service.Database") as mock_database:
            
            # Mock connection and transaction
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(side_effect=[0, None])  # user_count, then booking_id
            mock_conn.execute = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])  # no existing bookings
            mock_conn.transaction = MagicMock(return_value=AsyncMock().__aenter__())
            
            mock_db.acquire = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock()
            ))
            
            mock_history.record_create = AsyncMock()
            mock_database.log_event = AsyncMock()

            # Mock service repository
            with patch("database.repositories.service_repository.ServiceRepository") as mock_service_repo:
                mock_service = MagicMock()
                mock_service.id = 1
                mock_service.duration_minutes = 60
                mock_service.is_active = True
                mock_service_repo.get_all_services = AsyncMock(return_value=[mock_service])

                # Test
                success, error = await booking_service.create_booking(
                    "2026-02-20", "10:00", user_id=123, username="testuser"
                )

                # Assertions
                assert success is True
                assert error == "success"
                mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_booking_slot_taken(self, booking_service):
        """Слот уже занят"""
        with patch("services.booking_service.db_adapter") as mock_db:
            # Mock connection
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=0)  # user_count OK
            
            # Mock existing booking (slot taken)
            mock_conn.fetch = AsyncMock(return_value=[
                {"time": "10:00", "duration": 60}
            ])
            
            mock_conn.transaction = MagicMock(return_value=AsyncMock().__aenter__())
            
            mock_db.acquire = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock()
            ))

            # Mock service
            with patch("database.repositories.service_repository.ServiceRepository") as mock_service_repo:
                mock_service = MagicMock()
                mock_service.id = 1
                mock_service.duration_minutes = 60
                mock_service.is_active = True
                mock_service_repo.get_all_services = AsyncMock(return_value=[mock_service])

                # Test
                success, error = await booking_service.create_booking(
                    "2026-02-20", "10:00", user_id=123, username="testuser"
                )

                # Assertions
                assert success is False
                assert error == "slot_taken"

    @pytest.mark.asyncio
    async def test_create_booking_limit_exceeded(self, booking_service):
        """Превышен лимит записей пользователя"""
        with patch("services.booking_service.db_adapter") as mock_db, \
             patch("services.booking_service.MAX_BOOKINGS_PER_USER", 3):
            
            # Mock connection
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=3)  # user already has 3 bookings
            mock_conn.transaction = MagicMock(return_value=AsyncMock().__aenter__())
            
            mock_db.acquire = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock()
            ))

            # Mock service
            with patch("database.repositories.service_repository.ServiceRepository") as mock_service_repo:
                mock_service = MagicMock()
                mock_service.id = 1
                mock_service.duration_minutes = 60
                mock_service.is_active = True
                mock_service_repo.get_all_services = AsyncMock(return_value=[mock_service])

                # Test
                success, error = await booking_service.create_booking(
                    "2026-02-20", "10:00", user_id=123, username="testuser"
                )

                # Assertions
                assert success is False
                assert error == "limit_exceeded"

    @pytest.mark.asyncio
    async def test_create_booking_no_services(self, booking_service):
        """Нет доступных услуг"""
        with patch("database.repositories.service_repository.ServiceRepository") as mock_service_repo:
            mock_service_repo.get_all_services = AsyncMock(return_value=[])  # No services

            # Test
            success, error = await booking_service.create_booking(
                "2026-02-20", "10:00", user_id=123, username="testuser"
            )

            # Assertions
            assert success is False
            assert error == "no_services"

    @pytest.mark.asyncio
    async def test_create_booking_timeout(self, booking_service):
        """Таймаут транзакции"""
        with patch("services.booking_service.db_adapter") as mock_db, \
             patch("services.booking_service.asyncio.timeout") as mock_timeout:
            
            # Mock timeout error
            mock_timeout.side_effect = asyncio.TimeoutError()

            # Mock service
            with patch("database.repositories.service_repository.ServiceRepository") as mock_service_repo:
                mock_service = MagicMock()
                mock_service.id = 1
                mock_service.duration_minutes = 60
                mock_service.is_active = True
                mock_service_repo.get_all_services = AsyncMock(return_value=[mock_service])

                # Test
                success, error = await booking_service.create_booking(
                    "2026-02-20", "10:00", user_id=123, username="testuser"
                )

                # Assertions
                assert success is False
                assert error == "timeout_error"


class TestRescheduleBooking:
    """Тесты переноса бронирования"""

    @pytest.mark.asyncio
    async def test_reschedule_booking_success(self, booking_service):
        """Успешный перенос записи"""
        with patch("services.booking_service.db_adapter") as mock_db, \
             patch("services.booking_service.BookingHistoryRepository") as mock_history, \
             patch("services.booking_service.Database") as mock_database:
            
            # Mock connection
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={
                "id": 1,
                "duration_minutes": 60,
                "service_id": 1
            })
            mock_conn.fetch = AsyncMock(return_value=[])  # new slot is free
            mock_conn.execute = AsyncMock()
            mock_conn.transaction = MagicMock(return_value=AsyncMock().__aenter__())
            
            mock_db.acquire = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock()
            ))
            
            mock_history.record_reschedule = AsyncMock()
            mock_database.log_event = AsyncMock()

            # Test
            success = await booking_service.reschedule_booking(
                booking_id=1,
                old_date_str="2026-02-20",
                old_time_str="10:00",
                new_date_str="2026-02-21",
                new_time_str="14:00",
                user_id=123,
                username="testuser"
            )

            # Assertions
            assert success is True
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_reschedule_booking_not_found(self, booking_service):
        """Запись не найдена"""
        with patch("services.booking_service.db_adapter") as mock_db:
            # Mock connection
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value=None)  # booking not found
            mock_conn.transaction = MagicMock(return_value=AsyncMock().__aenter__())
            
            mock_db.acquire = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock()
            ))

            # Test
            success = await booking_service.reschedule_booking(
                booking_id=999,
                old_date_str="2026-02-20",
                old_time_str="10:00",
                new_date_str="2026-02-21",
                new_time_str="14:00",
                user_id=123,
                username="testuser"
            )

            # Assertions
            assert success is False

    @pytest.mark.asyncio
    async def test_reschedule_booking_new_slot_taken(self, booking_service):
        """Новый слот занят"""
        with patch("services.booking_service.db_adapter") as mock_db:
            # Mock connection
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={
                "id": 1,
                "duration_minutes": 60,
                "service_id": 1
            })
            # New slot has existing booking
            mock_conn.fetch = AsyncMock(return_value=[
                {"time": "14:00", "duration": 60}
            ])
            mock_conn.transaction = MagicMock(return_value=AsyncMock().__aenter__())
            
            mock_db.acquire = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock()
            ))

            # Test
            success = await booking_service.reschedule_booking(
                booking_id=1,
                old_date_str="2026-02-20",
                old_time_str="10:00",
                new_date_str="2026-02-21",
                new_time_str="14:00",
                user_id=123,
                username="testuser"
            )

            # Assertions
            assert success is False


class TestCancelBooking:
    """Тесты отмены бронирования"""

    @pytest.mark.asyncio
    async def test_cancel_booking_success(self, booking_service):
        """Успешная отмена записи"""
        with patch("services.booking_service.db_adapter") as mock_db, \
             patch("services.booking_service.BookingHistoryRepository") as mock_history, \
             patch("services.booking_service.Database") as mock_database:
            
            # Mock fetchrow
            mock_db.fetchrow = AsyncMock(return_value={
                "id": 1,
                "service_id": 1
            })
            
            # Mock execute
            mock_db.execute = AsyncMock()
            
            mock_history.record_cancel = AsyncMock()
            mock_database.log_event = AsyncMock()

            # Test
            success, booking_id = await booking_service.cancel_booking(
                date_str="2026-02-20",
                time_str="10:00",
                user_id=123
            )

            # Assertions
            assert success is True
            assert booking_id == 1
            mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_booking_not_found(self, booking_service):
        """Запись не найдена"""
        with patch("services.booking_service.db_adapter") as mock_db:
            # Mock fetchrow - booking not found
            mock_db.fetchrow = AsyncMock(return_value=None)

            # Test
            success, booking_id = await booking_service.cancel_booking(
                date_str="2026-02-20",
                time_str="10:00",
                user_id=123
            )

            # Assertions
            assert success is False
            assert booking_id == 0


class TestSlotAvailability:
    """Тесты проверки доступности слота"""

    @pytest.mark.asyncio
    async def test_slot_free(self, booking_service):
        """Слот свободен"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [],  # no bookings
            []   # no blocked
        ])

        result = await booking_service._check_slot_availability_in_transaction(
            mock_conn, "2026-02-20", "10:00", 60
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_slot_blocked(self, booking_service):
        """Слот заблокирован"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [],  # no bookings
            [{"time": "10:00"}]  # blocked
        ])

        result = await booking_service._check_slot_availability_in_transaction(
            mock_conn, "2026-02-20", "10:00", 60
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_slot_overlap_exact(self, booking_service):
        """Точное пересечение слотов"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [{"time": "10:00", "duration": 60}],  # existing booking
            []  # no blocked
        ])

        result = await booking_service._check_slot_availability_in_transaction(
            mock_conn, "2026-02-20", "10:00", 60
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_slot_overlap_partial_start(self, booking_service):
        """Частичное пересечение (начало)"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [{"time": "09:30", "duration": 60}],  # 9:30-10:30
            []  # no blocked
        ])

        # Пытаемся забронировать 10:00-11:00
        result = await booking_service._check_slot_availability_in_transaction(
            mock_conn, "2026-02-20", "10:00", 60
        )

        # Должно быть занято, так как 9:30-10:30 пересекается с 10:00-11:00
        assert result is False

    @pytest.mark.asyncio
    async def test_slot_overlap_partial_end(self, booking_service):
        """Частичное пересечение (конец)"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [{"time": "11:00", "duration": 60}],  # 11:00-12:00
            []  # no blocked
        ])

        # Пытаемся забронировать 10:00-11:30 (90 минут)
        result = await booking_service._check_slot_availability_in_transaction(
            mock_conn, "2026-02-20", "10:00", 90
        )

        # Должно быть занято
        assert result is False

    @pytest.mark.asyncio
    async def test_slot_no_overlap_adjacent(self, booking_service):
        """Нет пересечения - соседние слоты"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [{"time": "11:00", "duration": 60}],  # 11:00-12:00
            []  # no blocked
        ])

        # Пытаемся забронировать 10:00-11:00
        result = await booking_service._check_slot_availability_in_transaction(
            mock_conn, "2026-02-20", "10:00", 60
        )

        # Должно быть свободно
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
