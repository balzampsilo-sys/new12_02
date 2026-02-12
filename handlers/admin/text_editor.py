"""Admin Text Editor - Редактор текстов бота"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from services.text_manager import TextManager
from database.repositories.admin_repository import AdminRepository

logger = logging.getLogger(__name__)
router = Router()


class TextEditorStates(StatesGroup):
    """States for text editing flow"""

    editing = State()  # Ввод нового текста


# ==================== KEYBOARDS ====================


def get_text_categories_kb():
    """Keyboard with text categories"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    categories = TextManager.get_categories()

    # Маппинг категорий на русские названия
    category_names = {
        "common": "🔧 Общие",
        "booking": "📅 Бронирование",
        "errors": "❌ Ошибки",
        "admin": "👨‍💼 Админ-панель",
        "start": "👋 Старт и помощь",
        "onboarding": "🎉 Онбординг",
        "system": "⚙️ Системные",
    }

    buttons = []
    for cat in categories:
        name = category_names.get(cat, cat.title())
        buttons.append(
            [InlineKeyboardButton(text=name, callback_data=f"text_cat:{cat}")]
        )

    # Кнопка возврата
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:back")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_texts_list_kb(category: str, page: int = 1, per_page: int = 10):
    """Keyboard with list of texts in category"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    texts = await TextManager.get_all(category=category, include_yaml=True)

    if not texts:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="text_editor")]
            ]
        )

    # Пагинация
    keys = sorted(texts.keys())
    total_pages = (len(keys) + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_keys = keys[start_idx:end_idx]

    buttons = []

    for key in page_keys:
        text_info = texts[key]
        # Показываем индикатор источника
        indicator = "✅" if text_info["is_custom"] else "📄"  # ✅ = custom, 📄 = default
        short_key = key.split(".")[-1]  # Показываем только последнюю часть

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{indicator} {short_key}", callback_data=f"text_edit:{key}"
                )
            ]
        )

    # Пагинация
    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"text_page:{category}:{page - 1}")
        )
    nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(text="➡️", callback_data=f"text_page:{category}:{page + 1}")
        )
    buttons.append(nav_row)

    # Кнопка возврата
    buttons.append([InlineKeyboardButton(text="⬅️ К категориям", callback_data="text_editor")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_text_edit_kb(key: str, is_custom: bool):
    """Keyboard for editing specific text"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = [[InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"text_prompt:{key}")]]

    # Кнопка сброса (только для custom текстов)
    if is_custom:
        buttons.append(
            [InlineKeyboardButton(text="🔄 Сбросить к дефолту", callback_data=f"text_reset:{key}")]
        )

    # Возврат к списку
    category = key.split(".")[0]
    buttons.append(
        [InlineKeyboardButton(text="⬅️ К списку", callback_data=f"text_cat:{category}")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== HANDLERS ====================


@router.message(F.text == "📝 Редактор текстов")
async def text_editor_menu(message: Message):
    """Main text editor menu"""
    # Check admin rights
    is_admin = await AdminRepository.is_admin(message.from_user.id)
    if not is_admin:
        await message.answer("❌ У вас нет доступа к этой функции")
        return

    await message.answer(
        "📝 <b>Редактор текстов бота</b>\n\n"
        "Здесь вы можете изменять любые сообщения бота без перезапуска.\n\n"
        "✅ - Кастомизированный текст\n"
        "📄 - Дефолтный текст\n\n"
        "Выберите категорию:",
        reply_markup=get_text_categories_kb(),
    )


@router.callback_query(F.data == "text_editor")
async def text_editor_callback(callback: CallbackQuery):
    """Return to text editor main menu"""
    await callback.message.edit_text(
        "📝 <b>Редактор текстов бота</b>\n\n"
        "✅ - Кастомизированный\n"
        "📄 - Дефолтный\n\n"
        "Выберите категорию:",
        reply_markup=get_text_categories_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("text_cat:"))
async def show_category_texts(callback: CallbackQuery):
    """Show texts in selected category"""
    category = callback.data.split(":")[1]

    texts = await TextManager.get_all(category=category, include_yaml=True)

    if not texts:
        await callback.answer("❌ Тексты не найдены", show_alert=True)
        return

    keyboard = await get_texts_list_kb(category, page=1)

    await callback.message.edit_text(
        f"📝 <b>Категория: {category}</b>\n\n"
        f"Найдено текстов: <b>{len(texts)}</b>\n\n"
        f"Выберите текст для редактирования:",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("text_page:"))
async def navigate_texts_page(callback: CallbackQuery):
    """Navigate through text pages"""
    parts = callback.data.split(":")
    category = parts[1]
    page = int(parts[2])

    keyboard = await get_texts_list_kb(category, page=page)

    texts = await TextManager.get_all(category=category)

    await callback.message.edit_text(
        f"📝 <b>Категория: {category}</b>\n\n"
        f"Найдено текстов: <b>{len(texts)}</b>\n\n"
        f"Выберите текст для редактирования:",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("text_edit:"))
async def show_text_details(callback: CallbackQuery):
    """Show text details and editing options"""
    key = callback.data.split(":", 1)[1]

    # Get text from all sources
    current_text = await TextManager.get(key)
    texts = await TextManager.get_all()
    text_info = texts.get(key, {})

    is_custom = text_info.get("is_custom", False)
    source = text_info.get("source", "unknown")
    description = text_info.get("description", "")

    source_emoji = {
        "database": "💾 База данных (кастом)",
        "yaml": "📄 YAML (дефолт)",
        "hardcoded": "🔒 Hardcoded",
    }

    message_text = (
        f"📝 <b>Редактирование текста</b>\n\n"
        f"🔑 <b>Ключ:</b> <code>{key}</code>\n"
        f"📎 <b>Источник:</b> {source_emoji.get(source, source)}\n"
    )

    if description:
        message_text += f"📝 <b>Описание:</b> {description}\n"

    message_text += f"\n💬 <b>Текущий текст:</b>\n<pre>{current_text}</pre>"

    await callback.message.edit_text(message_text, reply_markup=get_text_edit_kb(key, is_custom))
    await callback.answer()


@router.callback_query(F.data.startswith("text_prompt:"))
async def prompt_new_text(callback: CallbackQuery, state: FSMContext):
    """Prompt user to enter new text"""
    key = callback.data.split(":", 1)[1]

    current_text = await TextManager.get(key)

    await state.update_data(editing_key=key, editing_category=key.split(".")[0])
    await state.set_state(TextEditorStates.editing)

    await callback.message.edit_text(
        f"✏️ <b>Редактирование текста</b>\n\n"
        f"🔑 Ключ: <code>{key}</code>\n\n"
        f"💬 Текущий текст:\n<pre>{current_text}</pre>\n\n"
        f"⬇️ <b>Отправьте новый текст:</b>\n\n"
        f"ℹ️ Можно использовать параметры: {{date}}, {{time}}, {{username}}"
    )
    await callback.answer()


@router.message(StateFilter(TextEditorStates.editing))
async def save_new_text(message: Message, state: FSMContext):
    """Save new text to database"""
    data = await state.get_data()
    key = data["editing_key"]
    category = data["editing_category"]
    new_text = message.text

    # Save to database
    success = await TextManager.update(key=key, text=new_text, admin_id=message.from_user.id)

    if success:
        await message.answer(
            f"✅ <b>Текст успешно обновлен!</b>\n\n"
            f"🔑 Ключ: <code>{key}</code>\n\n"
            f"💬 Новый текст:\n<pre>{new_text}</pre>\n\n"
            f"ℹ️ Изменения применяются немедленно!",
            reply_markup=await get_texts_list_kb(category, page=1),
        )

        # Log admin action
        await AdminRepository.log_action(
            admin_id=message.from_user.id,
            action="text_updated",
            details=f"Updated text: {key}",
        )
    else:
        await message.answer(
            f"❌ <b>Ошибка при сохранении</b>\n\n"
            f"Попробуйте еще раз или обратитесь к разработчику"
        )

    await state.clear()


@router.callback_query(F.data.startswith("text_reset:"))
async def reset_text_to_default(callback: CallbackQuery):
    """Reset text to default (YAML) value"""
    key = callback.data.split(":", 1)[1]
    category = key.split(".")[0]

    # Get confirmation
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, сбросить", callback_data=f"text_reset_confirm:{key}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"text_edit:{key}"),
            ]
        ]
    )

    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение сброса</b>\n\n"
        f"Вы уверены что хотите сбросить текст <code>{key}</code> к дефолтному значению?\n\n"
        f"ℹ️ Кастомная версия будет удалена, и будет использоваться текст из YAML.",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("text_reset_confirm:"))
async def confirm_reset_text(callback: CallbackQuery):
    """Confirm and reset text to default"""
    key = callback.data.split(":", 1)[1]
    category = key.split(".")[0]

    success = await TextManager.reset_to_default(key)

    if success:
        # Get new (default) text
        default_text = await TextManager.get(key)

        await callback.message.edit_text(
            f"✅ <b>Текст сброшен к дефолтному!</b>\n\n"
            f"🔑 Ключ: <code>{key}</code>\n\n"
            f"📄 Дефолтный текст (YAML):\n<pre>{default_text}</pre>",
            reply_markup=await get_texts_list_kb(category, page=1),
        )

        # Log admin action
        await AdminRepository.log_action(
            admin_id=callback.from_user.id, action="text_reset", details=f"Reset text: {key}"
        )
    else:
        await callback.answer("❌ Ошибка при сбросе", show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """No-operation callback for pagination display"""
    await callback.answer()
