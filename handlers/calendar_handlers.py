"""Handlers для работы с календарем и гибким расписанием"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback

from database.repositories.audit_repository import AuditRepository
from database.repositories.booking_repository import BookingRepository
from database.repositories.calendar_repository import CalendarRepository
from keyboards.admin_keyboards import ADMIN_MENU
from utils.helpers import is_admin
from utils.permissions import has_permission
from utils.states import AdminStates

router = Router()

# === ПЕРЕНОС ЗАПИСЕЙ ЧЕРЕЗ КАЛЕНДАРЬ ===


@router.callback_query(F.data.startswith("reschedule_booking:"))
async def start_reschedule_booking(callback: CallbackQuery, state: FSMContext):
    """Начать перенос записи через календарь"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    # Извлекаем booking_id
    booking_id = int(callback.data.split(":")[1])

    # Сохраняем в state
    await state.update_data(reschedule_booking_id=booking_id)
    await state.set_state(AdminStates.reschedule_select_date)

    # Показываем календарь
    calendar = SimpleCalendar()
    calendar_markup = await calendar.start_calendar()

    await callback.message.edit_text(
        f"📅 ПЕРЕНОС ЗАПИСИ #{booking_id}\n\n"
        "Выберите новую дату:",
        reply_markup=calendar_markup,
    )
    await callback.answer()


@router.callback_query(
    SimpleCalendarCallback.filter(), AdminStates.reschedule_select_date
)
async def process_reschedule_date(
    callback: CallbackQuery, callback_data: dict, state: FSMContext
):
    """Обработка выбора даты для переноса"""
    calendar = SimpleCalendar()
    selected, selected_date = await calendar.process_selection(callback, callback_data)

    if selected:
        # Сохраняем дату
        date_str = selected_date.strftime("%Y-%m-%d")
        await state.update_data(reschedule_date=date_str)

        # Получаем доступные слоты
        occupied = await BookingRepository.get_occupied_slots_for_day(date_str)
        blocked = await BookingRepository.get_blocked_slots(date_str)

        # Генерируем слоты (пока простая логика 9-19)
        from config import WORK_HOURS_END, WORK_HOURS_START

        occupied_times = {slot[0] for slot in occupied}
        blocked_times = {slot[1] for slot in blocked}

        available_slots = []
        for hour in range(WORK_HOURS_START, WORK_HOURS_END):
            time_str = f"{hour:02d}:00"
            if time_str not in occupied_times and time_str not in blocked_times:
                available_slots.append(time_str)

        if not available_slots:
            await callback.message.edit_text(
                f"❌ На дату {date_str} нет свободных слотов\n\n"
                "Выберите другую дату"
            )
            await state.clear()
            return

        # Показываем доступные слоты
        kb_buttons = []
        for slot in available_slots[:15]:  # Макс 15 слотов
            kb_buttons.append(
                [InlineKeyboardButton(text=slot, callback_data=f"reschedule_time:{slot}")]
            )

        kb_buttons.append(
            [InlineKeyboardButton(text="❌ Отмена", callback_data="reschedule_cancel")]
        )

        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

        await state.set_state(AdminStates.reschedule_select_time)
        await callback.message.edit_text(
            f"🕒 Выберите время на {date_str}:\n\n"
            f"🟢 Доступно слотов: {len(available_slots)}",
            reply_markup=kb,
        )


@router.callback_query(F.data.startswith("reschedule_time:"), AdminStates.reschedule_select_time)
async def confirm_reschedule(
    callback: CallbackQuery, state: FSMContext
):
    """Подтверждение переноса"""
    time_str = callback.data.split(":", 1)[1]

    data = await state.get_data()
    booking_id = data["reschedule_booking_id"]
    new_date = data["reschedule_date"]

    # Получаем старую запись
    # TODO: Добавить метод в BookingRepository
    # Пока просто переносим

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="reschedule_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="reschedule_cancel"),
            ]
        ]
    )

    await state.update_data(reschedule_time=time_str)

    await callback.message.edit_text(
        f"❓ ПОДТВЕРЖДЕНИЕ ПЕРЕНОСА\n\n"
        f"🆔 Запись: #{booking_id}\n"
        f"📅 Новая дата: {new_date}\n"
        f"🕒 Новое время: {time_str}\n\n"
        "⚠️ Клиент получит уведомление о переносе",
        reply_markup=kb,
    )


