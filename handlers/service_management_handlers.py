"""Обработчики управления услугами для администратора"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.models import Service
from database.repositories.service_repository import ServiceRepository
from keyboards.admin_keyboards import ADMIN_MENU
from utils.helpers import is_admin
from utils.states import AdminStates
from utils.validators import validate_id

router = Router()


# === ГЛАВНОЕ МЕНЮ УПРАВЛЕНИЯ УСЛУГАМИ ===


@router.message(F.text == "⚙️ Управление услугами")
async def services_menu(message: Message):
    """Главное меню управления услугами"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список услуг", callback_data="services_list")],
            [InlineKeyboardButton(text="➕ Добавить услугу", callback_data="service_create_start")],
            [InlineKeyboardButton(text="🔄 Изменить порядок", callback_data="services_reorder")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_cancel")],
        ]
    )

    await message.answer(
        "⚙️ УПРАВЛЕНИЕ УСЛУГАМИ\n\n" "Выберите действие:",
        reply_markup=kb,
    )


# === СПИСОК УСЛУГ ===


@router.callback_query(F.data == "services_list")
async def services_list_view(callback: CallbackQuery):
    """Просмотр списка всех услуг"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    services = await ServiceRepository.get_all_services(active_only=False)

    if not services:
        await callback.answer("📭 Нет услуг", show_alert=True)
        return

    keyboard = []
    for service in services:
        status_icon = "✅" if service.is_active else "🚫"
        text = f"{status_icon} {service.name} ({service.duration_minutes}мин, {service.price})"
        keyboard.append(
            [InlineKeyboardButton(text=text, callback_data=f"service_view:{service.id}")]
        )

    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="services_back")])

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        f"📋 СПИСОК УСЛУГ ({len(services)})\n\n"
        "✅ - активна\n"
        "🚫 - отключена\n\n"
        "Выберите услугу для просмотра/редактирования:",
        reply_markup=kb,
    )
    await callback.answer()


# === ПРОСМОТР УСЛУГИ ===


@router.callback_query(F.data.startswith("service_view:"))
async def service_view(callback: CallbackQuery):
    """Просмотр детальной информации об услуге"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    service_id = validate_id(callback.data.split(":")[1], "service_id")
    if not service_id:
        await callback.answer("❌ Неверный ID", show_alert=True)
        return

    service = await ServiceRepository.get_service_by_id(service_id)
    if not service:
        await callback.answer("❌ Услуга не найдена", show_alert=True)
        return

    status = "✅ Активна" if service.is_active else "🚫 Отключена"

    text = (
        f"📋 УСЛУГА #{service.id}\n\n"
        f"📝 Название: {service.name}\n"
        f"📄 Описание: {service.description or 'не указано'}\n"
        f"⏱ Длительность: {service.duration_minutes} минут\n"
        f"💰 Цена: {service.price}\n"
        f"🎨 Цвет: {service.color or 'не указан'}\n"
        f"📊 Порядок отображения: {service.display_order}\n"
        f"⚙️ Статус: {status}"
    )

    toggle_text = "🚫 Отключить" if service.is_active else "✅ Включить"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать", callback_data=f"service_edit:{service_id}"
                )
            ],
            [InlineKeyboardButton(text=toggle_text, callback_data=f"service_toggle:{service_id}")],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить", callback_data=f"service_delete_confirm:{service_id}"
                )
            ],
            [InlineKeyboardButton(text="🔙 К списку", callback_data="services_list")],
        ]
    )

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# === СОЗДАНИЕ УСЛУГИ ===


@router.callback_query(F.data == "service_create_start")
async def service_create_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания новой услуги"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.service_awaiting_name)

    await callback.message.edit_text(
        "➕ СОЗДАНИЕ УСЛУГИ\n\n"
        "Шаг 1/4: Введите название услуги\n"
        "Например: Консультация 90 минут\n\n"
        "Для отмены отправьте /cancel"
    )
    await callback.answer()


