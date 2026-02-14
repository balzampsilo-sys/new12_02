#!/usr/bin/env python3
"""
Master Bot - Автоматический деплой клиентов через Telegram

Функции:
- Прием заявок на новых клиентов (через Redis Queue)
- Автоматический деплой ботов (через Deploy Worker)
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
from aiogram.filters import Command
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
from deploy_queue import DeployQueue

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === КОНФИГУРАЦИЯ ===
MASTER_BOT_TOKEN = os.getenv("MASTER_BOT_TOKEN")
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

# === DEPLOY QUEUE ===
deploy_queue = DeployQueue(
    redis_host=os.getenv("REDIS_HOST", "redis"),
    redis_port=int(os.getenv("REDIS_PORT", "6379")),
    redis_db=int(os.getenv("REDIS_DB", "0")),
    key_prefix=os.getenv("REDIS_KEY_PREFIX", "master_bot:")
)

if deploy_queue.is_available():
    logger.info("✅ Deploy Queue is ready")
else:
    logger.warning("⚠️ Deploy Queue not available - deploy functionality disabled")


# === FSM STATES ===
class NewClientStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_admin_id = State()
    waiting_for_company_name = State()
    waiting_for_confirmation = State()


class PaymentStates(StatesGroup):
    waiting_for_client_search = State()
    waiting_for_days = State()
    waiting_for_amount = State()
    waiting_for_confirmation = State()


# === КЛАВИАТУРЫ ===
def main_menu_keyboard():
    keyboard = [
        [KeyboardButton(text="➕ Добавить клиента")],
        [KeyboardButton(text="💰 Принять платеж")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="👥 Список клиентов")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def cancel_keyboard():
    keyboard = [[KeyboardButton(text="🚫 Отмена")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def confirm_keyboard():
    keyboard = [
        [KeyboardButton(text="✅ Подтвердить")],
        [KeyboardButton(text="🚫 Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def payment_periods_keyboard():
    keyboard = [
        [KeyboardButton(text="30 дней (1 месяц)")],
        [KeyboardButton(text="90 дней (3 месяца)")],
        [KeyboardButton(text="180 дней (6 месяцев)")],
        [KeyboardButton(text="365 дней (1 год)")],
        [KeyboardButton(text="🚫 Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def amount_keyboard(recommended: int):
    keyboard = [
        [KeyboardButton(text=f"✅ {recommended} ₽ (рекомендуем)")],
        [KeyboardButton(text="🚫 Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# === КОМАНДЫ ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            "❌ У вас нет доступа к этому боту.\n"
            "Это служебный бот для управления клиентами."
        )
        return
    
    queue_status = "✅ включена" if deploy_queue.is_available() else "⚠️ отключена"
    queue_length = deploy_queue.get_queue_length() if deploy_queue.is_available() else 0
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "🤖 МАСТЕР-БОТ ДЛЯ УПРАВЛЕНИЯ КЛИЕНТАМИ\n\n"
        "Что я умею:\n"
        "➕ Автоматически деплоить новых клиентов\n"
        "💰 Принимать платежи и продлевать подписки\n"
        "📊 Показывать статистику\n"
        "👥 Управлять клиентами\n\n"
        f"🔄 Очередь деплоя: {queue_status}\n"
        f"📋 Задач в очереди: {queue_length}\n\n"
        "Выберите действие:",
        reply_markup=main_menu_keyboard()
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    help_text = """
📚 ПОМОЩЬ

Основные команды:
/start - Главное меню
/stats - Статистика
/clients - Список всех клиентов
/queue - Статус очереди деплоя
/dbpath - Показать путь к базе данных
/help - Эта справка

Добавление клиента:
1. Нажмите "➕ Добавить клиента"
2. Отправьте токен бота (от @BotFather)
3. Отправьте Telegram ID клиента (от @userinfobot)
4. Введите название компании
5. Подтвердите - задача добавится в очередь
6. Deploy Worker автоматически выполнит деплой
7. Вы получите уведомление о результате

