"""Состояния FSM"""

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """Состояния для администраторов"""
    awaiting_new_admin_id = State()
    awaiting_admin_username = State()
    awaiting_broadcast_message = State()  # ✅ ADDED: Для рассылки


class FieldEditStates(StatesGroup):
    """Состояния для редактирования полей"""
    selecting_field_type = State()
    selecting_record = State()
    entering_new_value = State()