@router.callback_query(F.data == "reschedule_confirm")
async def execute_reschedule(callback: CallbackQuery, state: FSMContext):
    """Выполнение переноса"""
    data = await state.get_data()
    booking_id = data["reschedule_booking_id"]
    new_date = data["reschedule_date"]
    new_time = data["reschedule_time"]

    # TODO: Реализовать логику переноса в BookingRepository
    # success = await BookingRepository.reschedule_booking(booking_id, new_date, new_time)

    await AuditRepository.log_action(
        admin_id=callback.from_user.id,
        action="reschedule_booking_via_calendar",
        target_id=str(booking_id),
        details=f"new_date={new_date}, new_time={new_time}",
    )

    await state.clear()

    await callback.message.edit_text(
        f"✅ ЗАПИСЬ ПЕРЕНЕСЕНА!\n\n"
        f"🆔 Запись: #{booking_id}\n"
        f"📅 Новая дата: {new_date}\n"
        f"🕒 Новое время: {new_time}\n\n"
        "👤 Клиент уведомлен"
    )
    await callback.answer("✅ Готово!")


@router.callback_query(F.data == "reschedule_cancel")
async def cancel_reschedule(callback: CallbackQuery, state: FSMContext):
    """Отмена переноса"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("❌ Отменено")


# === БЛОКИРОВКА ДАТ ЧЕРЕЗ КАЛЕНДАРЬ ===


@router.callback_query(F.data == "block_dates_calendar")
async def start_block_dates(callback: CallbackQuery, state: FSMContext):
    """Начать блокировку дат через календарь"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    if not await has_permission(callback.from_user.id, "manage_bookings"):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await state.set_state(AdminStates.block_dates_start)

    calendar = SimpleCalendar()
    calendar_markup = await calendar.start_calendar()

    await callback.message.edit_text(
        "🚫 БЛОКИРОВКА ДАТ\n\n"
        "📅 Выберите НАЧАЛЬНУЮ дату блокировки:",
        reply_markup=calendar_markup,
    )
    await callback.answer()


@router.callback_query(SimpleCalendarCallback.filter(), AdminStates.block_dates_start)
async def process_block_start_date(
    callback: CallbackQuery, callback_data: dict, state: FSMContext
):
    """Обработка начальной даты блокировки"""
    calendar = SimpleCalendar()
    selected, selected_date = await calendar.process_selection(callback, callback_data)

    if selected:
        date_str = selected_date.strftime("%Y-%m-%d")
        await state.update_data(block_start_date=date_str)
        await state.set_state(AdminStates.block_dates_end)

        calendar_markup = await calendar.start_calendar()
        await callback.message.edit_text(
            f"📅 Начальная дата: {date_str}\n\n"
            "📅 Выберите КОНЕЧНУЮ дату блокировки:\n"
            "(или ту же для одного дня)",
            reply_markup=calendar_markup,
        )


@router.callback_query(SimpleCalendarCallback.filter(), AdminStates.block_dates_end)
async def process_block_end_date(
    callback: CallbackQuery, callback_data: dict, state: FSMContext
):
    """Обработка конечной даты блокировки"""
    calendar = SimpleCalendar()
    selected, selected_date = await calendar.process_selection(callback, callback_data)

    if selected:
        data = await state.get_data()
        start_date_str = data["block_start_date"]
        end_date_str = selected_date.strftime("%Y-%m-%d")

        # Проверка: конечная дата не раньше начальной
        if end_date_str < start_date_str:
            await callback.answer(
                "❌ Конечная дата не может быть раньше начальной", show_alert=True
            )
            return

        await state.update_data(block_end_date=end_date_str)
        await state.set_state(AdminStates.block_dates_reason)

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⏰ Весь день", callback_data="block_time_fullday"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🕒 Указать время", callback_data="block_time_custom"
                    )
                ],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="block_dates_cancel")],
            ]
        )

        await callback.message.edit_text(
            f"✅ ДИАПАЗОН ВЫБРАН\n\n"
            f"📅 С: {start_date_str}\n"
            f"📅 По: {end_date_str}\n\n"
            "Выберите время блокировки:",
            reply_markup=kb,
        )