Прием платежа:
1. Нажмите "💰 Принять платеж"
2. Введите название компании для поиска
3. Выберите период продления
4. Введите сумму платежа (или используйте рекомендуемую)
5. Подтвердите

Архитектура:
• Master Bot (Docker) - управление
• Redis Queue - очередь задач
• Deploy Worker (HOST) - деплой клиентов

Поддержка: 
https://github.com/balzampsilo-sys/new12_02/blob/main/QUEUE_SETUP.md
    """
    await message.answer(help_text)


@dp.message(Command("queue"))
async def cmd_queue(message: types.Message):
    """Показать статус очереди деплоя"""
    if not is_admin(message.from_user.id):
        return
    
    if not deploy_queue.is_available():
        await message.answer(
            "❌ ОЧЕРЕДЬ НЕДОСТУПНА\n\n"
            "Redis не подключен.\n"
            "Проверьте что Redis запущен: docker-compose ps redis"
        )
        return
    
    queue_length = deploy_queue.get_queue_length()
    
    status_text = f"🔄 СТАТУС ОЧЕРЕДИ ДЕПЛОЯ\n\n"
    status_text += f"✅ Очередь активна\n"
    status_text += f"📋 Задач в очереди: {queue_length}\n\n"
    
    if queue_length > 0:
        status_text += f"⚡ Deploy Worker обработает их в порядке поступления.\n"
    else:
        status_text += "🎉 Очередь пуста. Все задачи выполнены!\n"
    
    status_text += f"\n🔧 Redis: {deploy_queue.redis_host}:{deploy_queue.redis_port}/{deploy_queue.redis_db}"
    
    await message.answer(status_text)


@dp.message(Command("dbpath"))
async def cmd_dbpath(message: types.Message):
    """Показать путь к базе данных (для отладки)"""
    if not is_admin(message.from_user.id):
        return
    
    db_exists = Path(DB_PATH).exists()
    db_size = Path(DB_PATH).stat().st_size if db_exists else 0
    
    info = f"🔍 ИНФОРМАЦИЯ О БАЗЕ ДАННЫХ\n\n"
    info += f"📂 Путь: {DB_PATH}\n"
    info += f"{'✅' if db_exists else '❌'} Существует: {'Да' if db_exists else 'Нет'}\n"
    info += f"📦 Размер: {db_size} bytes\n\n"
    info += f"📂 Project root: {PROJECT_ROOT}"
    
    await message.answer(info)


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    stats = sub_manager.get_statistics()
    
    stats_text = f"📊 СТАТИСТИКА\n\n"
    stats_text += f"👥 Всего клиентов: {stats['total_clients']}\n"
    stats_text += f"✅ Активных: {stats['active_clients']}\n"
    stats_text += f"⏸️ Приостановлено: {stats['suspended_clients']}\n"
    stats_text += f"🆓 Триал: {stats.get('trial_clients', 0)}\n\n"
    stats_text += f"💾 Redis DB:\n"
    stats_text += f"   • Занято: {16 - stats['available_redis_dbs']}\n"
    stats_text += f"   • Свободно: {stats['available_redis_dbs']}\n\n"
    stats_text += f"💰 Доход за месяц: {stats['monthly_revenue']:.2f} ₽"
    
    await message.answer(stats_text)


@dp.message(Command("clients"))
async def cmd_clients(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    clients = sub_manager.list_clients(limit=50)
    
    if not clients:
        await message.answer("📭 Клиентов пока нет")
        return
    
    client_list = "👥 СПИСОК КЛИЕНТОВ\n\n"
    
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
        
        client_list += f"{status_emoji} {company}\n"
        client_list += f"   Redis DB: {redis_db} | До: {expires}\n\n"
    
    await message.answer(client_list)


# === ДОБАВЛЕНИЕ КЛИЕНТА ===
@dp.message(F.text == "➕ Добавить клиента")
async def start_add_client(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    # Проверить доступность очереди
    if not deploy_queue.is_available():
        await message.answer(
            "❌ ОЧЕРЕДЬ ДЕПЛОЯ НЕДОСТУПНА\n\n"
            "Redis не подключен. Деплой временно невозможен.\n\n"
            "Обратитесь к администратору.\n\n"
            "Проверка: docker-compose ps redis",
            reply_markup=main_menu_keyboard()
        )
        return
    
    await state.set_state(NewClientStates.waiting_for_token)
    await message.answer(
        "🤖 НОВЫЙ КЛИЕНТ\n\n"
        "Шаг 1/3: Отправьте токен бота\n\n"
        "Как получить:\n"
        "1. Клиент пишет @BotFather\n"
        "2. Отправляет /newbot\n"
        "3. Получает токен вида: 123456:ABC...\n\n"
        "Отправьте токен:",
        reply_markup=cancel_keyboard()
    )


@dp.message(NewClientStates.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    token = message.text.strip()
    
    if ":" not in token or len(token) < 20:
        await message.answer(
            "❌ Неверный формат токена\n\n"
            "Токен должен быть вида: 123456789:ABCdefGHI...\n\n"
            "Попробуйте еще раз:"
        )
        return
    
    await state.update_data(bot_token=token)
    await state.set_state(NewClientStates.waiting_for_admin_id)
    await message.answer(
        "✅ Токен принят\n\n"
        "Шаг 2/3: Отправьте Telegram ID клиента\n\n"
        "Как получить:\n"
        "1. Клиент пишет @userinfobot\n"
        "2. Отправляет /start\n"
        "3. Получает ID (число вида: 987654321)\n\n"
        "Отправьте ID:"
    )


@dp.message(NewClientStates.waiting_for_admin_id)
async def process_admin_id(message: types.Message, state: FSMContext):
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
    
    await state.update_data(admin_telegram_id=admin_id)
    await state.set_state(NewClientStates.waiting_for_company_name)
    await message.answer(
        "✅ ID принят\n\n"
        "Шаг 3/3: Введите название компании\n\n"
        "Например: Салон красоты Анны\n\n"
        "Введите название:"
    )


@dp.message(NewClientStates.waiting_for_company_name)
async def process_company_name(message: types.Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    company_name = message.text.strip()
    await state.update_data(company_name=company_name)
    data = await state.get_data()
    
    # БЕЗ MARKDOWN - просто текст
    confirmation_text = f"""📋 ПОДТВЕРЖДЕНИЕ

