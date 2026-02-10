"""Патч для интеграции услуг в booking_handlers.py

Этот файл содержит обновленные обработчики.
Добавьте эти функции в booking_handlers.py:
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import DAY_NAMES, ERROR_NO_SERVICES, MAX_BOOKINGS_PER_USER
from database.queries import Database
from database.repositories.service_repository import ServiceRepository
from keyboards.user_keyboards import (
    MAIN_MENU,
    create_confirmation_keyboard,
    create_month_calendar,
    create_services_keyboard,
)
from services.booking_service import BookingService
from services.notification_service import NotificationService
from utils.helpers import now_local
from utils.validators import validate_id


router = Router()


# === НОВЫЙ ОБРАБОТЧИК: НАЧАЛО ЗАПИСИ С ВЫБОРОМ УСЛУГИ ===

@router.message(F.text == "📅 Записаться")
async def booking_start(message: Message, state: FSMContext):
    """Начало процесса записи с выбором услуги"""
    await state.clear()
    await Database.log_event(message.from_user.id, "booking_started")

    can_book, current_count = await Database.can_user_book(message.from_user.id)

    if not can_book:
        await message.answer(
            f"⚠️ У вас уже {MAX_BOOKINGS_PER_USER} активных записи.\n\n"
            "Отмените одну из них, чтобы записаться снова.\n"
            "📋 Мои записи → выберите запись для отмены",
            reply_markup=MAIN_MENU,
        )
        return

    # ✅ КРИТИЧНО: Получаем активные услуги
    services = await ServiceRepository.get_all_services(active_only=True)

    if not services:
        # Нет активных услуг
        await message.answer(
            "⚠️ УСЛУГИ ВРЕМЕННО НЕДОСТУПНЫ\n\n"
            "Обратитесь к администратору.",
            reply_markup=MAIN_MENU,
        )
        await Database.log_event(message.from_user.id, "booking_failed_no_services")
        return

    # ✅ НОВОЕ: Показываем выбор услуги
    kb = create_services_keyboard(services)

    await message.answer(
        "📍 ШАГ 1 из 4: Выберите услугу\n\n"
        f"📊 Ваших записей: {current_count}/{MAX_BOOKINGS_PER_USER}",
        reply_markup=kb,
    )


# === НОВЫЙ ОБРАБОТЧИК: ВЫБОР УСЛУГИ ===

@router.callback_query(F.data.startswith("select_service:"))
async def select_service(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора услуги"""
    service_id = validate_id(callback.data.split(":")[1], "service_id")

    if not service_id:
        await callback.answer("❌ Ошибка: неверный ID услуги", show_alert=True)
        return

    # Проверяем что услуга существует и активна
    service = await ServiceRepository.get_service_by_id(service_id)

    if not service:
        await callback.answer("❌ Услуга не найдена", show_alert=True)
        return

    if not service.is_active:
        await callback.answer("❌ Услуга недоступна", show_alert=True)
        return

    # ✅ КРИТИЧНО: Сохраняем service_id в state
    await state.update_data(service_id=service_id)

    await callback.answer("✅ Услуга выбрана")

    # Переходим к календарю
    today = now_local()
    kb = await create_month_calendar(today.year, today.month)

    can_book, current_count = await Database.can_user_book(callback.from_user.id)

    await callback.message.edit_text(
        f"✅ Выбрана услуга:\n\n"
        f"📝 {service.name}\n"
        f"⏱ Длительность: {service.duration_minutes} мин\n"
        f"💰 Цена: {service.price}\n\n"
        "📍 ШАГ 2 из 4: Выберите дату\n\n"
        "🟢 = все слоты свободны\n"
        "🟡 = есть свободные слоты\n"
        "🔴 = все занято\n"
        "⚫ = прошедшая дата\n\n"
        f"📊 Ваших записей: {current_count}/{MAX_BOOKINGS_PER_USER}",
        reply_markup=kb,
    )


# === ОБНОВЛЕННЫЙ ОБРАБОТЧИК: ПОДТВЕРЖДЕНИЕ ВРЕМЕНИ ===

