"""Обработчики пользовательских команд"""

import asyncio

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import (
    CANCELLATION_HOURS,
    MAX_BOOKINGS_PER_USER,
    ONBOARDING_DELAY_LONG,
    ONBOARDING_DELAY_SHORT,
)
from database.queries import Database
from database.repositories.service_repository import ServiceRepository
from keyboards.user_keyboards import MAIN_MENU, create_onboarding_keyboard

router = Router()


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    """Команда /start с онбордингом"""
    await state.clear()
    user_id = message.from_user.id
    is_new = await Database.is_new_user(user_id)

    if is_new:
        await Database.log_event(user_id, "user_registered")

        # Приветствие
        await message.answer(
            "👋 Добро пожаловать в систему онлайн-записи!\n\n"
            "🎯 Записаться на удобное время — всего 3 клика"
        )
        await asyncio.sleep(ONBOARDING_DELAY_SHORT)

        # Преимущества
        await message.answer(
            "✨ ЧТО Я УМЕЮ:\n\n"
            "📅 Запись за 30 секунд\n"
            "🔄 Перенос в 2 клика\n"
            "⏰ Напоминания за 24ч\n"
            "⭐ 4.8/5 на основе 247 отзывов"
        )
        await asyncio.sleep(ONBOARDING_DELAY_SHORT)

        # Интерактивный выбор
        await message.answer(
            "Хотите быстрый обзор или сразу запишемся?",
            reply_markup=create_onboarding_keyboard(),
        )
    else:
        # Для вернувшихся
        stats = await Database.get_client_stats(user_id)
        if stats.total_bookings >= 5:
            await message.answer(
                "С возвращением! 🎉\n\n"
                f"Вы уже {stats.total_bookings} раз с нами.\n"
                f"Средний рейтинг ваших отзывов: {stats.avg_rating:.1f}⭐\n\n"
                "Спасибо за доверие!",
                reply_markup=MAIN_MENU,
            )
        else:
            await message.answer(
                "С возвращением! 👋\n\nВыберите действие:", reply_markup=MAIN_MENU
            )


@router.callback_query(F.data == "onboarding_tour")
async def onboarding_tour(callback: CallbackQuery, state: FSMContext):
    """Интерактивный туториал"""
    await state.clear()
    await callback.message.edit_text(
        "🎓 КАК ЭТО РАБОТАЕТ\n\n"
        "1️⃣ Выбираете дату в календаре\n"
        "   🟢 = много мест\n"
        "   🟡 = есть места\n"
        "   🔴 = всё занято\n\n"
        "2️⃣ Выбираете удобное время\n"
        "   (09:00 - 19:00)\n\n"
        "3️⃣ Подтверждаете — готово!\n"
        "   Вам придёт напоминание за 24ч\n\n"
        "💡 Можно иметь до 3 записей одновременно"
    )
    await asyncio.sleep(ONBOARDING_DELAY_LONG)
    await callback.message.answer("Всё понятно? Попробуем! 🚀", reply_markup=MAIN_MENU)
    await callback.answer()


@router.callback_query(F.data == "skip_onboarding")
async def skip_onboarding(callback: CallbackQuery, state: FSMContext):
    """Пропуск онбординга"""
    await state.clear()
    await callback.message.edit_text("Отлично! Давайте запишем вас 📅")
    await callback.message.answer("Выберите действие:", reply_markup=MAIN_MENU)
    await callback.answer()


@router.message(F.text == "ℹ️ О сервисе")
async def about_service(message: Message):
    """Информация о сервисе - получение из активных услуг"""
    # ✅ ИСПРАВЛЕНО: получаем информацию из активных услуг
    services = await ServiceRepository.get_all_services(active_only=True)
    
    if not services:
        await message.answer(
            "ℹ️ ИНФОРМАЦИЯ О СЕРВИСЕ\n\n"
            "В данный момент услуги временно недоступны.\n"
            "Пожалуйста, обратитесь к администратору.",
            reply_markup=MAIN_MENU,
        )
        return
    
    # Формируем список услуг
    text = "ℹ️ ДОСТУПНЫЕ УСЛУГИ\n\n"
    
    for i, service in enumerate(services, 1):
        text += f"{i}. 📝 {service.name}\n"
        text += f"   ⏱ Длительность: {service.duration_minutes} мин\n"
        text += f"   💰 Стоимость: {service.price}\n"
        if service.description:
            text += f"   📄 {service.description}\n"
        text += "\n"
    
    text += (
        f"🔔 Напоминание за {CANCELLATION_HOURS}ч до встречи\n"
        f"❌ Отмена возможна за {CANCELLATION_HOURS}ч\n"
        f"📊 Лимит одновременных записей: {MAX_BOOKINGS_PER_USER}"
    )
    
    await message.answer(text, reply_markup=MAIN_MENU)


@router.message(F.text == "📅 Записаться")
async def booking_button(message: Message, state: FSMContext):
    """Обработчик кнопки Записаться"""
    from handlers.booking_handlers import booking_start
    await booking_start(message, state)


@router.message(F.text == "📋 Мои записи")
async def my_bookings_button(message: Message):
    """Обработчик кнопки Мои записи"""
    from handlers.booking_handlers import my_bookings
    await my_bookings(message)


@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery):
    """Игнорирование callback"""
    await callback.answer()


@router.message()
async def unknown_message(message: Message):
    """Обработчик неизвестных сообщений"""
    await message.answer(
        "🤔 Я не понимаю это сообщение.\n\n"
        "Используйте кнопки меню 👇",
        reply_markup=MAIN_MENU
    )
