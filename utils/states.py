"""Состояния FSM для бота"""

from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    """Состояния для процесса бронирования"""
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_confirmation = State()


class AdminStates(StatesGroup):
    """Состояния для админ-панели"""
    awaiting_broadcast_message = State()  # ✅ УНИФИЦИРОВАНО имя
    awaiting_block_date = State()
    awaiting_block_time = State()
    awaiting_block_reason = State()
    awaiting_admin_id = State()
    awaiting_removal_id = State()
    awaiting_work_hours_start = State()
    awaiting_work_hours_end = State()
    awaiting_slot_interval = State()  # ✅ НОВОЕ состояние!
    
    # Календарные состояния
    reschedule_select_date = State()
    reschedule_select_time = State()
    block_dates_start = State()
    block_dates_end = State()
    block_dates_reason = State()
