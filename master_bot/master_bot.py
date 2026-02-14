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
from deploy_manager import DeploymentManager

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
deploy_manager = DeploymentManager(project_root=PROJECT_ROOT)


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
    if not is_admin(message.from_user.id):
        return
    
    help_text = """
📚 **ПОМОЩЬ**

**Основные команды:**
/start - Главное меню
/stats - Статистика
/clients - Список всех клиентов
/dbpath - Показать путь к базе данных
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


@dp.message(Command("dbpath"))
async def cmd_dbpath(message: types.Message):
    """Показать путь к базе данных (для отладки)"""
    if not is_admin(message.from_user.id):
        return
    
    db_exists = Path(DB_PATH).exists()
    db_size = Path(DB_PATH).stat().st_size if db_exists else 0
    
    info = f"""
🔍 **ИНФОРМАЦИЯ О БАЗЕ ДАННЫХ**

📂 Путь: `{DB_PATH}`
{'✅' if db_exists else '❌'} Существует: **{'Да' if db_exists else 'Нет'}**
📦 Размер: **{db_size} bytes**

📂 Project root: `{PROJECT_ROOT}`
    """
    
    await message.answer(info, parse_mode="Markdown")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
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
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    token = message.text.strip()
    
    if ":" not in token or len(token) < 20:
        await message.answer(
            "❌ Неверный формат токена\n\n"
            "Токен должен быть вида: `123456789:ABCdefGHI...`\n\n"
            "Попробуйте еще раз:",
            parse_mode="Markdown"
        )
        return
    
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
        "Шаг 3/3: Введите **название компании**\n\n"
        "Например: Салон красоты Анны\n\n"
        "Введите название:",
        parse_mode="Markdown"
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
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu_keyboard())
        return
    
    if message.text != "✅ Подтвердить":
        await message.answer("Нажмите кнопку подтверждения")
        return
    
    data = await state.get_data()
    
    processing_msg = await message.answer(
        "⏳ **ДЕПЛОЙ ЗАПУЩЕН**\n\n"
        "Это займет 2-3 минуты...\n"
        "Не закрывайте бот!",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    
    try:
        result = deploy_manager.deploy_client(
            bot_token=data['bot_token'],
            admin_telegram_id=data['admin_telegram_id'],
            company_name=data['company_name']
        )
        
        try:
            await processing_msg.delete()
        except:
            pass
        
        if result['success']:
            success_text = f"""
✅ **БОТ УСПЕШНО РАЗВЕРНУТ!**

🏢 Компания: **{data['company_name']}**
🆔 Client ID: `{result['client_id']}`
💾 Redis DB: **{result['redis_db']}**
🐳 Container: `{result['container_name']}`
📅 Подписка до: **{(datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')}** (+30 дней)

✅ Бот работает 24/7
✅ Клиент может начать использовать

📱 Клиент может найти бота по username в Telegram
            """
            
            await message.answer(success_text, parse_mode="Markdown")
            
            try:
                await bot.send_message(
                    data['admin_telegram_id'],
                    f"🎉 Ваш бот для '{data['company_name']}' успешно запущен!\n\n"
                    f"Найдите своего бота в Telegram и нажмите /start"
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить клиента: {e}")
        else:
            await message.answer(
                f"❌ **ОШИБКА ДЕПЛОЯ**\n\n"
                f"Причина: {result.get('error', 'Unknown')}\n\n"
                f"Попробуйте еще раз или проверьте логи",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Deploy error: {e}", exc_info=True)
        
        try:
            await processing_msg.delete()
        except:
            pass
        
        await message.answer(
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


# === ПЛАТЕЖИ ===
@dp.message(F.text == "💰 Принять платеж")
async def start_payment(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await state.set_state(PaymentStates.waiting_for_client_search)
    await message.answer(
        "💰 **ПРИЕМ ПЛАТЕЖА**\n\n"
        "Введите название компании для поиска:\n"
        "(можно ввести часть названия)",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
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
            f"❌ Клиенты не найдены по запросу: `{search_query}`\n\n"
            f"Попробуйте другое название:",
            parse_mode="Markdown"
        )
        return
    
    if len(found_clients) > 1:
        client_list = "🔍 **Найдено несколько клиентов:**\n\n"
        for i, client in enumerate(found_clients[:10], 1):
            company = client['company_name'] or 'Без названия'
            status_emoji = {'active': '✅', 'suspended': '⏸️'}.get(client['subscription_status'], '❓')
            client_list += f"{i}. {status_emoji} {company}\n"
        
        client_list += "\nУточните название:"
        await message.answer(client_list, parse_mode="Markdown")
        return
    
    client = found_clients[0]
    await state.update_data(client_id=client['client_id'], company_name=client['company_name'])
    
    expires = datetime.fromisoformat(client['subscription_expires_at'])
    days_left = (expires - datetime.now()).days
    
    client_info = f"""
✅ **Клиент найден**

🏢 Компания: **{client['company_name']}**
📅 Подписка до: **{expires.strftime('%Y-%m-%d')}** ({days_left} дней)
💾 Redis DB: **{client['redis_db']}**
📊 Статус: **{client['subscription_status']}**

Выберите период продления:
    """
    
    await state.set_state(PaymentStates.waiting_for_days)
    await message.answer(
        client_info,
        reply_markup=payment_periods_keyboard(),
        parse_mode="Markdown"
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
    
    amount_text = f"""
💰 **ВВОД СУММЫ**

📅 Период: **{days} дней**
💡 Рекомендуемая сумма: **{recommended_amount} ₽** (10₽/день)

Введите сумму платежа в рублях:
(или нажмите кнопку для рекомендуемой суммы)
    """
    
    await state.set_state(PaymentStates.waiting_for_amount)
    await message.answer(
        amount_text,
        reply_markup=amount_keyboard(recommended_amount),
        parse_mode="Markdown"
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
    
    confirmation_text = f"""
📋 **ПОДТВЕРЖДЕНИЕ ПЛАТЕЖА**

🏢 Компания: **{data['company_name']}**
📅 Период: **{data['days']} дней**
💰 Сумма: **{amount} ₽**

Подтвердить продление?
    """
    
    await state.set_state(PaymentStates.waiting_for_confirmation)
    await message.answer(
        confirmation_text,
        reply_markup=confirm_keyboard(),
        parse_mode="Markdown"
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
        # (add_payment уже продлевает на 30 дней по умолчанию)
        if data['days'] != 30:
            sub_manager.reactivate_client(
                client_id=data['client_id'],
                extend_days=data['days'] - 30
            )
        
        success_text = f"""
✅ **ПЛАТЕЖ ПРИНЯТ**

🏢 Компания: **{data['company_name']}**
📅 Продлено на: **{data['days']} дней**
💰 Сумма: **{data['amount']} ₽**

✅ Подписка успешно продлена!
        """
        
        await message.answer(
            success_text,
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"Payment error: {e}", exc_info=True)
        await message.answer(
            f"❌ **КРИТИЧЕСКАЯ ОШИБКА**\n\n"
            f"Ошибка: {str(e)}",
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
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
