"""Repository для управления календарными блокировками и гибким расписанием"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import aiosqlite

from config import DATABASE_PATH


class CalendarRepository:
    """Репозиторий для работы с календарем и гибким расписанием"""

    @staticmethod
    async def init_calendar_tables():
        """Инициализация таблиц для гибкого расписания и блокировок диапазонов"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Таблица гибкого расписания по дням недели
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS work_schedule (
                    weekday INTEGER PRIMARY KEY,  -- 0=Пн, 6=Вс
                    is_working INTEGER DEFAULT 1,  -- 0=выходной, 1=рабочий
                    shift1_start TEXT,  -- HH:MM
                    shift1_end TEXT,    -- HH:MM
                    shift2_start TEXT,  -- HH:MM (опционально)
                    shift2_end TEXT,    -- HH:MM (опционально)
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Таблица блокировок диапазонов дат
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS blocked_date_ranges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_date TEXT NOT NULL,  -- YYYY-MM-DD
                    end_date TEXT NOT NULL,    -- YYYY-MM-DD
                    start_time TEXT,           -- HH:MM (null = весь день)
                    end_time TEXT,             -- HH:MM (null = весь день)
                    reason TEXT,
                    blocked_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_recurring INTEGER DEFAULT 0  -- 1=повторяющаяся блокировка
                )
                """
            )

            # Индексы
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_blocked_ranges_dates ON blocked_date_ranges(start_date, end_date)"
            )

            await db.commit()
            logging.info("Calendar tables initialized")

    @staticmethod
    async def get_week_schedule() -> Dict[int, Dict]:
        """
        Получить расписание на неделю

        Returns:
            Dict[weekday, {is_working, shift1_start, shift1_end, shift2_start, shift2_end}]
        """
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT weekday, is_working, shift1_start, shift1_end, shift2_start, shift2_end FROM work_schedule"
            ) as cursor:
                rows = await cursor.fetchall()

                schedule = {}
                for row in rows:
                    schedule[row[0]] = {
                        "is_working": bool(row[1]),
                        "shift1_start": row[2],
                        "shift1_end": row[3],
                        "shift2_start": row[4],
                        "shift2_end": row[5],
                    }

                return schedule

    @staticmethod
    async def set_weekday_schedule(
        weekday: int,
        is_working: bool,
        shift1_start: str,
        shift1_end: str,
        shift2_start: Optional[str] = None,
        shift2_end: Optional[str] = None,
    ) -> bool:
        """
        Установить расписание для дня недели

        Args:
            weekday: 0-6 (0=Понедельник)
            is_working: Рабочий ли день
            shift1_start: Начало первой смены (HH:MM)
            shift1_end: Конец первой смены (HH:MM)
            shift2_start: Начало второй смены (опционально)
            shift2_end: Конец второй смены (опционально)
        """
        if not (0 <= weekday <= 6):
            return False

        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO work_schedule 
                    (weekday, is_working, shift1_start, shift1_end, shift2_start, shift2_end, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        weekday,
                        int(is_working),
                        shift1_start,
                        shift1_end,
                        shift2_start,
                        shift2_end,
                    ),
                )
                await db.commit()
                return True
        except Exception as e:
            logging.error(f"Error setting weekday schedule: {e}")
            return False

    @staticmethod
    async def block_date_range(
        start_date: str,
        end_date: str,
        admin_id: int,
        reason: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        is_recurring: bool = False,
    ) -> int:
        """
        Заблокировать диапазон дат

        Args:
            start_date: Дата начала (YYYY-MM-DD)
            end_date: Дата окончания (YYYY-MM-DD)
            admin_id: ID администратора
            reason: Причина блокировки
            start_time: Начало времени блокировки (HH:MM, None = весь день)
            end_time: Конец времени блокировки (HH:MM, None = весь день)
            is_recurring: Повторяющаяся ли блокировка

        Returns:
            ID созданной записи или 0 при ошибке
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute(
                    """
                    INSERT INTO blocked_date_ranges 
                    (start_date, end_date, start_time, end_time, reason, blocked_by, is_recurring)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (start_date, end_date, start_time, end_time, reason, admin_id, int(is_recurring)),
                )
                await db.commit()
                return cursor.lastrowid
        except Exception as e:
            logging.error(f"Error blocking date range: {e}")
            return 0

    @staticmethod
    async def unblock_date_range(block_id: int) -> bool:
        """Разблокировать диапазон дат"""
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute("DELETE FROM blocked_date_ranges WHERE id=?", (block_id,))
                await db.commit()
                return True
        except Exception as e:
            logging.error(f"Error unblocking date range: {e}")
            return False

    @staticmethod
    async def get_blocked_ranges(
        start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Tuple]:
        """
        Получить заблокированные диапазоны

        Args:
            start_date: Фильтр с даты (YYYY-MM-DD)
            end_date: Фильтр по дату (YYYY-MM-DD)

        Returns:
            List[Tuple[id, start_date, end_date, start_time, end_time, reason, blocked_by, created_at, is_recurring]]
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                if start_date and end_date:
                    query = """
                        SELECT id, start_date, end_date, start_time, end_time, reason, blocked_by, created_at, is_recurring
                        FROM blocked_date_ranges
                        WHERE (start_date <= ? AND end_date >= ?)
                        ORDER BY start_date
                    """
                    params = (end_date, start_date)
                else:
                    query = """
                        SELECT id, start_date, end_date, start_time, end_time, reason, blocked_by, created_at, is_recurring
                        FROM blocked_date_ranges
                        ORDER BY start_date
                    """
                    params = ()

                async with db.execute(query, params) as cursor:
                    return await cursor.fetchall()
        except Exception as e:
            logging.error(f"Error getting blocked ranges: {e}")
            return []

    @staticmethod
    async def is_date_blocked(
        check_date: str, check_time: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить заблокирована ли дата/время

        Args:
            check_date: Дата для проверки (YYYY-MM-DD)
            check_time: Время для проверки (HH:MM)

        Returns:
            Tuple[is_blocked, reason]
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                # Проверяем полнодневные блокировки
                async with db.execute(
                    """
                    SELECT reason FROM blocked_date_ranges
                    WHERE start_date <= ? AND end_date >= ?
                    AND start_time IS NULL AND end_time IS NULL
                    LIMIT 1
                    """,
                    (check_date, check_date),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return True, row[0]

                # Если указано время, проверяем временные блокировки
                if check_time:
                    async with db.execute(
                        """
                        SELECT reason FROM blocked_date_ranges
                        WHERE start_date <= ? AND end_date >= ?
                        AND start_time IS NOT NULL AND end_time IS NOT NULL
                        AND start_time <= ? AND end_time >= ?
                        LIMIT 1
                        """,
                        (check_date, check_date, check_time, check_time),
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            return True, row[0]

                return False, None
        except Exception as e:
            logging.error(f"Error checking if date blocked: {e}")
            return False, None

    @staticmethod
    async def get_working_hours_for_date(check_date: str) -> Optional[Dict]:
        """
        Получить рабочие часы для конкретной даты с учетом дня недели

        Args:
            check_date: Дата (YYYY-MM-DD)

        Returns:
            Dict с расписанием или None если выходной
        """
        try:
            # Определяем день недели (0=Пн)
            date_obj = datetime.strptime(check_date, "%Y-%m-%d")
            weekday = date_obj.weekday()

            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.execute(
                    """
                    SELECT is_working, shift1_start, shift1_end, shift2_start, shift2_end
                    FROM work_schedule WHERE weekday=?
                    """,
                    (weekday,),
                ) as cursor:
                    row = await cursor.fetchone()

                    if not row or not row[0]:
                        return None  # Выходной день

                    return {
                        "shift1_start": row[1],
                        "shift1_end": row[2],
                        "shift2_start": row[3],
                        "shift2_end": row[4],
                    }
        except Exception as e:
            logging.error(f"Error getting working hours for date: {e}")
            return None
