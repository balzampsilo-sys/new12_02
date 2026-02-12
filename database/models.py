"""Модели данных"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class Service:
    """Модель услуги/процедуры"""

    id: Optional[int]
    name: str
    description: Optional[str]
    duration_minutes: int
    price: Optional[str]
    color: str = "#4CAF50"
    is_active: bool = True
    display_order: int = 0
    slot_interval_minutes: int = 60  # ✅ NEW: Интервал между слотами (30/60/90/120)
    created_at: Optional[datetime] = None

    def get_duration_display(self) -> str:
        """Отображение длительности в читаемом формате"""
        hours = self.duration_minutes // 60
        minutes = self.duration_minutes % 60

        if hours and minutes:
            return f"{hours} ч {minutes} мин"
        elif hours:
            return f"{hours} ч"
        else:
            return f"{minutes} мин"

    def get_slot_interval_display(self) -> str:
        """Отображение интервала слотов"""
        if self.slot_interval_minutes >= 60:
            hours = self.slot_interval_minutes // 60
            minutes = self.slot_interval_minutes % 60
            if minutes:
                return f"{hours} ч {minutes} мин"
            return f"{hours} ч"
        return f"{self.slot_interval_minutes} мин"

    def validate_slot_interval(self) -> bool:
        """Проверка что интервал слотов валидный"""
        return self.slot_interval_minutes in [30, 60, 90, 120]


@dataclass
class ScheduleSettings:
    """Настройки расписания"""

    work_hours_start: int = 9
    work_hours_end: int = 19
    max_bookings_per_day: int = 8
    updated_at: Optional[datetime] = None

    def get_available_hours(self) -> list[int]:
        """Получить список доступных часов"""
        return list(range(self.work_hours_start, self.work_hours_end))


@dataclass
class Booking:
    """Расширенная модель бронирования"""

    id: Optional[int]
    date: str
    time: str
    user_id: int
    username: Optional[str]
    service_id: Optional[int]
    duration_minutes: int = 60
    created_at: Optional[datetime] = None
    version: int = 1

    # Расширенные поля (загружаются из JOIN)
    service_name: Optional[str] = None
    service_color: Optional[str] = None
    service_price: Optional[str] = None
