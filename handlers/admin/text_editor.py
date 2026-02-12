"""Admin Text Editor - UI для редактирования текстов бота"""

import logging
from typing import Dict, List

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from services.text_manager import HybridTextManager

router = Router()


class TextEditorStates(StatesGroup):
    """Состояния для редактирования текстов"""

    waiting_for_new_text = State()


# ========================================
# ГЛАВНОЕ МЕНЮ РЕДАКТОРА
# ========================================


@router.message(F.text == "📝 Редактор текстов")
async def text_editor_menu(message: Message):
    """Главное меню редактора текстов"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Общие", callback_data="texts_cat:common"),
                InlineKeyboardButton(text="📅 Бронирование", callback_data="texts_cat:booking"),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Мои записи", callback_data="texts_cat:my_bookings"
                ),
                InlineKeyboardButton(text="💬 Отзывы", callback_data="texts_cat:feedback"),
            ],
            [
                InlineKeyboardButton(
                    text="👨‍💼 Админка", callback_data="texts_cat:admin"
                ),
                InlineKeyboardButton(text="👋 Онбординг", callback_data="texts_cat:onboarding"),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Перезагрузить YAML", callback_data="texts_reload_yaml"
                ),
                InlineKeyboardButton(text="🧹 Очистить кэш", callback_data="texts_clear_cache"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
        ]
    )

    await message.answer(
        "📝 <b>Редактор текстов бота</b>\n\n"
        "Выберите категорию для редактирования:\n\n"
        "💡 <i>Тексты можно редактировать без перезапуска бота</i>",
        reply_markup=keyboard,
    )


# ========================================
# ПРОСМОТР КАТЕГОРИИ
# ========================================


@router.callback_query(F.data.startswith("texts_cat:"))
async def show_category_texts(callback: CallbackQuery):
    """Показать тексты выбранной категории"""
    category = callback.data.split(":")[1]

    # Получаем все тексты категории
    texts = await HybridTextManager.get_all(category=category)

    if not texts:
        await callback.answer("⚠️ Тексты не найдены в этой категории", show_alert=True)
        return

    # Формируем список текстов с кнопками
    keyboard = []

    for key, (text, is_custom) in sorted(texts.items()):
        # Обрезаем длинный текст для отображения
        display_text = text[:50] + "..." if len(text) > 50 else text
        status = "✏️" if is_custom else "📄"

        button_text = f"{status} {key.split('.')[-1]}"
        keyboard.append(
            [InlineKeyboardButton(text=button_text, callback_data=f"text_edit:{key}")]
        )

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="texts_menu")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    category_names = {
        "common": "Общие",
        "booking": "Бронирование",
        "my_bookings": "Мои записи",
        "feedback": "Отзывы",
        "admin": "Админка",
        "onboarding": "Онбординг",
    }

    await callback.message.edit_text(
        f"📝 <b>Категория: {category_names.get(category, category)}</b>\n\n"
        f"Найдено текстов: {len(texts)}\n\n"
        f"📄 - дефолтный текст (из YAML)\n"
        f"✏️ - кастомизированный (из БД)",
        reply_markup=markup,
    )

    await callback.answer()


# ========================================
# РЕДАКТИРОВАНИЕ ТЕКСТА
# ========================================


@router.callback_query(F.data.startswith("text_edit:"))
async def edit_text_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование текста"""
    key = callback.data.split(":", 1)[1]

    # Получаем текущий текст
    current_text = await HybridTextManager.get(key)

    # Сохраняем ключ в состоянии
    await state.update_data(editing_key=key)
    await state.set_state(TextEditorStates.waiting_for_new_text)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Сбросить к дефолту", callback_data=f"text_reset:{key}"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="texts_cancel_edit")],
        ]
    )

    await callback.message.edit_text(
        f"📝 <b>Редактирование текста</b>\n\n"
        f"Ключ: <code>{key}</code>\n\n"
        f"<b>Текущий текст:</b>\n{current_text}\n\n"
        f"<i>Отправьте новый текст сообщением:</i>",
        reply_markup=keyboard,
    )

    await callback.answer()


