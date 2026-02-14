#!/usr/bin/env python3
"""
Master Bot - Автоматический деплой клиентов через Telegram

Функции:
- Прием заявок на новых клиентов
- Автоматический деплой ботов
- Управление подписками
- Интеграция с платежами
- Статистика и мониторинг
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# Загрузить переменные окружения из .env
from dotenv import load_dotenv
load_dotenv()

# Добавить automation/ в путь
project_root = Path(__file__).parent.parent.resolve()  # Абсолютный путь!
sys.path.insert(0, str(project_root / "automation"))

from subscription_manager import SubscriptionManager
from deploy_manager import DeploymentManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === КОНФИГУРАЦИЯ ===
MASTER_BOT_TOKEN = os.getenv("MASTER_BOT_TOKEN")  # Токен мастер-бота
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
PROJECT_ROOT = project_root

if not MASTER_BOT_TOKEN:
    raise ValueError("MASTER_BOT_TOKEN not set in environment")

if not ADMIN_IDS:
    raise ValueError("ADMIN_IDS not set in environment")

# Инициализация
bot = Bot(token=MASTER_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# АБСОЛЮТНЫЙ путь к базе данных
DB_PATH = str(PROJECT_ROOT / "subscriptions.db")
logger.info(f"💾 Database path: {DB_PATH}")
logger.info(f"📂 Project root: {PROJECT_ROOT}")

sub_manager = SubscriptionManager(DB_PATH)
deploy_manager = DeploymentManager(project_root=PROJECT_ROOT)


# === FSM STATES ===
class NewClientStates(StatesGroup):
    """Состояния для добавления нового клиента"""
    waiting_for_token = State()
    waiting_for_admin_id = State()
    waiting_for_company_name = State()
    waiting_for_confirmation = State()


class PaymentStates(StatesGroup):
    """Состояния для обработки платежа"""
    waiting_for_client_search = State()
    waiting_for_days = State()
    waiting_for_amount = State()
    waiting_for_confirmation = State()


# === КЛАВИАТУРЫ ===
def main_menu_keyboard():
    """Главное меню"""
    keyboard = [
        [KeyboardButton(text="➕ Добавить клиента")],
        [KeyboardButton(text="💰 Принять платеж")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="👥 Список клиентов")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def cancel_keyboard():
    """Кнопка отмены"""
    keyboard = [[KeyboardButton(text="🚫 Отмена")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def confirm_keyboard():
    """Кнопки подтверждения"""
    keyboard = [
        [KeyboardButton(text="✅ Подтвердить")],
        [KeyboardButton(text="🚫 Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def payment_periods_keyboard():
    """Периоды оплаты"""
    keyboard = [
        [KeyboardButton(text="30 дней (1 месяц)")],
        [KeyboardButton(text="90 дней (3 месяца)")],
        [KeyboardButton(text="180 дней (6 месяцев)")],
        [KeyboardButton(text="365 дней (1 год)")],
        [KeyboardButton(text="🚫 Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def amount_keyboard(recommended: int):
    """Клавиатура с рекомендуемой суммой"""
    keyboard = [
        [KeyboardButton(text=f"✅ {recommended} ₽ (рекомендуем)")],
        [KeyboardButton(text="🚫 Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# === ПРОВЕРКА АДМИНА ===
def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id in ADMIN_IDS


# === ОБРАБОТЧИКИ КОМАНД ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Команда /start"""
    if not is_admin(message.from_user.id):
        await message.answer(
            "❌ У вас нет доступа к этому боту.\n"
            "Это служебный бот для управления клиентами."
        )
        return
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "🤖 **Мастер-бот для управления клиентами**\n\n"
        "Что я умею:\n"
        "➕ Автоматически деплоить новых клиентов\n"
        "💰 Принимать платежи и продлевать подписки\n"
        "📊 Показывать статистику\n"
        "👥 Управлять клиентами\n\n"
        "Выберите действие:",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда /help"""
    if not is_admin(message.from_user.id):
        return
    
    help_text = """
📚 **ПОМОЩЬ**

**Основные команды:**
/start - Главное меню
/stats - Статистика
/clients - Список всех клиентов
/help - Эта справка

**Добавление клиента:**
1. Нажмите "➕ Добавить клиента"
2. Отправьте токен бота (от @BotFather)
3. Отправьте Telegram ID клиента (от @userinfobot)
4. Введите название компании
5. Подтвердите деплой

**Прием платежа:**
1. Нажмите "💰 Принять платеж"
2. Введите название компании для поиска
3. Выберите период продления
4. Введите сумму платежа (или используйте рекомендуемую)
5. Подтвердите

**Статистика:**
- Всего клиентов
- Активных подписок
- Свободных Redis DB
- Доход за месяц

**Поддержка:** 
https://github.com/balzampsilo-sys/new12_02
    """
    await message.answer(help_text, parse_mode="Markdown")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Команда /stats"""
    if not is_admin(message.from_user.id):
        return
    
    stats = sub_manager.get_statistics()
    
    stats_text = f"""
📊 **СТАТИСТИКА**

👥 Всего клиентов: **{stats['total_clients']}**
✅ Активных: **{stats['active_clients']}**
⏸️ Приостановлено: **{stats['suspended_clients']}**
🆓 Триал: **{stats.get('trial_clients', 0)}**

💾 Redis DB:
   • Занято: **{16 - stats['available_redis_dbs']}**
   • Свободно: **{stats['available_redis_dbs']}**

💰 Доход за месяц: **{stats['monthly_revenue']:.2f} ₽**
    """
    
    await message.answer(stats_text, parse_mode="Markdown")


@dp.message(Command("clients"))
async def cmd_clients(message: types.Message):
    """Команда /clients"""
    if not is_admin(message.from_user.id):
        return
    
    clients = sub_manager.list_clients(limit=50)
    
    if not clients:
        await message.answer("📭 Клиентов пока нет")
        return
    
    client_list = "👥 **СПИСОК КЛИЕНТОВ**\n\n"
    
    for client in clients:
        status_emoji = {
            'active': '✅',
            'suspended': '⏸️',
            'cancelled': '❌',
            'trial': '🆓'
        }.get(client['subscription_status'], '❓')
        
        company = client['company_name'] or 'Без названия'
        redis_db = client['redis_db']
        expires = client['subscription_expires_at'][:10]
        
        client_list += f"{status_emoji} **{company}**\n"
        client_list += f"   Redis DB: {redis_db} | До: {expires}\n\n"
    
    await message.answer(client_list, parse_mode="Markdown")


# [... rest of the handlers remain the same ...]
# Остальной код остается без изменений
#... (все обработчики остаются такими же)