@router.message(AdminStates.service_awaiting_name)
async def service_create_name(message: Message, state: FSMContext):
    """Обработка названия услуги"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Создание услуги отменено", reply_markup=ADMIN_MENU)
        return

    name = message.text.strip()
    if len(name) < 3 or len(name) > 100:
        await message.answer("❌ Название должно быть от 3 до 100 символов\n\n" "Попробуйте снова:")
        return

    await state.update_data(name=name)
    await state.set_state(AdminStates.service_awaiting_description)

    await message.answer(
        f"✅ Название: {name}\n\n"
        "Шаг 2/4: Введите описание услуги\n"
        "(или отправьте '-' чтобы пропустить)"
    )


@router.message(AdminStates.service_awaiting_description)
async def service_create_description(message: Message, state: FSMContext):
    """Обработка описания услуги"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    description = None if message.text == "-" else message.text.strip()

    if description and len(description) > 500:
        await message.answer(
            "❌ Описание слишком длинное (макс 500 символов)\n\n" "Попробуйте снова:"
        )
        return

    await state.update_data(description=description)
    await state.set_state(AdminStates.service_awaiting_duration)

    await message.answer(
        f"✅ Описание: {description or 'не указано'}\n\n"
        "Шаг 3/4: Введите длительность в минутах\n"
        "Например: 60, 90, 120"
    )


@router.message(AdminStates.service_awaiting_duration)
async def service_create_duration(message: Message, state: FSMContext):
    """Обработка длительности услуги"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    try:
        duration = int(message.text)
        if duration < 15 or duration > 480:  # От 15 минут до 8 часов
            raise ValueError()
    except ValueError:
        await message.answer(
            "❌ Введите корректную длительность (15-480 минут)\n\n" "Попробуйте снова:"
        )
        return

    await state.update_data(duration_minutes=duration)
    await state.set_state(AdminStates.service_awaiting_price)

    await message.answer(
        f"✅ Длительность: {duration} минут\n\n"
        "Шаг 4/4: Введите цену\n"
        "Например: 3000 ₽ или Free"
    )


@router.message(AdminStates.service_awaiting_price)
async def service_create_price(message: Message, state: FSMContext):
    """Обработка цены и создание услуги"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    price = message.text.strip()
    if len(price) > 50:
        await message.answer("❌ Цена слишком длинная (макс 50 символов)\n\n" "Попробуйте снова:")
        return

    data = await state.get_data()

    # Получаем максимальный display_order
    services = await ServiceRepository.get_all_services(active_only=False)
    max_order = max([s.display_order for s in services], default=0)

    # Создаем услугу
    service = Service(
        id=0,  # Будет присвоен автоматически
        name=data["name"],
        description=data.get("description"),
        duration_minutes=data["duration_minutes"],
        price=price,
        color=None,
        is_active=True,
        display_order=max_order + 1,
    )

    service_id = await ServiceRepository.create_service(service)

    await state.clear()

    await message.answer(
        f"✅ Услуга создана!\n\n"
        f"ID: {service_id}\n"
        f"📝 {service.name}\n"
        f"⏱ {service.duration_minutes} минут\n"
        f"💰 {service.price}\n\n"
        "Услуга автоматически активирована.",
        reply_markup=ADMIN_MENU,
    )

    logging.info(f"Admin {message.from_user.id} created service {service_id}: {service.name}")


# === РЕДАКТИРОВАНИЕ УСЛУГИ ===


