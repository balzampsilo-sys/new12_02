"""Обработчики управления услугами в админ-панели"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.repositories.service_repository import ServiceRepository
from keyboards.admin_keyboards import ADMIN_MENU
from utils.helpers import is_admin
from utils.states import AdminStates

router = Router()


# === ПРОСМОТР УСЛУГ ===


@router.callback_query(F.data == "admin_services")
async def services_menu(callback: CallbackQuery):
    """Меню управления услугами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    # Получаем все услуги (включая неактивные)
    all_services = await ServiceRepository.get_all_services()
    active_count = sum(1 for s in all_services if s.is_active)

    text = f"🎯 УПРАВЛЕНИЕ УСЛУГАМИ\n\n"
    text += f"Всего услуг: {len(all_services)}\n"
    text += f"Активных: {active_count}\n\n"

    if all_services:
        text += "📝 Список услуг:\n\n"
        for service in all_services:
            status = "✅" if service.is_active else "🚫"
            text += f"{status} {service.name}\n"
            text += f"   ⏱️ {service.duration_minutes} мин | 💰 {service.price}\n"
            if service.description:
                desc = (
                    service.description[:40] + "..."
                    if len(service.description) > 40
                    else service.description
                )
                text += f"   💬 {desc}\n"
            text += "\n"
    else:
        text += "💭 Услуг пока нет"

    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить услугу", callback_data="service_add")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="service_list_edit")],
        [InlineKeyboardButton(text="🔄 Изменить порядок", callback_data="service_reorder")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_cancel")],
    ]

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# === ДОБАВЛЕНИЕ УСЛУГИ ===


@router.callback_query(F.data == "service_add")
async def service_add_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления услуги"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.service_awaiting_name)

    await callback.message.edit_text(
        "➕ ДОБАВЛЕНИЕ УСЛУГИ\n\n"
        "Шаг 1/4: Введите название услуги\n\n"
        "💡 Примеры:\n"
        "  • Консультация (60 мин)\n"
        "  • VIP консультация\n"
        "  • Экспресс (30 мин)\n\n"
        "Для отмены: /cancel"
    )
    await callback.answer()


@router.message(AdminStates.service_awaiting_name)
async def service_add_name(message: Message, state: FSMContext):
    """Принятие названия услуги"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=ADMIN_MENU)
        return

    if len(message.text) > 100:
        await message.answer(
            "❌ Слишком длинное название (макс. 100 символов)\n\n"
            "Введите более короткое название:"
        )
        return

    await state.update_data(service_name=message.text)
    await state.set_state(AdminStates.service_awaiting_description)

    await message.answer(
        f"✅ Название: {message.text}\n\n"
        "Шаг 2/4: Введите описание услуги\n\n"
        "💡 Примеры:\n"
        "  • Стандартная консультация\n"
        "  • Углубленная консультация с рекомендациями\n\n"
        "Или отправьте '-' чтобы пропустить"
    )


@router.message(AdminStates.service_awaiting_description)
async def service_add_description(message: Message, state: FSMContext):
    """Принятие описания услуги"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=ADMIN_MENU)
        return

    description = None if message.text == "-" else message.text

    if description and len(description) > 500:
        await message.answer(
            "❌ Слишком длинное описание (макс. 500 символов)\n\n"
            "Введите более короткое описание:"
        )
        return

    await state.update_data(service_description=description)
    await state.set_state(AdminStates.service_awaiting_duration)

    data = await state.get_data()
    name = data.get("service_name")

    await message.answer(
        f"✅ Название: {name}\n"
        f"✅ Описание: {description or 'не указано'}\n\n"
        "Шаг 3/4: Введите длительность в минутах\n\n"
        "💡 Примеры: 30, 60, 90, 120\n\n"
        "Просто напишите число:"
    )


@router.message(AdminStates.service_awaiting_duration)
async def service_add_duration(message: Message, state: FSMContext):
    """Принятие длительности услуги"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=ADMIN_MENU)
        return

    try:
        duration = int(message.text)
        if duration < 15 or duration > 480:
            await message.answer(
                "❌ Длительность должна быть от 15 до 480 минут\n\n"
                "Введите корректную длительность:"
            )
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число\n\n" "Пример: 60")
        return

    await state.update_data(service_duration=duration)
    await state.set_state(AdminStates.service_awaiting_price)

    data = await state.get_data()
    name = data.get("service_name")
    description = data.get("service_description")

    await message.answer(
        f"✅ Название: {name}\n"
        f"✅ Описание: {description or 'не указано'}\n"
        f"✅ Длительность: {duration} мин\n\n"
        "Шаг 4/4: Введите цену\n\n"
        "💡 Примеры:\n"
        "  • 3000 ₽\n"
        "  • Бесплатно\n"
        "  • от 5000 ₽\n"
    )


@router.message(AdminStates.service_awaiting_price)
async def service_add_price_and_save(message: Message, state: FSMContext):
    """Принятие цены и сохранение услуги"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=ADMIN_MENU)
        return

    if len(message.text) > 50:
        await message.answer(
            "❌ Слишком длинная цена (макс. 50 символов)\n\n" "Введите более короткую цену:"
        )
        return

    data = await state.get_data()
    name = data.get("service_name")
    description = data.get("service_description")
    duration = data.get("service_duration")
    price = message.text

    # Получаем максимальный display_order
    all_services = await ServiceRepository.get_all_services()
    max_order = max([s.display_order for s in all_services], default=0)

    # Цвет по умолчанию
    default_color = "#4A90E2"

    # Создаем услугу
    service_id = await ServiceRepository.create_service(
        name=name,
        description=description,
        duration_minutes=duration,
        price=price,
        is_active=True,
        display_order=max_order + 1,
        color=default_color,
    )

    await state.clear()

    if service_id:
        await message.answer(
            "✅ УСЛУГА ДОБАВЛЕНА!\n\n"
            f"📝 Название: {name}\n"
            f"💬 Описание: {description or 'не указано'}\n"
            f"⏱️ Длительность: {duration} мин\n"
            f"💰 Цена: {price}\n"
            f"✅ Статус: Активна\n\n"
            "🎉 Пользователи теперь могут выбрать эту услугу при записи!",
            reply_markup=ADMIN_MENU,
        )
        logging.info(f"Admin {message.from_user.id} created service: {name}")
    else:
        await message.answer("❌ Ошибка при создании услуги", reply_markup=ADMIN_MENU)


# Продолжение следует...
# Следующие части: Редактирование, Удаление, Изменение порядка