🏢 Компания: {data['company_name']}
🤖 Токен: {data['bot_token'][:20]}...
👤 Admin ID: {data['admin_telegram_id']}

⚡ После подтверждения задача будет добавлена в очередь деплоя!
🤖 Deploy Worker автоматически выполнит развёртывание.

Продолжить?"""
    
    await state.set_state(NewClientStates.waiting_for_confirmation)
    await message.answer(
        confirmation_text,
        reply_markup=confirm_keyboard()
    )


@dp.message(NewClientStates.waiting_for_confirmation)
async def process_confirmation(message: types.Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    if message.text != "✅ Подтвердить":
        await message.answer("Нажмите кнопку подтверждения")
        return
    
    data = await state.get_data()
    
    # Проверить доступность очереди
    if not deploy_queue.is_available():
        await message.answer(
            "❌ Redis недоступен. Обратитесь к техподдержке.",
            reply_markup=main_menu_keyboard()
        )
        await state.clear()
        return
    
    # Добавить задачу в очередь
    try:
        task_id = deploy_queue.add_deploy_task(
            bot_token=data['bot_token'],
            admin_telegram_id=data['admin_telegram_id'],
            company_name=data['company_name'],
            created_by=message.from_user.id
        )
        
        if not task_id:
            await message.answer(
                "❌ Не удалось добавить задачу. Попробуйте ещё раз.",
                reply_markup=main_menu_keyboard()
            )
            await state.clear()
            return
        
        # Уведомить о постановке в очередь
        queue_length = deploy_queue.get_queue_length()
        
        success_text = f"""✅ ЗАДАЧА ДОБАВЛЕНА В ОЧЕРЕДЬ

