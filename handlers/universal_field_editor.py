"""
Универсальный редактор полей для любых сущностей.

НИЗКИЙ ПРИОРИТЕТ (Nice to have)

Позволяет редактировать:
- Названия услуг
- Имена администраторов
- Любые другие текстовые поля
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

import aiosqlite
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from config import DATABASE_PATH
from keyboards.admin_keyboards import ADMIN_MENU
from utils.helpers import is_admin
from utils.states import AdminStates
from utils.callback_validator import create_safe_callback

router = Router()


class FieldConfig:
    """Конфигурация редактируемого поля"""
    
    def __init__(
        self,
        table: str,
        id_field: str,
        name_field: str,
        display_name: str,
        icon: str = "✏️",
        max_length: int = 100,
        min_length: int = 1,
        additional_fields: Optional[List[str]] = None,
        where_clause: Optional[str] = None
    ):
        self.table = table
        self.id_field = id_field
        self.name_field = name_field
        self.display_name = display_name
        self.icon = icon
        self.max_length = max_length
        self.min_length = min_length
        self.additional_fields = additional_fields or []
        self.where_clause = where_clause or ""


# Конфигурация редактируемых полей
EDITABLE_FIELDS: Dict[str, FieldConfig] = {
    "services": FieldConfig(
        table="services",
        id_field="id",
        name_field="name",
        display_name="Услуги",
        icon="💼",
        max_length=100,
        additional_fields=["description", "price", "duration_minutes"],
        where_clause="WHERE is_active = 1"
    ),
    "admins": FieldConfig(
        table="admins",
        id_field="user_id",
        name_field="username",
        display_name="Администраторы",
        icon="👤",
        max_length=50
    ),
}


class UniversalFieldEditor:
    """Универсальный редактор полей"""
    
    @staticmethod
    async def get_records(
        config: FieldConfig,
        limit: int = 50
    ) -> List[Tuple]:
        """
        Получить записи для редактирования.
        
        Returns:
            List[(id, name, ...additional_fields)]
        """
        fields = [config.id_field, config.name_field] + config.additional_fields
        fields_str = ", ".join(fields)
        
        query = f"""
            SELECT {fields_str}
            FROM {config.table}
            {config.where_clause}
            ORDER BY {config.name_field}
            LIMIT ?
        """
        
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(query, (limit,)) as cursor:
                return await cursor.fetchall()
    
    @staticmethod
    async def get_record_by_id(
        config: FieldConfig,
        record_id: Any
    ) -> Optional[Tuple]:
        """Получить одну запись по ID"""
        fields = [config.id_field, config.name_field] + config.additional_fields
        fields_str = ", ".join(fields)
        
        query = f"""
            SELECT {fields_str}
            FROM {config.table}
            WHERE {config.id_field} = ?
        """
        
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(query, (record_id,)) as cursor:
                return await cursor.fetchone()
    
    @staticmethod
    async def update_field(
        config: FieldConfig,
        record_id: Any,
        new_value: str
    ) -> bool:
        """Обновить поле"""
        query = f"""
            UPDATE {config.table}
            SET {config.name_field} = ?
            WHERE {config.id_field} = ?
        """
        
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(query, (new_value, record_id))
                await db.commit()
            return True
        except Exception as e:
            logging.error(f"Failed to update field: {e}")
            return False
    
    @staticmethod
    def validate_value(
        value: str,
        config: FieldConfig
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидация нового значения.
        
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "❌ Значение не может быть пустым"
        
        if len(value) < config.min_length:
            return False, f"❌ Минимальная длина: {config.min_length} символов"
        
        if len(value) > config.max_length:
            return False, f"❌ Максимальная длина: {config.max_length} символов"
        
        return True, None


# === ОБРАБОТЧИКИ ===

@router.message(F.text == "✏️ Редактор полей")
async def field_editor_menu(message: Message):
    """Главное меню редактора полей"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return
    
    keyboard = []
    
    for key, config in EDITABLE_FIELDS.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{config.icon} {config.display_name}",
                callback_data=create_safe_callback('edit_field', key)
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="v2:back_to_admin"
        )
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        "✏️ УНИВЕРСАЛЬНЫЙ РЕДАКТОР ПОЛЕЙ\n\n"
        "📝 Выберите тип поля для редактирования:",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("v2:edit_field:"))
