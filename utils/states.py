"""Состояния FSM для бота

Полный список всех состояний для всех хендлеров.
"""

from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    """Состояния для процесса бронирования"""
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_confirmation = State()


class AdminStates(StatesGroup):
    """Состояния для админ-панели"""
    # Рассылка
    awaiting_broadcast_message = State()
    
    # Блокировка слотов
    awaiting_block_date = State()
    awaiting_block_time = State()
    awaiting_block_reason = State()
    
    # Управление администраторами
    awaiting_admin_id = State()  # Старое название (deprecated, но оставляем для совместимости)
    awaiting_new_admin_id = State()  # Добавление нового админа
    awaiting_admin_username = State()  # Ручной ввод username
    awaiting_removal_id = State()  # Удаление админа
    
    # Настройки расписания
    awaiting_work_hours_start = State()
    awaiting_work_hours_end = State()
    awaiting_slot_interval = State()
    
    # Календарные состояния (для calendar_handlers.py)
    reschedule_select_date = State()
    reschedule_select_time = State()
    block_dates_start = State()
    block_dates_end = State()
    block_dates_reason = State()


class MassEditStates(StatesGroup):
    """Состояния для массового редактирования"""
    # Общие состояния
    awaiting_date_selection = State()
    awaiting_action_selection = State()
    awaiting_confirmation = State()
    
    # Массовый перенос времени
    awaiting_date_for_time_edit = State()
    awaiting_new_time = State()
    
    # Массовая смена услуги
    awaiting_date_for_service_edit = State()
    awaiting_new_service = State()


class ServiceStates(StatesGroup):
    """Состояния для управления услугами"""
    # Добавление услуги
    awaiting_service_name = State()
    awaiting_service_description = State()
    awaiting_service_duration = State()
    awaiting_service_price = State()
    
    # Редактирование услуги
    awaiting_edit_field = State()
    awaiting_new_value = State()


class SettingsStates(StatesGroup):
    """Состояния для настроек системы"""
    awaiting_setting_value = State()
    awaiting_timezone = State()
    awaiting_notification_time = State()
    awaiting_max_advance_days = State()