🏢 Компания: {data['company_name']}
🆔 Task ID: {task_id}
📋 Позиция в очереди: {queue_length}

⏳ Деплой начнётся в течение 1-2 минут.
🔔 Вы получите уведомление о результате.

💡 Проверить статус: /queue"""
        
        await message.answer(
            success_text,
            reply_markup=main_menu_keyboard()
        )
        
        logger.info(f"✅ Task {task_id} added to queue for {data['company_name']}")
    
    except Exception as e:
        logger.error(f"Error adding task to queue: {e}", exc_info=True)
        await message.answer(
            "❌ КРИТИЧЕСКАЯ ОШИБКА\n\nОбратитесь к техподдержке",
            reply_markup=main_menu_keyboard()
        )
    
    finally:
        await state.clear()


# === ПЛАТЕЖИ ===
@dp.message(F.text == "💰 Принять платеж")
async def start_payment(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await state.set_state(PaymentStates.waiting_for_client_search)
    await message.answer(
        "💰 ПРИЕМ ПЛАТЕЖА\n\n"
        "Введите название компании для поиска:\n"
        "(можно ввести часть названия)",
        reply_markup=cancel_keyboard()
    )


@dp.message(PaymentStates.waiting_for_client_search)
async def process_client_search(message: types.Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    search_query = message.text.strip().lower()
    all_clients = sub_manager.list_clients(limit=100)
    found_clients = [
        c for c in all_clients 
        if search_query in (c.get('company_name') or '').lower()
    ]
    
    if not found_clients:
        await message.answer(
            f"❌ Клиенты не найдены по запросу: {search_query}\n\n"
            f"Попробуйте другое название:"
        )
        return
    
    if len(found_clients) > 1:
        client_list = "🔍 Найдено несколько клиентов:\n\n"
        for i, client in enumerate(found_clients[:10], 1):
            company = client['company_name'] or 'Без названия'
            status_emoji = {'active': '✅', 'suspended': '⏸️'}.get(client['subscription_status'], '❓')
            client_list += f"{i}. {status_emoji} {company}\n"
        
        client_list += "\nУточните название:"
        await message.answer(client_list)
        return
    
    client = found_clients[0]
    await state.update_data(client_id=client['client_id'], company_name=client['company_name'])
    
    expires = datetime.fromisoformat(client['subscription_expires_at'])
    days_left = (expires - datetime.now()).days
    
    client_info = f"""✅ Клиент найден

🏢 Компания: {client['company_name']}
📅 Подписка до: {expires.strftime('%Y-%m-%d')} ({days_left} дней)
💾 Redis DB: {client['redis_db']}
📊 Статус: {client['subscription_status']}

Выберите период продления:"""
    
    await state.set_state(PaymentStates.waiting_for_days)
    await message.answer(
        client_info,
        reply_markup=payment_periods_keyboard()
    )


@dp.message(PaymentStates.waiting_for_days)
async def process_payment_days(message: types.Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    days_map = {
        "30 дней (1 месяц)": 30,
        "90 дней (3 месяца)": 90,
        "180 дней (6 месяцев)": 180,
        "365 дней (1 год)": 365
    }
    
    days = days_map.get(message.text)
    if not days:
        await message.answer(
            "❌ Неверный выбор. Нажмите кнопку с периодом."
        )
        return
    
    await state.update_data(days=days)
    
    # Рекомендуемая сумма: 10₽/день (300₽ за месяц)
    recommended_amount = days * 10
    
    amount_text = f"""💰 ВВОД СУММЫ

📅 Период: {days} дней
💡 Рекомендуемая сумма: {recommended_amount} ₽ (10₽/день)