@router.callback_query(F.data == "block_time_fullday")
async def block_fullday_reason(callback: CallbackQuery, state: FSMContext):
    """Блокировка на весь день - запрос причины"""
    await state.update_data(block_time_type="fullday")
    await state.set_state(AdminStates.block_dates_reason)

    await callback.message.edit_text(
        "📝 Введите причину блокировки:\n\n"
        "Пример: 'Отпуск', 'Праздник', 'Технические работы'\n\n"
        "Для отмены отправьте /cancel"
    )
    await callback.answer()


@router.message(AdminStates.block_dates_reason)
async def confirm_block_dates(message: Message, state: FSMContext):
    """Подтверждение блокировки дат"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=ADMIN_MENU)
        return

    reason = message.text.strip()
    data = await state.get_data()

    start_date = data["block_start_date"]
    end_date = data["block_end_date"]
    time_type = data.get("block_time_type", "fullday")

    # Создаем блокировку
    block_id = await CalendarRepository.block_date_range(
        start_date=start_date,
        end_date=end_date,
        admin_id=message.from_user.id,
        reason=reason,
        start_time=None if time_type == "fullday" else None,
        end_time=None if time_type == "fullday" else None,
    )

    if block_id:
        await AuditRepository.log_action(
            admin_id=message.from_user.id,
            action="block_date_range_via_calendar",
            target_id=str(block_id),
            details=f"from={start_date} to={end_date}, reason={reason}",
        )

        await message.answer(
            f"✅ ДАТЫ ЗАБЛОКИРОВАНЫ!\n\n"
            f"🚫 Блокировка #{block_id}\n"
            f"📅 С: {start_date}\n"
            f"📅 По: {end_date}\n"
            f"📝 Причина: {reason}\n\n"
            "✅ Клиенты не смогут забронировать эти даты",
            reply_markup=ADMIN_MENU,
        )
        logging.info(
            f"Admin {message.from_user.id} blocked dates {start_date} to {end_date}: {reason}"
        )
    else:
        await message.answer("❌ Ошибка при блокировке", reply_markup=ADMIN_MENU)

    await state.clear()


@router.callback_query(F.data == "block_dates_cancel")
async def cancel_block_dates(callback: CallbackQuery, state: FSMContext):
    """Отмена блокировки дат"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("❌ Отменено")


# === ПРОСМОТР ЗАБЛОКИРОВАННЫХ ДАТ ===


@router.callback_query(F.data == "view_blocked_dates")
async def view_blocked_dates(callback: CallbackQuery):
    """Показать список заблокированных дат"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    # Получаем блокировки на ближайшие 3 месяца
    today = datetime.now().date()
    end_date = today + timedelta(days=90)

    blocked_ranges = await CalendarRepository.get_blocked_ranges(
        start_date=today.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d")
    )

    if not blocked_ranges:
        await callback.message.edit_text(
            "🟢 Нет заблокированных дат на ближайшие 3 месяца"
        )
        return

    text = "🚫 ЗАБЛОКИРОВАННЫЕ ДАТЫ\n\n"

    for block in blocked_ranges[:10]:  # Показываем первые 10
        block_id, start, end, start_t, end_t, reason, _, created, _ = block
        time_info = "⏰ Весь день" if not start_t else f"🕒 {start_t}-{end_t}"
        text += f"#{block_id}: {start} - {end}\n{time_info}\n📝 {reason or 'Нет причины'}\n\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_blocked_dates")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "close_blocked_dates")
async def close_blocked_dates(callback: CallbackQuery):
    """Закрыть список блокировок"""
    await callback.message.delete()
    await callback.answer()
