"""Клавиатуры для администратора"""

import calendar
from datetime import datetime

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import CALENDAR_MAX_MONTHS_AHEAD, DAY_NAMES_SHORT, MONTH_NAMES
from database.queries import Database
from utils.helpers import now_local

ADMIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Dashboard"), KeyboardButton(text="💡 Рекомендации")],
        [KeyboardButton(text="📅 Расписание"), KeyboardButton(text="👥 Клиенты")],
        [
            KeyboardButton(text="⚙️ Управление услугами"),
            KeyboardButton(text="⚡ Массовые операции"),
        ],
        [
            KeyboardButton(text="👥 Администраторы"),
            KeyboardButton(text="📝 Массовое редактирование"),
        ],
        [
            KeyboardButton(text="✏️ Редактор полей"),
            KeyboardButton(text="📊 Экспорт данных"),
        ],
        [
            KeyboardButton(text="📝 Редактор текстов"),  # ✅ NEW: i18n text editor
            KeyboardButton(text="⚙️ Настройки"),
        ],
        [
            KeyboardButton(text="🔙 Выход из админки"),
        ],
    ],
    resize_keyboard=True,
)


async def create_admin_calendar(
    year: int, month: int, callback_prefix: str = "admin_date", allow_past: bool = True
) -> InlineKeyboardMarkup:
    """✨ Календарь для админа с навигацией и индикаторами загрузки

    Args:
        year: Год
        month: Месяц (1-12)
        callback_prefix: Префикс для callback_data (например 'block_date', 'mass_edit_date')
        allow_past: Разрешить выбор прошедших дат (по умолчанию True для админа)

    Returns:
        InlineKeyboardMarkup с календарем
    """
    keyboard = []
    today = now_local()

    # Навигация
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    # ✅ Админ может листать в прошлое (для аналитики или разблокировки)
    can_go_prev = allow_past or prev_year > today.year or (
        prev_year == today.year and prev_month >= today.month
    )

    # Ограничение: максимум N месяцев вперёд
    max_year = today.year
    max_month = today.month + CALENDAR_MAX_MONTHS_AHEAD
    if max_month > 12:
        max_year += max_month // 12
        max_month = max_month % 12
        if max_month == 0:
            max_month = 12
            max_year -= 1

    can_go_next = next_year < max_year or (next_year == max_year and next_month <= max_month)

    # Кнопки навигации
    prev_button = (
        InlineKeyboardButton(
            text="◀️", callback_data=f"{callback_prefix}_cal:{prev_year}-{prev_month:02d}"
        )
        if can_go_prev
        else InlineKeyboardButton(text=" ", callback_data="ignore")
    )

    next_button = (
        InlineKeyboardButton(
            text="▶️", callback_data=f"{callback_prefix}_cal:{next_year}-{next_month:02d}"
        )
        if can_go_next
        else InlineKeyboardButton(text=" ", callback_data="ignore")
    )

    keyboard.append(
        [
            prev_button,
            InlineKeyboardButton(text=f"{MONTH_NAMES[month-1]} {year}", callback_data="ignore"),
            next_button,
        ]
    )

    # Дни недели
    keyboard.append(
        [InlineKeyboardButton(text=day, callback_data="ignore") for day in DAY_NAMES_SHORT]
    )

    # ✅ Получаем все статусы одним запросом (ОПТИМИЗАЦИЯ!)
    month_statuses = await Database.get_month_statuses(year, month)

    # Дни месяца
    cal = calendar.monthcalendar(year, month)
    today_date = today.date()

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date = datetime(year, month, day).date()
                date_str = date.strftime("%Y-%m-%d")

                # ✅ Админ может выбирать прошедшие даты
                if not allow_past and date < today_date:
                    row.append(InlineKeyboardButton(text="⚫", callback_data="ignore"))
                else:
                    # Используем закэшированный статус
                    status = month_statuses.get(date_str, "🟢")

                    # ✅ Все дни кликабельны для админа (даже полностью занятые)
                    row.append(
                        InlineKeyboardButton(
                            text=f"{day}{status}", callback_data=f"{callback_prefix}:{date_str}"
                        )
                    )
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"{callback_prefix}_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