@router.callback_query(F.data.startswith("service_edit:"))
async def service_edit_menu(callback: CallbackQuery):
    """Меню редактирования услуги"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    service_id = validate_id(callback.data.split(":")[1], "service_id")
    if not service_id:
        await callback.answer("❌ Неверный ID", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Название", callback_data=f"edit_field:{service_id}:name"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Описание", callback_data=f"edit_field:{service_id}:description"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Длительность", callback_data=f"edit_field:{service_id}:duration"
                )
            ],
            [InlineKeyboardButton(text="✏️ Цена", callback_data=f"edit_field:{service_id}:price")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"service_view:{service_id}")],
        ]
    )

    await callback.message.edit_text(
        f"✏️ РЕДАКТИРОВАНИЕ УСЛУГИ #{service_id}\n\n" "Выберите поле для изменения:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"))
async def service_edit_field_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования поля"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        _, service_id, field = callback.data.split(":", 2)
        service_id = validate_id(service_id, "service_id")
        if not service_id:
            raise ValueError()
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    field_names = {
        "name": "название",
        "description": "описание",
        "duration": "длительность (в минутах)",
        "price": "цена",
    }

    await state.set_state(AdminStates.service_edit_value)
    await state.update_data(service_id=service_id, field=field)

    await callback.message.edit_text(
        f"✏️ РЕДАКТИРОВАНИЕ\n\n"
        f"Введите новое значение для поля '{field_names.get(field, field)}':\n\n"
        "Для отмены отправьте /cancel"
    )
    await callback.answer()


@router.message(AdminStates.service_edit_value)
async def service_edit_field_save(message: Message, state: FSMContext):
    """Сохранение отредактированного поля"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=ADMIN_MENU)
        return

    data = await state.get_data()
    service_id = data["service_id"]
    field = data["field"]
    new_value = message.text.strip()

    # Получаем текущую услугу
    service = await ServiceRepository.get_service_by_id(service_id)
    if not service:
        await state.clear()
        await message.answer("❌ Услуга не найдена", reply_markup=ADMIN_MENU)
        return

    # Валидация и обновление
    try:
        if field == "name":
            if len(new_value) < 3 or len(new_value) > 100:
                raise ValueError("Название должно быть от 3 до 100 символов")
            service.name = new_value
        elif field == "description":
            if new_value == "-":
                service.description = None
            elif len(new_value) > 500:
                raise ValueError("Описание слишком длинное (макс 500 символов)")
            else:
                service.description = new_value
        elif field == "duration":
            duration = int(new_value)
            if duration < 15 or duration > 480:
                raise ValueError("Длительность должна быть от 15 до 480 минут")
            service.duration_minutes = duration
        elif field == "price":
            if len(new_value) > 50:
                raise ValueError("Цена слишком длинная (макс 50 символов)")
            service.price = new_value
        else:
            raise ValueError("Неизвестное поле")

    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте снова:")
        return

    # Сохраняем изменения
    success = await ServiceRepository.update_service(service_id, service)

    await state.clear()

    if success:
        await message.answer(
            f"✅ Поле '{field}' успешно обновлено!\n\n" f"Новое значение: {new_value}",
            reply_markup=ADMIN_MENU,
        )
        logging.info(f"Admin {message.from_user.id} updated service {service_id} field {field}")
    else:
        await message.answer(
            "❌ Ошибка при сохранении",
            reply_markup=ADMIN_MENU,
        )


# === ПЕРЕКЛЮЧЕНИЕ АКТИВНОСТИ ===


@router.callback_query(F.data.startswith("service_toggle:"))
async def service_toggle_active(callback: CallbackQuery):
    """Переключение активности услуги"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    service_id = validate_id(callback.data.split(":")[1], "service_id")
    if not service_id:
        await callback.answer("❌ Неверный ID", show_alert=True)
        return

    service = await ServiceRepository.get_service_by_id(service_id)
    if not service:
        await callback.answer("❌ Услуга не найдена", show_alert=True)
        return

    # Переключаем статус
    service.is_active = not service.is_active
    success = await ServiceRepository.update_service(service_id, service)

    if success:
        status = "включена" if service.is_active else "отключена"
        await callback.answer(f"✅ Услуга {status}")
        logging.info(
            f"Admin {callback.from_user.id} toggled service {service_id} to {service.is_active}"
        )

        # Обновляем view
        await service_view(callback)
    else:
        await callback.answer("❌ Ошибка при обновлении", show_alert=True)


# === УДАЛЕНИЕ УСЛУГИ ===


@router.callback_query(F.data.startswith("service_delete_confirm:"))
async def service_delete_confirm(callback: CallbackQuery):
    """Подтверждение удаления услуги"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    service_id = validate_id(callback.data.split(":")[1], "service_id")
    if not service_id:
        await callback.answer("❌ Неверный ID", show_alert=True)
        return

    service = await ServiceRepository.get_service_by_id(service_id)
    if not service:
        await callback.answer("❌ Услуга не найдена", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Да, удалить", callback_data=f"service_delete:{service_id}"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"service_view:{service_id}")],
        ]
    )

    await callback.message.edit_text(
        f"⚠️ УДАЛЕНИЕ УСЛУГИ\n\n"
        f"Вы уверены, что хотите удалить услугу?\n\n"
        f"📝 {service.name}\n"
        f"⏱ {service.duration_minutes} минут\n"
        f"💰 {service.price}\n\n"
        "⚠️ Это действие нельзя отменить!",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("service_delete:"))
