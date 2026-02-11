"""Обработчики для управления администраторами"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import ADMIN_IDS
from database.queries import Database
from keyboards.admin_keyboards import ADMIN_MENU
from utils.helpers import is_admin
from utils.states import AdminStates

router = Router()


@router.message(F.text == "👥 Администраторы")
async def admin_management_menu(message: Message):
    """Меню управления администраторами"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Список админов", callback_data="list_admins"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Добавить админа", callback_data="add_admin_start"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➖ Удалить админа", callback_data="remove_admin_start"
                )
            ],
        ]
    )

    admin_count = await Database.get_admin_count()
    total_admins = len(ADMIN_IDS) + admin_count

    await message.answer(
        f"👥 УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ\n\n"
        f"🔑 Статические (.env): {len(ADMIN_IDS)}\n"
        f"💾 Динамические (БД): {admin_count}\n"
        f"👥 Всего: {total_admins}\n\n"
        "Выберите действие:",
        reply_markup=kb,
    )


@router.callback_query(F.data == "list_admins")
async def list_admins(callback: CallbackQuery):
    """Список всех администраторов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    text = "📋 СПИСОК АДМИНИСТРАТОРОВ\n\n"

    # Статические админы из .env
    text += "🔑 Статические (.env):\n"
    for admin_id in ADMIN_IDS:
        user_link = f"<a href='tg://user?id={admin_id}'>{admin_id}</a>"
        text += f"  • {user_link}\n"
    text += "\n"

    # Динамические админы из БД
    db_admins = await Database.get_all_admins()

    if db_admins:
        text += "💾 Динамические (БД):\n"
        for user_id, username, added_by, added_at in db_admins:
            user_link = f"<a href='tg://user?id={user_id}'>{user_id}</a>"
            username_display = f"@{username}" if username else "нет username"
            text += f"  • {user_link} ({username_display})\n"
            text += f"    🔹 Добавлен: {added_at[:16]}\n"
        text += "\n"
    else:
        text += "💾 Динамические: нет\n\n"

    text += "ℹ️ Статические админы нельзя удалить через бота"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="back_to_admin_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "add_admin_start")
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления админа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.awaiting_new_admin_id)

    await callback.message.edit_text(
        "➕ ДОБАВЛЕНИЕ АДМИНИСТРАТОРА\n\n"
        "Введите Telegram ID пользователя:\n\n"
        "💡 Как узнать ID:\n"
        "1. Попросить пользователя написать @userinfobot\n"
        "2. Использовать @getmyid_bot\n\n"
        "Для отмены отправьте /cancel"
    )
    await callback.answer()


@router.message(AdminStates.awaiting_new_admin_id)
async def add_admin_process(message: Message, state: FSMContext):
    """Обработка добавления админа"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Добавление отменено", reply_markup=ADMIN_MENU)
        return

    # Валидация user_id
    try:
        new_admin_id = int(message.text)
        if new_admin_id <= 0:
            raise ValueError("ID must be positive")
    except ValueError:
        await message.answer(
            "❌ Неверный формат ID\n\n"
            "ID должен быть положительным числом.\n"
            "Пример: 123456789\n\n"
            "Введите корректный ID:"
        )
        return

    # Проверка что не уже админ
    if new_admin_id in ADMIN_IDS:
        await state.clear()
        await message.answer(
            "⚠️ Этот пользователь уже статический админ (.env)",
            reply_markup=ADMIN_MENU,
        )
        return

    is_already_admin = await Database.is_admin_in_db(new_admin_id)
    if is_already_admin:
        await state.clear()
        await message.answer(
            "⚠️ Этот пользователь уже админ", reply_markup=ADMIN_MENU
        )
        return

    # Получаем username если возможно
    try:
        chat = await message.bot.get_chat(new_admin_id)
        username = chat.username
    except Exception:
        username = None

    # Добавляем в БД
    success = await Database.add_admin(
        user_id=new_admin_id,
        username=username,
        added_by=message.from_user.id,
    )

    await state.clear()

    if success:
        username_display = f"@{username}" if username else "нет username"
        await message.answer(
            f"✅ Администратор добавлен!\n\n"
            f"🆔 ID: {new_admin_id}\n"
            f"👤 Username: {username_display}\n\n"
            f"ℹ️ Пользователь теперь может использовать /admin",
            reply_markup=ADMIN_MENU,
        )

        # Уведомляем нового админа
        try:
            await message.bot.send_message(
                new_admin_id,
                "🎉 Поздравляем!\n\n"
                "Вы получили права администратора!\n"
                "Используйте /admin для доступа к панели",
            )
        except Exception as e:
            logging.warning(f"Failed to notify new admin {new_admin_id}: {e}")

        logging.info(
            f"Admin {message.from_user.id} added new admin {new_admin_id} ({username})"
        )
    else:
        await message.answer(
            "❌ Ошибка при добавлении админа", reply_markup=ADMIN_MENU
        )