@router.message(TextEditorStates.waiting_for_new_text)
async def save_new_text(message: Message, state: FSMContext):
    """Сохранить новый текст"""
    data = await state.get_data()
    key = data.get("editing_key")

    if not key:
        await message.answer("❌ Ошибка: ключ не найден")
        await state.clear()
        return

    new_text = message.text.strip()

    # Сохраняем в БД
    success = await HybridTextManager.update(
        key=key, text=new_text, admin_id=message.from_user.id
    )

    if success:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ К категории", callback_data=f"texts_cat:{key.split('.')[0]}"
                    )
                ],
                [InlineKeyboardButton(text="📝 Главное меню", callback_data="texts_menu")],
            ]
        )

        # Превью нового текста
        preview = new_text[:200] + "..." if len(new_text) > 200 else new_text

        await message.answer(
            f"✅ <b>Текст успешно обновлен!</b>\n\n"
            f"Ключ: <code>{key}</code>\n\n"
            f"<b>Новый текст:</b>\n{preview}",
            reply_markup=keyboard,
        )

        logging.info(f"Text updated by admin {message.from_user.id}: {key}")
    else:
        await message.answer("❌ Ошибка при сохранении текста. Попробуйте позже.")

    await state.clear()


# ========================================
# СБРОС К ДЕФОЛТУ
# ========================================


@router.callback_query(F.data.startswith("text_reset:"))
async def reset_text_confirm(callback: CallbackQuery):
    """Подтверждение сброса к дефолту"""
    key = callback.data.split(":", 1)[1]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, сбросить", callback_data=f"text_reset_confirm:{key}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data=f"text_edit:{key}"
                ),
            ]
        ]
    )

    await callback.message.edit_text(
        f"⚠️ <b>Сброс к дефолтному значению</b>\n\n"
        f"Ключ: <code>{key}</code>\n\n"
        f"Текст будет сброшен к значению из YAML файла.\n"
        f"Продолжить?",
        reply_markup=keyboard,
    )

    await callback.answer()


@router.callback_query(F.data.startswith("text_reset_confirm:"))
async def reset_text_execute(callback: CallbackQuery):
    """Выполнить сброс к дефолту"""
    key = callback.data.split(":", 1)[1]

    success = await HybridTextManager.reset_to_default(key)

    if success:
        # Получаем дефолтный текст
        default_text = await HybridTextManager.get(key)
        preview = default_text[:200] + "..." if len(default_text) > 200 else default_text

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ К категории", callback_data=f"texts_cat:{key.split('.')[0]}"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            f"✅ <b>Текст сброшен к дефолтному значению!</b>\n\n"
            f"Ключ: <code>{key}</code>\n\n"
            f"<b>Текущий текст:</b>\n{preview}",
            reply_markup=keyboard,
        )

        logging.info(f"Text reset to default by admin {callback.from_user.id}: {key}")
    else:
        await callback.answer("❌ Ошибка при сбросе текста", show_alert=True)


# ========================================
# СЛУЖЕБНЫЕ КОМАНДЫ
# ========================================


@router.callback_query(F.data == "texts_reload_yaml")
async def reload_yaml(callback: CallbackQuery):
    """Перезагрузить YAML тексты"""
    await HybridTextManager.reload_yaml()
    await callback.answer("✅ YAML тексты перезагружены", show_alert=True)
    logging.info(f"YAML reloaded by admin {callback.from_user.id}")


@router.callback_query(F.data == "texts_clear_cache")
async def clear_cache(callback: CallbackQuery):
    """Очистить кэш текстов"""
    HybridTextManager.clear_cache()
    await callback.answer("✅ Кэш текстов очищен", show_alert=True)
    logging.info(f"Cache cleared by admin {callback.from_user.id}")


@router.callback_query(F.data == "texts_cancel_edit")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Отменить редактирование"""
    await state.clear()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Главное меню", callback_data="texts_menu")]
        ]
    )

    await callback.message.edit_text(
        "❌ Редактирование отменено", reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "texts_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в главное меню редактора"""
    await state.clear()
    await text_editor_menu(callback.message)
    await callback.answer()
