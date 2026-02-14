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
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# Добавить automation/ в путь
project_root = Path(__file__).parent.parent
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
PROJECT_ROOT = Path(__file__).parent.parent

if not MASTER_BOT_TOKEN:
    raise ValueError("MASTER_BOT_TOKEN not set in environment")

if not ADMIN_IDS:
    raise ValueError("ADMIN_IDS not set in environment")

# Инициализация
bot = Bot(token=MASTER_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

sub_manager = SubscriptionManager(str(PROJECT_ROOT / "subscriptions.db"))
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
3. Введите сумму платежа
4. Подтвердите

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


# === ДОБАВЛЕНИЕ КЛИЕНТА ===
@dp.message(F.text == "➕ Добавить клиента")
async def start_add_client(message: types.Message, state: FSMContext):
    """Начало процесса добавления клиента"""
    if not is_admin(message.from_user.id):
        return
    
    await state.set_state(NewClientStates.waiting_for_token)
    await message.answer(
        "🤖 **НОВЫЙ КЛИЕНТ**\n\n"
        "Шаг 1/3: Отправьте **токен бота**\n\n"
        "Как получить:\n"
        "1. Клиент пишет @BotFather\n"
        "2. Отправляет /newbot\n"
        "3. Получает токен вида: `123456:ABC...`\n\n"
        "Отправьте токен:",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )


@dp.message(NewClientStates.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    """Обработка токена бота"""
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    token = message.text.strip()
    
    # Базовая валидация токена
    if ":" not in token or len(token) < 20:
        await message.answer(
            "❌ Неверный формат токена\n\n"
            "Токен должен быть вида: `123456789:ABCdefGHI...`\n\n"
            "Попробуйте еще раз:",
            parse_mode="Markdown"
        )
        return
    
    # Сохранить токен
    await state.update_data(bot_token=token)
    
    await state.set_state(NewClientStates.waiting_for_admin_id)
    await message.answer(
        "✅ Токен принят\n\n"
        "Шаг 2/3: Отправьте **Telegram ID клиента**\n\n"
        "Как получить:\n"
        "1. Клиент пишет @userinfobot\n"
        "2. Отправляет /start\n"
        "3. Получает ID (число вида: 987654321)\n\n"
        "Отправьте ID:",
        parse_mode="Markdown"
    )


@dp.message(NewClientStates.waiting_for_admin_id)
async def process_admin_id(message: types.Message, state: FSMContext):
    """Обработка Telegram ID"""
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ ID должен быть числом\n\n"
            "Пример: 987654321\n\n"
            "Попробуйте еще раз:"
        )
        return
    
    # Сохранить ID
    await state.update_data(admin_telegram_id=admin_id)
    
    await state.set_state(NewClientStates.waiting_for_company_name)
    await message.answer(
        "✅ ID принят\n\n"
        "Шаг 3/3: Введите **название компании**\n\n"
        "Например: Салон красоты Анны\n\n"
        "Введите название:",
        parse_mode="Markdown"
    )


@dp.message(NewClientStates.waiting_for_company_name)
async def process_company_name(message: types.Message, state: FSMContext):
    """Обработка названия компании"""
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    company_name = message.text.strip()
    await state.update_data(company_name=company_name)
    
    # Получить все данные
    data = await state.get_data()
    
    # Показать подтверждение
    confirmation_text = f"""
📋 **ПОДТВЕРЖДЕНИЕ**

🏢 Компания: **{data['company_name']}**
🤖 Токен: `{data['bot_token'][:20]}...`
👤 Admin ID: `{data['admin_telegram_id']}`

⚡ После подтверждения бот будет автоматически развернут!

Продолжить?
    """
    
    await state.set_state(NewClientStates.waiting_for_confirmation)
    await message.answer(
        confirmation_text,
        reply_markup=confirm_keyboard(),
        parse_mode="Markdown"
    )


@dp.message(NewClientStates.waiting_for_confirmation)
async def process_confirmation(message: types.Message, state: FSMContext):
    """Обработка подтверждения"""
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    if message.text != "✅ Подтвердить":
        await message.answer("Нажмите кнопку подтверждения")
        return
    
    # Получить данные
    data = await state.get_data()
    
    # Показать процесс
    processing_msg = await message.answer(
        "⏳ **ДЕПЛОЙ ЗАПУЩЕН**\n\n"
        "Это займет 2-3 минуты...\n"
        "Не закрывайте бот!",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    
    try:
        # ДЕПЛОЙ!
        result = deploy_manager.deploy_client(
            bot_token=data['bot_token'],
            admin_telegram_id=data['admin_telegram_id'],
            company_name=data['company_name']
        )
        
        if result['success']:
            success_text = f"""
✅ **БОТ УСПЕШНО РАЗВЕРНУТ!**

🏢 Компания: **{data['company_name']}**
🆔 Client ID: `{result['client_id']}`
💾 Redis DB: **{result['redis_db']}**
🐳 Container: `{result['container_name']}`
📅 Подписка до: **{(datetime.now().strftime('%Y-%m-%d'))}** (+30 дней)

✅ Бот работает 24/7
✅ Клиент может начать использовать

📱 Клиент может найти бота по username в Telegram
            """
            
            await processing_msg.edit_text(
                success_text,
                parse_mode="Markdown"
            )
            
            # Уведомить клиента (опционально)
            try:
                await bot.send_message(
                    data['admin_telegram_id'],
                    f"🎉 Ваш бот для '{data['company_name']}' успешно запущен!\n\n"
                    f"Найдите своего бота в Telegram и нажмите /start"
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить клиента: {e}")
        
        else:
            await processing_msg.edit_text(
                f"❌ **ОШИБКА ДЕПЛОЯ**\n\n"
                f"Причина: {result.get('error', 'Unknown')}\n\n"
                f"Попробуйте еще раз или проверьте логи",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Deploy error: {e}", exc_info=True)
        await processing_msg.edit_text(
            f"❌ **КРИТИЧЕСКАЯ ОШИБКА**\n\n"
            f"Ошибка: {str(e)}\n\n"
            f"Обратитесь к техподдержке",
            parse_mode="Markdown"
        )
    
    finally:
        await state.clear()
        await message.answer(
            "Выберите действие:",
            reply_markup=main_menu_keyboard()
        )


# === СТАТИСТИКА ===
@dp.message(F.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    """Показать статистику"""
    if not is_admin(message.from_user.id):
        return
    
    await cmd_stats(message)


# === СПИСОК КЛИЕНТОВ ===
@dp.message(F.text == "👥 Список клиентов")
async def show_clients(message: types.Message):
    """Показать список клиентов"""
    if not is_admin(message.from_user.id):
        return
    
    await cmd_clients(message)


# === ПЛАТЕЖИ ===
@dp.message(F.text == "💰 Принять платеж")
async def start_payment(message: types.Message, state: FSMContext):
    """Начало приема платежа"""
    if not is_admin(message.from_user.id):
        return
    
    await state.set_state(PaymentStates.waiting_for_client_search)
    await message.answer(
        "💰 **ПРИЕМ ПЛАТЕЖА**\n\n"
        "Введите название компании для поиска:",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )


# === ПОМОЩЬ ===
@dp.message(F.text == "❓ Помощь")
async def show_help(message: types.Message):
    """Показать помощь"""
    if not is_admin(message.from_user.id):
        return
    
    await cmd_help(message)


# === ЗАПУСК ===
async def main():
    """Запуск бота"""
    logger.info("🚀 Master Bot starting...")
    logger.info(f"Admin IDs: {ADMIN_IDS}")
    
    # Удалить webhook если есть
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запустить polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
