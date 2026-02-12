"""Admin handlers for text editor - Управление текстами бота

Функционал:
- Просмотр всех текстов по категориям
- Редактирование текста через бота
- Предпросмотр изменений
- Сброс к дефолтным значениям
- Hot reload кэша
"""

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.repositories.admin_repository import AdminRepository
from services.text_manager import TextManager

logger = logging.getLogger(__name__)

router = Router()


# ==================== FSM States ====================
class TextEditorStates(StatesGroup):
    """FSM состояния для редактора текстов"""

    editing_text = State()


# ==================== Keyboards ====================
def get_text_editor_menu_kb() -> InlineKeyboardMarkup:
    """Клавиатура главного меню редактора"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📂 По категориям", callback_data="text_editor:categories"),
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить кэш", callback_data="text_editor:reload"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Главное меню", callback_data="admin_menu"),
            ],
        ]
    )


async def get_categories_kb() -> InlineKeyboardMarkup:
    """Клавиатура с категориями"""
    categories = await TextManager.get_categories()

    buttons = []
    for category in categories:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📁 {category.title()}",
                    callback_data=f"text_editor:category:{category}",
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="text_editor:menu")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_texts_list_kb(category: str, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Клавиатура со списком текстов"""
    texts = await TextManager.get_all(category=category)

    # Пагинация
    text_items = list(texts.items())
    total_pages = (len(text_items) + per_page - 1) // per_page
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_items = text_items[start_idx:end_idx]

    buttons = []
    for key, data in page_items:
        # Маркер кастомизации
        marker = "✏️" if data["is_customized"] else "📄"
        short_key = key.split(".")[-1]  # Показываем только последнюю часть

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{marker} {short_key}",
                    callback_data=f"text_editor:edit:{key}",
                )
            ]
        )

    # Кнопки пагинации
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"text_editor:category:{category}:page:{page-1}",
                )
            )
        nav_buttons.append(
            InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="ignore")
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"text_editor:category:{category}:page:{page+1}",
                )
            )
        buttons.append(nav_buttons)

    buttons.append(
        [InlineKeyboardButton(text="⬅️ Категории", callback_data="text_editor:categories")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_text_actions_kb(key: str) -> InlineKeyboardMarkup:
    """Клавиатура действий над текстом"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=f"text_editor:edit_prompt:{key}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Сбросить к дефолту",
                    callback_data=f"text_editor:reset:{key}",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="text_editor:categories"),
            ],
        ]
    )


def get_confirm_kb(key: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"text_editor:confirm_save:{key}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"text_editor:edit:{key}",
                ),
            ],
        ]
    )


# ==================== Handlers ====================
@router.message(F.text == "📝 Редактор текстов")
async def text_editor_menu(message: Message, state: FSMContext):
    """Главное меню редактора текстов"""
    await state.clear()

    # Проверяем права админа
    is_admin = await AdminRepository.is_admin(message.from_user.id)
    if not is_admin:
        await message.answer("❌ У вас нет прав для редактирования текстов")
        return

    await message.answer(
        "📝 <b>РЕДАКТОР ТЕКСТОВ БОТА</b>\n\n"
        "Здесь вы можете изменять любые тексты бота без редеплоя.\n\n"
        "📄 - дефолтный текст\n"
        "✏️ - кастомизированный",
        reply_markup=get_text_editor_menu_kb(),
    )


@router.callback_query(F.data == "text_editor:menu")
async def show_text_editor_menu(callback: CallbackQuery, state: FSMContext):
    """Показать главное меню"""
    await state.clear()
    await callback.message.edit_text(
        "📝 <b>РЕДАКТОР ТЕКСТОВ БОТА</b>\n\n"
        "Здесь вы можете изменять любые тексты бота без редеплоя.",
        reply_markup=get_text_editor_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "text_editor:categories")
async def show_categories(callback: CallbackQuery):
    """Показать категории"""
    categories_kb = await get_categories_kb()

    await callback.message.edit_text(
        "📂 <b>КАТЕГОРИИ ТЕКСТОВ</b>\n\n" "Выберите категорию:",
        reply_markup=categories_kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("text_editor:category:"))
async def show_category_texts(callback: CallbackQuery):
    """Показать тексты категории"""
    parts = callback.data.split(":")
    category = parts[2]
    page = int(parts[4]) if len(parts) > 4 else 0

    texts_kb = await get_texts_list_kb(category, page)
    texts = await TextManager.get_all(category=category)

    await callback.message.edit_text(
        f"📁 <b>Категория: {category.upper()}</b>\n\n"
        f"Найдено текстов: {len(texts)}\n\n"
        f"📄 - дефолтный\n"
        f"✏️ - кастомизированный",
        reply_markup=texts_kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("text_editor:edit:"))
async def show_text_detail(callback: CallbackQuery):
    """Показать детали текста"""
    key = callback.data.split(":", 2)[2]

    current_text = await TextManager.get(key)
    texts = await TextManager.get_all()
    text_data = texts.get(key, {})

    description = text_data.get("description", "Нет описания")
    is_customized = text_data.get("is_customized", False)

    status = "✏️ Кастомизирован" if is_customized else "📄 Дефолтный"

    await callback.message.edit_text(
        f"📝 <b>ТЕКСТ: {key}</b>\n\n"
        f"<b>Статус:</b> {status}\n"
        f"<b>Описание:</b> {description}\n\n"
        f"<b>Текущий текст:</b>\n<code>{current_text}</code>",
        reply_markup=get_text_actions_kb(key),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("text_editor:edit_prompt:"))
async def edit_text_prompt(callback: CallbackQuery, state: FSMContext):
    """Запросить новый текст"""
    key = callback.data.split(":", 2)[2]

    current_text = await TextManager.get(key)

    await state.update_data(editing_key=key, old_text=current_text)
    await state.set_state(TextEditorStates.editing_text)

    await callback.message.edit_text(
        f"✏️ <b>РЕДАКТИРОВАНИЕ</b>\n\n"
        f"<b>Ключ:</b> <code>{key}</code>\n\n"
        f"<b>Текущий текст:</b>\n{current_text}\n\n"
        f"Отправьте новый текст или /cancel для отмены"
    )
    await callback.answer()


@router.message(StateFilter(TextEditorStates.editing_text), F.text)
async def save_new_text(message: Message, state: FSMContext):
    """Сохранить новый текст"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Редактирование отменено")
        return

    data = await state.get_data()
    key = data["editing_key"]
    old_text = data["old_text"]
    new_text = message.text

    # Предпросмотр
    await state.update_data(new_text=new_text)

    await message.answer(
        f"👁 <b>ПРЕДПРОСМОТР ИЗМЕНЕНИЙ</b>\n\n"
        f"<b>Ключ:</b> <code>{key}</code>\n\n"
        f"<b>Было:</b>\n{old_text}\n\n"
        f"<b>Станет:</b>\n{new_text}\n\n"
        f"Применить изменения?",
        reply_markup=get_confirm_kb(key),
    )


@router.callback_query(F.data.startswith("text_editor:confirm_save:"))
async def confirm_save_text(callback: CallbackQuery, state: FSMContext):
    """Подтвердить сохранение"""
    key = callback.data.split(":", 2)[2]
    data = await state.get_data()
    new_text = data.get("new_text")

    if not new_text:
        await callback.answer("❌ Ошибка: текст не найден", show_alert=True)
        return

    # Сохраняем в БД
    success, message = await TextManager.update(key, new_text, admin_id=callback.from_user.id)

    if success:
        await callback.message.edit_text(
            f"✅ <b>ТЕКСТ ОБНОВЛЁН!</b>\n\n"
            f"<b>Ключ:</b> <code>{key}</code>\n"
            f"<b>Новый текст:</b>\n{new_text}\n\n"
            f"🔄 Изменения применятся немедленно (без рестарта)",
            reply_markup=get_text_editor_menu_kb(),
        )
        await callback.answer("✅ Сохранено!")
    else:
        await callback.message.edit_text(
            f"❌ <b>ОШИБКА</b>\n\n{message}", reply_markup=get_text_editor_menu_kb()
        )
        await callback.answer("❌ Ошибка", show_alert=True)

    await state.clear()


@router.callback_query(F.data.startswith("text_editor:reset:"))
async def reset_to_default(callback: CallbackQuery):
    """Сбросить к дефолтному значению"""
    key = callback.data.split(":", 2)[2]

    success, message = await TextManager.reset_to_default(key)

    if success:
        default_text = await TextManager.get(key)
        await callback.message.edit_text(
            f"✅ <b>ТЕКСТ СБРОШЕН К ДЕФОЛТУ</b>\n\n"
            f"<b>Ключ:</b> <code>{key}</code>\n"
            f"<b>Дефолтный текст:</b>\n{default_text}",
            reply_markup=get_text_editor_menu_kb(),
        )
        await callback.answer("✅ Сброшено!")
    else:
        await callback.answer(f"❌ {message}", show_alert=True)


@router.callback_query(F.data == "text_editor:reload")
async def reload_cache(callback: CallbackQuery):
    """Перезагрузить кэш и YAML"""
    TextManager.reload_yaml()

    await callback.answer("✅ Кэш и YAML перезагружены!")
    await callback.message.answer(
        "✅ <b>КЭШ ПЕРЕЗАГРУЖЕН</b>\n\n"
        "Все изменения применены.",
        reply_markup=get_text_editor_menu_kb(),
    )