@router.callback_query(F.data == "remove_admin_start")
async def remove_admin_menu(callback: CallbackQuery):
    """Меню удаления админа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    db_admins = await Database.get_all_admins()

    if not db_admins:
        await callback.answer(
            "ℹ️ Нет динамических админов для удаления", show_alert=True
        )
        return

    keyboard = []
    for user_id, username, added_by, added_at in db_admins:
        display_text = f"➖ {user_id}"
        if username:
            display_text += f" (@{username})"

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=display_text, callback_data=f"remove_admin:{user_id}"
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_menu")]
    )

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        "➖ УДАЛЕНИЕ АДМИНИСТРАТОРА\n\n"
        f"Динамических админов: {len(db_admins)}\n\n"
        "⚠️ Статические админы (.env) не могут быть удалены\n\n"
        "Выберите админа для удаления:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("remove_admin:"))
async def remove_admin_confirm(callback: CallbackQuery):
    """Подтверждение удаления админа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        admin_to_remove = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    # Нельзя удалить себя
    if admin_to_remove == callback.from_user.id:
        await callback.answer(
            "❌ Нельзя удалить себя", show_alert=True
        )
        return

    # Проверка последнего админа
    total_admins = len(ADMIN_IDS) + await Database.get_admin_count()
    if total_admins <= 1:
        await callback.answer(
            "❌ Нельзя удалить последнего админа", show_alert=True
        )
        return

    # Удаляем
    success = await Database.remove_admin(admin_to_remove)

    if success:
        await callback.answer(f"✅ Админ {admin_to_remove} удалён")

        # Уведомляем удалённого админа
        try:
            await callback.bot.send_message(
                admin_to_remove,
                "⚠️ Ваши права администратора были отозваны",
            )
        except Exception as e:
            logging.warning(f"Failed to notify removed admin {admin_to_remove}: {e}")

        logging.info(
            f"Admin {callback.from_user.id} removed admin {admin_to_remove}"
        )

        # Обновляем меню
        await remove_admin_menu(callback)
    else:
        await callback.answer("❌ Ошибка удаления", show_alert=True)


@router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    """Возврат в меню управления админами"""
    await callback.message.delete()

    # Пересоздаём меню
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Список админов", callback_data="list_admins"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Добавить админа", callback_data="add_admin_start"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➖ Удалить админа", callback_data="remove_admin_start"
                )
            ],
        ]
    )

    admin_count = await Database.get_admin_count()
    total_admins = len(ADMIN_IDS) + admin_count

    await callback.message.answer(
        f"👥 УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ\n\n"
        f"🔑 Статические (.env): {len(ADMIN_IDS)}\n"
        f"💾 Динамические (БД): {admin_count}\n"
        f"👥 Всего: {total_admins}\n\n"
        "Выберите действие:",
        reply_markup=kb,
    )
    await callback.answer()
