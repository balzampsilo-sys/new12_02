"""Состояния FSM для бота"""

from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    """Состояния для процесса бронирования"""
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_confirmation = State()


class AdminStates(StatesGroup):
    """Состояния для админ-панели"""
    awaiting_broadcast_message = State()  # ✅ Рассылка сообщений
    awaiting_block_date = State()
    awaiting_block_time = State()
    awaiting_block_reason = State()
    
    # ✅ Управление администраторами
    awaiting_admin_id = State()  # Старое название (deprecated)
    awaiting_new_admin_id = State()  # Добавление нового админа
    awaiting_admin_username = State()  # Ручной ввод username
    awaiting_removal_id = State()
    
    # Настройки расписания
    awaiting_work_hours_start = State()
    awaiting_work_hours_end = State()
    awaiting_slot_interval = State()  # ✅ Интервал слотов
    
    # Календарные состояния
    reschedule_select_date = State()
    reschedule_select_time = State()
    block_dates_start = State()
    block_dates_end = State()
    block_dates_reason = State()


class MassEditStates(StatesGroup):
    """Состояния для массового редактирования"""
    awaiting_date_selection = State()
    awaiting_action_selection = State()
    awaiting_confirmation = State()