@router.callback_query(F.data.startswith("time:"))
async def confirm_time(callback: CallbackQuery, state: FSMContext):
    """Подтверждение времени с информацией об услуге"""
    from datetime import datetime
    from config import TIMEZONE, WORK_HOURS_START, WORK_HOURS_END
    from utils.validators import parse_callback_data, validate_booking_data, validate_work_hours

    # Валидация
    result = parse_callback_data(callback.data, 3)
    if not result:
        await callback.answer("❌ Ошибка: неверные данные", show_alert=True)
        await state.clear()
        return

    _, date_str, time_str = result

    # Проверяем форматы
    is_valid, error_msg = validate_booking_data(date_str, time_str)
    if not is_valid:
        await callback.answer(f"❌ {error_msg}", show_alert=True)
        await state.clear()
        return

    # Проверяем что дата не в прошлом
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    time_obj = datetime.strptime(time_str, "%H:%M")
    booking_dt = datetime.combine(date_obj.date(), time_obj.time())
    booking_dt = booking_dt.replace(tzinfo=TIMEZONE)

    if booking_dt < now_local():
        await callback.answer("❌ Нельзя выбрать прошедшее время", show_alert=True)
        await state.clear()
        return

    # Проверяем рабочие часы
    if not validate_work_hours(time_obj.hour, WORK_HOURS_START, WORK_HOURS_END):
        await callback.answer(
            f"❌ Время вне рабочих часов ({WORK_HOURS_START}-{WORK_HOURS_END})",
            show_alert=True
        )
        await state.clear()
        return

    # ✅ НОВОЕ: Получаем информацию об услуге
    data = await state.get_data()
    service_id = data.get('service_id')

    service_info = ""
    if service_id:
        service = await ServiceRepository.get_service_by_id(service_id)
        if service:
            service_info = (
                f"📝 Услуга: {service.name}\n"
                f"⏱ Длительность: {service.duration_minutes} мин\n"
                f"💰 Цена: {service.price}\n\n"
            )

    day_name = DAY_NAMES[date_obj.weekday()]
    confirm_kb = create_confirmation_keyboard(date_str, time_str)

    try:
        await callback.message.edit_text(
            "📍 ШАГ 4 из 4: Подтверждение\n\n"
            f"{service_info}"
            f"📅 {date_obj.strftime('%d.%m.%Y')} ({day_name})\n"
            f"🕒 {time_str}\n\n"
            "✅ Подтвердить?",
            reply_markup=confirm_kb,
        )
    except Exception as e:
        import logging
        logging.error(f"Error editing message in confirm_time: {e}")
        await callback.answer("❌ Ошибка")


# === ОБНОВЛЕННЫЙ ОБРАБОТЧИК: ФИНАЛЬНОЕ БРОНИРОВАНИЕ ===

@router.callback_query(F.data.startswith("confirm:"))
async def book_time(
    callback: CallbackQuery,
    state: FSMContext,
    booking_service: BookingService,
    notification_service: NotificationService,
):
    """Финальное бронирование с передачей service_id"""
    from datetime import datetime
    from config import ERROR_LIMIT_EXCEEDED, ERROR_NO_SERVICES, ERROR_SERVICE_UNAVAILABLE, ERROR_SLOT_TAKEN
    from utils.validators import parse_callback_data, validate_booking_data
    from keyboards.user_keyboards import create_time_slots
    import logging

    # Валидация
    result = parse_callback_data(callback.data, 3)
    if not result:
        await callback.answer("❌ Ошибка: неверные данные", show_alert=True)
        return

    _, date_str, time_str = result

    # Проверяем форматы
    is_valid, _ = validate_booking_data(date_str, time_str)
    if not is_valid:
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return

    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name or "Гость"

    # ✅ КРИТИЧНО: Получаем service_id из state
    data = await state.get_data()
    service_id = data.get('service_id')

    # Получаем информацию об услуге для отображения
    service_info = ""
    if service_id:
        service = await ServiceRepository.get_service_by_id(service_id)
        if service:
            service_info = (
                f"📝 {service.name}\n"
                f"⏱ {service.duration_minutes} мин\n"
                f"💰 {service.price}\n"
            )

    # ✅ КРИТИЧНО: Передаем service_id в create_booking
    success, error_code = await booking_service.create_booking(
        date_str, time_str, user_id, username, service_id
    )

    if success:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        await callback.message.edit_text(
            "✅ ЗАПИСЬ ПОДТВЕРЖДЕНА!\n\n"
            f"{service_info}\n"
            f"📅 {date_obj.strftime('%d.%m.%Y')} ({DAY_NAMES[date_obj.weekday()]})\n"
            f"🕒 {time_str}\n\n"
            "⏰ Напоминание за 24 часа\n"
            "📋 'Мои записи' — посмотреть все"
        )
        await callback.answer("✅ Запись создана!", show_alert=False)

        try:
            await notification_service.notify_admin_new_booking(
                date_str, time_str, user_id, username
            )
        except Exception as e:
            logging.error(f"Failed to notify admin: {e}")
    else:
        # Обработка ошибок
        error_messages = {
            ERROR_NO_SERVICES: "⚠️ Услуги временно недоступны\n\nОбратитесь к администратору",
            ERROR_SERVICE_UNAVAILABLE: "⚠️ Выбранная услуга недоступна",
            ERROR_LIMIT_EXCEEDED: f"⚠️ У вас уже {MAX_BOOKINGS_PER_USER} активных записи",
            ERROR_SLOT_TAKEN: "❌ Этот слот уже занят!",
        }

        message = error_messages.get(error_code, "❌ Произошла ошибка, попробуйте позже")

        if error_code == ERROR_NO_SERVICES:
            await callback.message.edit_text(message)
            await callback.answer("Обратитесь к администратору", show_alert=True)
        else:
            await callback.answer(message, show_alert=True)

            # Показываем слоты снова
            if error_code != ERROR_NO_SERVICES:
                try:
                    text, kb = await create_time_slots(date_str, state)
                    await callback.message.edit_text(
                        "❌ Не удалось записать\n\nВыберите другое время:",
                        reply_markup=kb
                    )
                except Exception as e:
                    logging.error(f"Error showing time slots after failed booking: {e}")
