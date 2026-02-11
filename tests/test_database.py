"""Тесты для работы с базой данных"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta

import aiosqlite
import pytest


class TestDatabase:
    """Критичные тесты для БД"""

    @pytest.fixture
    async def temp_db(self):
        """Создает временную БД для тестов"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        db_path = temp_file.name
        temp_file.close()

        # Инициализация тестовой БД
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS bookings
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, time TEXT, user_id INTEGER, username TEXT,
                created_at TEXT, service_id INTEGER DEFAULT 1,
                duration_minutes INTEGER DEFAULT 60,
                UNIQUE(date, time))"""
            )
            await db.execute(
                """CREATE TABLE IF NOT EXISTS services
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER DEFAULT 60,
                price TEXT,
                display_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1)"""
            )
            await db.execute(
                """INSERT INTO services (name, duration_minutes, price, is_active)
                VALUES ('Тестовая услуга', 60, '1000 ₽', 1)"""
            )
            await db.commit()

        yield db_path

        # Удаление временной БД
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_database_init(self, temp_db):
        """Тест инициализации БД"""
        assert os.path.exists(temp_db)
        
        async with aiosqlite.connect(temp_db) as db:
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()
            table_names = [t[0] for t in tables]
            
            assert "bookings" in table_names
            assert "services" in table_names

    @pytest.mark.asyncio
    async def test_slot_booking_success(self, temp_db):
        """Тест успешного бронирования слота"""
        date_str = "2026-03-15"
        time_str = "14:00"
        user_id = 123456
        
        async with aiosqlite.connect(temp_db) as db:
            await db.execute(
                """INSERT INTO bookings (date, time, user_id, username, created_at, service_id)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (date_str, time_str, user_id, "test_user", datetime.now().isoformat(), 1)
            )
            await db.commit()
            
            cursor = await db.execute(
                "SELECT * FROM bookings WHERE date=? AND time=?",
                (date_str, time_str)
            )
            booking = await cursor.fetchone()
            
            assert booking is not None
            assert booking[3] == user_id

    @pytest.mark.asyncio
    async def test_concurrent_bookings_same_slot(self, temp_db):
        """КРИТИЧНЫЙ ТЕСТ: Два пользователя пытаются забронировать один слот одновременно"""
        date_str = "2026-03-15"
        time_str = "15:00"
        user1_id = 111111
        user2_id = 222222
        
        async def book_slot(db_path: str, user_id: int, username: str):
            """Функция бронирования для конкурентного выполнения"""
            try:
                async with aiosqlite.connect(db_path) as db:
                    # Начинаем транзакцию
                    await db.execute("BEGIN EXCLUSIVE")
                    
                    # Проверяем доступность слота
                    cursor = await db.execute(
                        "SELECT id FROM bookings WHERE date=? AND time=?",
                        (date_str, time_str)
                    )
                    existing = await cursor.fetchone()
                    
                    if existing:
                        await db.rollback()
                        return False
                    
                    # Небольшая задержка для имитации реальной ситуации
                    await asyncio.sleep(0.01)
                    
                    # Бронируем
                    await db.execute(
                        """INSERT INTO bookings (date, time, user_id, username, created_at, service_id)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (date_str, time_str, user_id, username, datetime.now().isoformat(), 1)
                    )
                    await db.commit()
                    return True
            except aiosqlite.IntegrityError:
                # UNIQUE constraint violation
                return False
            except Exception:
                return False
        
        # Запускаем два бронирования одновременно
        results = await asyncio.gather(
            book_slot(temp_db, user1_id, "user1"),
            book_slot(temp_db, user2_id, "user2"),
            return_exceptions=True
        )
        
        # Проверяем: только одно бронирование должно пройти
        successful_bookings = sum(1 for r in results if r is True)
        assert successful_bookings == 1, f"Expected 1 successful booking, got {successful_bookings}"
        
        # Проверяем в БД
        async with aiosqlite.connect(temp_db) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM bookings WHERE date=? AND time=?",
                (date_str, time_str)
            )
            count = await cursor.fetchone()
            assert count[0] == 1, "Should have exactly 1 booking in the database"

    @pytest.mark.asyncio
    async def test_slot_overlap_different_durations(self, temp_db):
        """Тест проверки пересечения слотов с разной длительностью"""
        date_str = "2026-03-15"
        
        async with aiosqlite.connect(temp_db) as db:
            # Бронируем слот 14:00-15:30 (90 минут)
            await db.execute(
                """INSERT INTO bookings (date, time, user_id, username, created_at, service_id, duration_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (date_str, "14:00", 111111, "user1", datetime.now().isoformat(), 1, 90)
            )
            await db.commit()
            
            # Проверяем, что слот 14:30 занят (пересекается)
            # Нужна логика проверки overlap
            cursor = await db.execute(
                "SELECT * FROM bookings WHERE date=? AND time<=? ORDER BY time",
                (date_str, "14:30")
            )
            bookings = await cursor.fetchall()
            
            # Проверяем пересечение
            if bookings:
                booking = bookings[0]
                booking_time = datetime.strptime(f"{date_str} {booking[2]}", "%Y-%m-%d %H:%M")
                booking_end = booking_time + timedelta(minutes=booking[7])  # duration_minutes
                
                check_time = datetime.strptime(f"{date_str} 14:30", "%Y-%m-%d %H:%M")
                
                overlaps = booking_time <= check_time < booking_end
                assert overlaps, "14:30 should overlap with 14:00-15:30 booking"

    @pytest.mark.asyncio
    async def test_multiple_bookings_per_user_limit(self, temp_db):
        """Тест лимита бронирований на одного пользователя"""
        user_id = 123456
        max_bookings = 3
        
        async with aiosqlite.connect(temp_db) as db:
            # Создаем 3 бронирования
            for i in range(max_bookings):
                await db.execute(
                    """INSERT INTO bookings (date, time, user_id, username, created_at, service_id)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"2026-03-{15+i}", "14:00", user_id, "test_user", datetime.now().isoformat(), 1)
                )
            await db.commit()
            
            # Проверяем количество
            cursor = await db.execute(
                "SELECT COUNT(*) FROM bookings WHERE user_id=?",
                (user_id,)
            )
            count = await cursor.fetchone()
            assert count[0] == max_bookings

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, temp_db):
        """Тест отката транзакции при ошибке"""
        date_str = "2026-03-15"
        time_str = "16:00"
        
        async with aiosqlite.connect(temp_db) as db:
            try:
                await db.execute("BEGIN")
                
                # Успешная вставка
                await db.execute(
                    """INSERT INTO bookings (date, time, user_id, username, created_at, service_id)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (date_str, time_str, 123, "user1", datetime.now().isoformat(), 1)
                )
                
                # Попытка вставить дубликат (должна упасть)
                await db.execute(
                    """INSERT INTO bookings (date, time, user_id, username, created_at, service_id)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (date_str, time_str, 456, "user2", datetime.now().isoformat(), 1)
                )
                
                await db.commit()
            except aiosqlite.IntegrityError:
                await db.rollback()
            
            # Проверяем, что ничего не записалось
            cursor = await db.execute(
                "SELECT COUNT(*) FROM bookings WHERE date=? AND time=?",
                (date_str, time_str)
            )
            count = await cursor.fetchone()
            assert count[0] == 0, "Transaction should have been rolled back"

    @pytest.mark.asyncio
    async def test_service_activation_deactivation(self, temp_db):
        """Тест активации/деактивации услуг"""
        async with aiosqlite.connect(temp_db) as db:
            # Создаем услугу
            await db.execute(
                """INSERT INTO services (name, duration_minutes, price, is_active)
                VALUES (?, ?, ?, ?)""",
                ("Новая услуга", 60, "2000 ₽", 1)
            )
            await db.commit()
            
            # Деактивируем
            await db.execute(
                "UPDATE services SET is_active=0 WHERE name=?",
                ("Новая услуга",)
            )
            await db.commit()
            
            # Проверяем
            cursor = await db.execute(
                "SELECT is_active FROM services WHERE name=?",
                ("Новая услуга",)
            )
            result = await cursor.fetchone()
            assert result[0] == 0, "Service should be deactivated"

    @pytest.mark.asyncio
    async def test_booking_with_invalid_service(self, temp_db):
        """Тест бронирования с несуществующей услугой"""
        date_str = "2026-03-15"
        time_str = "17:00"
        invalid_service_id = 9999
        
        async with aiosqlite.connect(temp_db) as db:
            # Попытка забронировать с несуществующим service_id
            # В реальной БД должен быть FOREIGN KEY constraint
            await db.execute(
                """INSERT INTO bookings (date, time, user_id, username, created_at, service_id)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (date_str, time_str, 123, "user1", datetime.now().isoformat(), invalid_service_id)
            )
            await db.commit()
            
            # В текущей схеме это пройдет, но нужно добавить FK constraint
            cursor = await db.execute(
                "SELECT service_id FROM bookings WHERE date=? AND time=?",
                (date_str, time_str)
            )
            result = await cursor.fetchone()
            assert result[0] == invalid_service_id
            
            # TODO: Добавить FOREIGN KEY constraint в production


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
