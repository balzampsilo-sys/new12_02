"""Unit tests for AdminRepository"""

import asyncio
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite

from database.repositories.admin_repository import AdminRepository


class TestAdminRepository(unittest.TestCase):
    """Тесты для AdminRepository"""

    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        # Создаем временную БД
        cls.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        cls.test_db_path = cls.temp_db.name
        cls.temp_db.close()

    @classmethod
    def tearDownClass(cls):
        """Cleanup after all tests"""
        # Удаляем тестовую БД
        if os.path.exists(cls.test_db_path):
            os.unlink(cls.test_db_path)

    def setUp(self):
        """Setup before each test"""
        # Переопределяем DATABASE_PATH
        self.original_db_path = os.environ.get("DATABASE_PATH")
        os.environ["DATABASE_PATH"] = self.test_db_path

        # Создаем таблицу
        asyncio.run(self._create_table())

    def tearDown(self):
        """Cleanup after each test"""
        # Восстанавливаем DATABASE_PATH
        if self.original_db_path:
            os.environ["DATABASE_PATH"] = self.original_db_path
        else:
            del os.environ["DATABASE_PATH"]

        # Очищаем БД
        asyncio.run(self._clear_table())

    async def _create_table(self):
        """Create admins table"""
        async with aiosqlite.connect(self.test_db_path) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS admins
                (user_id INTEGER PRIMARY KEY,
                username TEXT,
                added_by INTEGER,
                added_at TEXT NOT NULL)"""
            )
            await db.commit()

    async def _clear_table(self):
        """Clear admins table"""
        async with aiosqlite.connect(self.test_db_path) as db:
            await db.execute("DELETE FROM admins")
            await db.commit()

    # === ТЕСТЫ ===

    def test_add_admin_success(self):
        """Тест: Успешное добавление админа"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            result = asyncio.run(
                AdminRepository.add_admin(
                    user_id=12345,
                    username="testuser",
                    added_by=99999
                )
            )

            self.assertTrue(result)

            # Проверяем что добавлен
            is_admin = asyncio.run(AdminRepository.is_admin(12345))
            self.assertTrue(is_admin)

    def test_add_admin_duplicate(self):
        """Тест: Дублирование админа (должно игнорироваться)"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            # Добавляем первый раз
            asyncio.run(AdminRepository.add_admin(12345, "user1", 99999))

            # Пытаемся добавить еще раз
            result = asyncio.run(AdminRepository.add_admin(12345, "user1", 99999))

            # Должно вернуть True (из-за INSERT OR IGNORE)
            self.assertTrue(result)

            # Количество = 1
            count = asyncio.run(AdminRepository.get_admin_count())
            self.assertEqual(count, 1)

    def test_remove_admin_success(self):
        """Тест: Успешное удаление админа"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            # Добавляем
            asyncio.run(AdminRepository.add_admin(12345, "user", 99999))

            # Удаляем
            result = asyncio.run(AdminRepository.remove_admin(12345))

            self.assertTrue(result)

            # Проверяем что удален
            is_admin = asyncio.run(AdminRepository.is_admin(12345))
            self.assertFalse(is_admin)

    def test_remove_admin_not_found(self):
        """Тест: Удаление несуществующего админа"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            result = asyncio.run(AdminRepository.remove_admin(99999))

            # Должно вернуть False
            self.assertFalse(result)

    def test_get_all_admins(self):
        """Тест: Получение всех админов"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            # Добавляем несколько
            asyncio.run(AdminRepository.add_admin(111, "user1", 999))
            asyncio.run(AdminRepository.add_admin(222, "user2", 999))
            asyncio.run(AdminRepository.add_admin(333, "user3", 999))

            admins = asyncio.run(AdminRepository.get_all_admins())

            self.assertEqual(len(admins), 3)
            self.assertEqual(admins[0][0], 111)  # user_id
            self.assertEqual(admins[1][0], 222)
            self.assertEqual(admins[2][0], 333)

    def test_get_all_admins_empty(self):
        """Тест: Получение пустого списка"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            admins = asyncio.run(AdminRepository.get_all_admins())

            self.assertEqual(len(admins), 0)

    def test_is_admin_true(self):
        """Тест: Проверка существующего админа"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            asyncio.run(AdminRepository.add_admin(12345, "user", 999))

            is_admin = asyncio.run(AdminRepository.is_admin(12345))

            self.assertTrue(is_admin)

    def test_is_admin_false(self):
        """Тест: Проверка несуществующего админа"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            is_admin = asyncio.run(AdminRepository.is_admin(99999))

            self.assertFalse(is_admin)

    def test_get_admin_count(self):
        """Тест: Подсчет админов"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            # Пусто
            count = asyncio.run(AdminRepository.get_admin_count())
            self.assertEqual(count, 0)

            # Добавляем 2
            asyncio.run(AdminRepository.add_admin(111, "user1", 999))
            asyncio.run(AdminRepository.add_admin(222, "user2", 999))

            count = asyncio.run(AdminRepository.get_admin_count())
            self.assertEqual(count, 2)

    def test_get_admin_info(self):
        """Тест: Получение информации об админе"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            asyncio.run(AdminRepository.add_admin(12345, "testuser", 99999))

            info = asyncio.run(AdminRepository.get_admin_info(12345))

            self.assertIsNotNone(info)
            self.assertEqual(info[0], "testuser")  # username
            self.assertEqual(info[1], 99999)  # added_by

    def test_get_admin_info_not_found(self):
        """Тест: Информация о несуществующем админе"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            info = asyncio.run(AdminRepository.get_admin_info(99999))

            self.assertIsNone(info)

    def test_add_admin_without_username(self):
        """Тест: Добавление админа без username"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            result = asyncio.run(
                AdminRepository.add_admin(
                    user_id=12345,
                    username=None,
                    added_by=99999
                )
            )

            self.assertTrue(result)

            info = asyncio.run(AdminRepository.get_admin_info(12345))
            self.assertIsNone(info[0])  # username is None

    def test_concurrency_safety(self):
        """Тест: Безопасность при конкурентных запросах"""
        with patch("database.repositories.admin_repository.DATABASE_PATH", self.test_db_path):
            async def add_multiple():
                tasks = [
                    AdminRepository.add_admin(i, f"user{i}", 999)
                    for i in range(100, 110)
                ]
                await asyncio.gather(*tasks)

            asyncio.run(add_multiple())

            count = asyncio.run(AdminRepository.get_admin_count())
            self.assertEqual(count, 10)


if __name__ == "__main__":
    unittest.main()