async def select_field_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа поля"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Парсим callback
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    field_type = parts[2]
    config = EDITABLE_FIELDS.get(field_type)
    
    if not config:
        await callback.answer("❌ Неизвестный тип поля", show_alert=True)
        return
    
    # Получаем записи
    records = await UniversalFieldEditor.get_records(config)
    
    if not records:
        await callback.answer(
            f"ℹ️ Нет записей в {config.display_name}",
            show_alert=True
        )
        return
    
    # Создаем клавиатуру с записями
    keyboard = []
    
    for record in records[:20]:  # Ограничение 20 записей на страницу
        record_id = record[0]
        name = record[1]
        
        # Дополнительная информация если есть
        extra_info = ""
        if len(record) > 2 and config.additional_fields:
            # Показываем первое дополнительное поле
            extra_value = str(record[2])[:20]
            extra_info = f" ({extra_value}...)"
        
        button_text = f"{config.icon} {name}{extra_info}"
        
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=create_safe_callback('rename_field', field_type, record_id)
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="v2:back_to_field_editor"
        )
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"{config.icon} {config.display_name.upper()}\n\n"
        f"📊 Найдено записей: {len(records)}\n\n"
        "📝 Выберите запись для редактирования:",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("v2:rename_field:"))
async def start_rename(callback: CallbackQuery, state: FSMContext):
    """Начало процесса переименования"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    field_type = parts[2]
    record_id = parts[3]
    
    config = EDITABLE_FIELDS.get(field_type)
    if not config:
        await callback.answer("❌ Неизвестный тип", show_alert=True)
        return
    
    # Получаем текущее значение
    record = await UniversalFieldEditor.get_record_by_id(config, record_id)
    
    if not record:
        await callback.answer("❌ Запись не найдена", show_alert=True)
        return
    
    current_value = record[1]  # name_field
    
    # Сохраняем в state
    await state.update_data(
        field_type=field_type,
        record_id=record_id,
        current_value=current_value
    )
    await state.set_state(AdminStates.service_edit_value)
    
    # Показываем форму ввода
    await callback.message.edit_text(
        f"✏️ РЕДАКТИРОВАНИЕ ПОЛЯ\n\n"
        f"📝 Тип: {config.display_name}\n"
        f"📌 Текущее значение:\n{current_value}\n\n"
        f"⌨️ Введите новое значение:\n"
        f"(от {config.min_length} до {config.max_length} символов)\n\n"
        "❌ Или /cancel для отмены"
    )
    await callback.answer()


@router.message(AdminStates.service_edit_value)
async def apply_rename(message: Message, state: FSMContext):
    """Применение нового значения"""
    if not is_admin(message.from_user.id):
        await state.clear()
        await message.answer("❌ Нет доступа")
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Редактирование отменено", reply_markup=ADMIN_MENU)
        return
    
    # Получаем данные из state
    data = await state.get_data()
    field_type = data.get('field_type')
    record_id = data.get('record_id')
    current_value = data.get('current_value')
    new_value = message.text.strip()
    
    config = EDITABLE_FIELDS.get(field_type)
    if not config:
        await state.clear()
        await message.answer("❌ Ошибка конфигурации", reply_markup=ADMIN_MENU)
        return
    
    # Валидация
    is_valid, error_msg = UniversalFieldEditor.validate_value(new_value, config)
    
    if not is_valid:
        await message.answer(
            f"{error_msg}\n\n"
            "🔁 Попробуйте ещё раз:"
        )
        return
    
    # Обновляем
    success = await UniversalFieldEditor.update_field(
        config,
        record_id,
        new_value
    )
    
    await state.clear()
    
    if success:
        await message.answer(
            f"✅ УСПЕШНО ОБНОВЛЕНО\n\n"
            f"📝 Тип: {config.display_name}\n"
            f"📌 Было: {current_value}\n"
            f"✅ Стало: {new_value}",
            reply_markup=ADMIN_MENU
        )
        
        logging.info(
            f"Admin {message.from_user.id} renamed {field_type} "
            f"id={record_id}: '{current_value}' → '{new_value}'"
        )
    else:
        await message.answer(
            f"❌ Ошибка при обновлении\n\n"
            "🛠 Попробуйте позже или обратитесь к разработчику",
            reply_markup=ADMIN_MENU
        )


@router.callback_query(F.data == "v2:back_to_field_editor")
async def back_to_field_editor(callback: CallbackQuery):
    """Возврат в главное меню редактора"""
    keyboard = []
    
    for key, config in EDITABLE_FIELDS.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{config.icon} {config.display_name}",
                callback_data=create_safe_callback('edit_field', key)
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="v2:back_to_admin"
        )
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "✏️ УНИВЕРСАЛЬНЫЙ РЕДАКТОР ПОЛЕЙ\n\n"
        "📝 Выберите тип поля для редактирования:",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "v2:back_to_admin")
async def back_to_admin(callback: CallbackQuery):
    """Возврат в админ-панель"""
    await callback.message.delete()
    await callback.message.answer(
        "🔐 АДМИН-ПАНЕЛЬ\n\nВыберите действие:",
        reply_markup=ADMIN_MENU
    )
    await callback.answer()