async def service_delete_execute(callback: CallbackQuery):
    """Выполнение удаления услуги"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    service_id = validate_id(callback.data.split(":")[1], "service_id")
    if not service_id:
        await callback.answer("❌ Неверный ID", show_alert=True)
        return

    success = await ServiceRepository.delete_service(service_id)

    if success:
        await callback.answer("✅ Услуга удалена")
        logging.info(f"Admin {callback.from_user.id} deleted service {service_id}")

        # Возвращаемся к списку
        await services_list_view(callback)
    else:
        await callback.answer("❌ Ошибка при удалении", show_alert=True)


# === ИЗМЕНЕНИЕ ПОРЯДКА ===


@router.callback_query(F.data == "services_reorder")
async def services_reorder_menu(callback: CallbackQuery):
    """Меню изменения порядка услуг"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    services = await ServiceRepository.get_all_services(active_only=False)

    if len(services) < 2:
        await callback.answer("❌ Для изменения порядка нужно минимум 2 услуги", show_alert=True)
        return

    keyboard = []
    for service in services:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⬆️ {service.name}", callback_data=f"reorder_up:{service.id}"
                ),
                InlineKeyboardButton(text="⬇️", callback_data=f"reorder_down:{service.id}"),
            ]
        )

    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="services_back")])

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        "🔄 ИЗМЕНИТЬ ПОРЯДОК УСЛУГ\n\n"
        "Используйте кнопки ⬆️⬇️ для изменения порядка\n"
        "(услуги отображаются в текущем порядке):",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reorder_up:"))
@router.callback_query(F.data.startswith("reorder_down:"))
async def services_reorder_execute(callback: CallbackQuery):
    """Выполнение изменения порядка"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    direction, service_id_str = callback.data.split(":", 1)
    service_id = validate_id(service_id_str, "service_id")
    if not service_id:
        await callback.answer("❌ Неверный ID", show_alert=True)
        return

    services = await ServiceRepository.get_all_services(active_only=False)
    service_dict = {s.id: s for s in services}

    if service_id not in service_dict:
        await callback.answer("❌ Услуга не найдена", show_alert=True)
        return

    # Сортируем по display_order
    sorted_services = sorted(services, key=lambda x: x.display_order)
    current_index = next(i for i, s in enumerate(sorted_services) if s.id == service_id)

    if direction == "reorder_up" and current_index > 0:
        # Меняем местами с предыдущей
        sorted_services[current_index], sorted_services[current_index - 1] = (
            sorted_services[current_index - 1],
            sorted_services[current_index],
        )
    elif direction == "reorder_down" and current_index < len(sorted_services) - 1:
        # Меняем местами со следующей
        sorted_services[current_index], sorted_services[current_index + 1] = (
            sorted_services[current_index + 1],
            sorted_services[current_index],
        )
    else:
        await callback.answer("❌ Нельзя переместить дальше")
        return

    # Обновляем display_order
    for i, service in enumerate(sorted_services):
        service.display_order = i + 1
        await ServiceRepository.update_service(service.id, service)

    await callback.answer("✅ Порядок изменен")
    logging.info(f"Admin {callback.from_user.id} reordered services")

    # Обновляем меню
    await services_reorder_menu(callback)


# === НАВИГАЦИЯ ===


@router.callback_query(F.data == "services_back")
async def services_back(callback: CallbackQuery):
    """Возврат в главное меню услуг"""
    await callback.message.delete()
    await callback.message.answer(
        "⚙️ УПРАВЛЕНИЕ УСЛУГАМИ\n\n" "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📋 Список услуг", callback_data="services_list")],
                [
                    InlineKeyboardButton(
                        text="➕ Добавить услугу", callback_data="service_create_start"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Изменить порядок", callback_data="services_reorder"
                    )
                ],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_cancel")],
            ]
        ),
    )
    await callback.answer()