Введите сумму платежа в рублях:
(или нажмите кнопку для рекомендуемой суммы)"""
    
    await state.set_state(PaymentStates.waiting_for_amount)
    await message.answer(
        amount_text,
        reply_markup=amount_keyboard(recommended_amount)
    )


@dp.message(PaymentStates.waiting_for_amount)
async def process_payment_amount(message: types.Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    amount_text = message.text.strip()
    
    if amount_text.startswith("✅"):
        import re
        match = re.search(r'(\d+)', amount_text)
        if match:
            amount = int(match.group(1))
        else:
            await message.answer("❌ Ошибка парсинга суммы")
            return
    else:
        try:
            amount = int(amount_text.replace(" ", "").replace("₽", ""))
        except ValueError:
            await message.answer(
                "❌ Неверный формат суммы\n\n"
                "Введите число (например: 300 или 1500):"
            )
            return
    
    if amount <= 0:
        await message.answer(
            "❌ Сумма должна быть больше нуля\n\n"
            "Введите корректную сумму:"
        )
        return
    
    await state.update_data(amount=amount)
    data = await state.get_data()
    
    confirmation_text = f"""📋 ПОДТВЕРЖДЕНИЕ ПЛАТЕЖА

🏢 Компания: {data['company_name']}
📅 Период: {data['days']} дней
💰 Сумма: {amount} ₽

Подтвердить продление?"""
    
    await state.set_state(PaymentStates.waiting_for_confirmation)
    await message.answer(
        confirmation_text,
        reply_markup=confirm_keyboard()
    )


@dp.message(PaymentStates.waiting_for_confirmation)
async def process_payment_confirmation(message: types.Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    if message.text != "✅ Подтвердить":
        await message.answer("Нажмите кнопку подтверждения")
        return
    
    data = await state.get_data()
    
    try:
        # Добавить платеж и продлить подписку
        sub_manager.add_payment(
            client_id=data['client_id'],
            amount=data['amount'],
            currency="RUB",
            payment_method="manual",
            notes=f"Extended for {data['days']} days"
        )
        
        # Дополнительно продлить на указанный период
        if data['days'] != 30:
            sub_manager.reactivate_client(
                client_id=data['client_id'],
                extend_days=data['days'] - 30
            )
        
        success_text = f"""✅ ПЛАТЕЖ ПРИНЯТ

🏢 Компания: {data['company_name']}
📅 Продлено на: {data['days']} дней
💰 Сумма: {data['amount']} ₽

✅ Подписка успешно продлена!"""
        
        await message.answer(success_text)
    
    except Exception as e:
        logger.error(f"Payment error: {e}", exc_info=True)
        await message.answer("❌ КРИТИЧЕСКАЯ ОШИБКА\n\nОбратитесь к техподдержке")
    
    finally:
        await state.clear()
        await message.answer(
            "Выберите действие:",
            reply_markup=main_menu_keyboard()
        )


# === СТАТИСТИКА ===
@dp.message(F.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await cmd_stats(message)


# === СПИСОК КЛИЕНТОВ ===
@dp.message(F.text == "👥 Список клиентов")
async def show_clients(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await cmd_clients(message)


# === ПОМОЩЬ ===
@dp.message(F.text == "❓ Помощь")
async def show_help(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await cmd_help(message)


# === ЗАПУСК ===
async def main():
    logger.info("🚀 Master Bot starting...")
    logger.info(f"Admin IDs: {ADMIN_IDS}")
    
    # Проверить что БД доступна
    if Path(DB_PATH).exists():
        logger.info(f"✅ Database found: {DB_PATH}")
        stats = sub_manager.get_statistics()
        logger.info(f"📊 Loaded {stats['total_clients']} clients from database")
    else:
        logger.warning(f"⚠️ Database not found, will be created: {DB_PATH}")
    
    # Проверить очередь
    if deploy_queue.is_available():
        queue_length = deploy_queue.get_queue_length()
        logger.info(f"✅ Deploy Queue ready. Tasks in queue: {queue_length}")
    else:
        logger.warning("⚠️ Deploy Queue not available. Deploy functionality disabled.")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
