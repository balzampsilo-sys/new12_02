#!/usr/bin/env python3
"""
Sales Bot - Полная интеграция
Продажа подписок + активация ботов из пула
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import sys
sys.path.insert(0, '/app')

from automation.bot_pool_manager import BotPoolManager

try:
    from yookassa import Configuration, Payment
    YOOKASSA_AVAILABLE = True
except ImportError:
    YOOKASSA_AVAILABLE = False
    logging.warning("⚠️ YooKassa not available, payment disabled")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Переменные окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not set!")
    exit(1)

ADMIN_IDS = os.getenv('ADMIN_IDS', '').split(',')
ADMIN_IDS = [int(aid.strip()) for aid in ADMIN_IDS if aid.strip()]

YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')

REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

logger.info("=" * 60)
logger.info("💰 SALES BOT STARTING (FULL INTEGRATION)")
logger.info("=" * 60)
logger.info(f"🤖 Token: {BOT_TOKEN[:20]}...")
logger.info(f"👥 Admins: {ADMIN_IDS}")
logger.info(f"💳 YooKassa: {'✅ Configured' if YOOKASSA_AVAILABLE and YOOKASSA_SHOP_ID else '❌ Not configured'}")
logger.info(f"📡 Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
logger.info("=" * 60)

# Настройка YooKassa
if YOOKASSA_AVAILABLE and YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY
    logger.info("✅ YooKassa configured")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Pool Manager
pool_manager = BotPoolManager(
    redis_host=REDIS_HOST,
    redis_port=REDIS_PORT,
    redis_db=REDIS_DB,
    pool_size=100
)

# FSM States
class BuyStates(StatesGroup):
    waiting_bot_token = State()
    waiting_telegram_id = State()
    waiting_company_name = State()
    confirming_payment = State()

# Тарифы
TARIFFS = {
    "basic_1m": {
        "name": "🌟 Базовый (1 месяц)",
        "price": 990,
        "duration_days": 30,
        "features": [
            "✅ Автоматическая запись",
            "✅ Напоминания клиентам",
            "✅ База клиентов",
            "✅ Техподдержка"
        ]
    },
    "pro_3m": {
        "name": "🚀 PRO (3 месяца)",
        "price": 2490,
        "duration_days": 90,
        "features": [
            "✅ Всё из Базового",
            "✅ Аналитика",
            "✅ SMS-напоминания",
            "✅ Приоритетная поддержка",
            "💸 Скидка 16%"
        ]
    },
    "premium_12m": {
        "name": "👑 PREMIUM (год)",
        "price": 7990,
        "duration_days": 365,
        "features": [
            "✅ Всё из PRO",
            "✅ Интеграции (1C, AmoCRM)",
            "✅ Персональный менеджер",
            "✅ Белый label",
            "💸 Скидка 33%"
        ]
    }
}

# Временное хранилище заказов (в production - в БД)
orders = {}

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💸 Посмотреть тарифы",
                callback_data="view_tariffs"
            )
        ],
        [
            InlineKeyboardButton(
                text="❓ Как это работает?",
                callback_data="how_it_works"
            )
        ],
        [
            InlineKeyboardButton(
                text="📞 Поддержка",
                url="https://t.me/your_support"
            )
        ]
    ])
    
    await message.answer(
        f"👋 <b>Добро пожаловать!</b>\n\n"
        f"🤖 Я помогу вам подключить <b>автоматическую систему записи</b> "
        f"для вашего бизнеса.\n\n"
        f"📊 <b>Что вы получите:</b>\n"
        f"• Собственный Telegram-бот\n"
        f"• Автоматическая запись клиентов\n"
        f"• Напоминания о визитах\n"
        f"• База данных клиентов\n"
        f"• Аналитика\n\n"
        f"⚡ <b>Активация за 5-10 секунд!</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "view_tariffs")
async def show_tariffs(callback: CallbackQuery):
    await callback.answer()
    
    text = "💸 <b>Наши тарифы:</b>\n\n"
    keyboard_buttons = []
    
    for tariff_id, tariff in TARIFFS.items():
        text += f"<b>{tariff['name']}</b>\n"
        text += f"💵 {tariff['price']} ₽ / {tariff['duration_days']} дней\n\n"
        
        for feature in tariff['features']:
            text += f"{feature}\n"
        
        text += "\n" + "─" * 30 + "\n\n"
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"🛒 {tariff['name']} - {tariff['price']} ₽",
                callback_data=f"buy_{tariff_id}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "how_it_works")
async def show_how_it_works(callback: CallbackQuery):
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")]
    ])
    
    await callback.message.edit_text(
        f"❓ <b>Как это работает?</b>\n\n"
        f"<b>Шаг 1:</b> Создайте бота в @BotFather\n"
        f"   • Отправьте /newbot\n"
        f"   • Укажите название и username\n"
        f"   • Получите токен\n\n"
        f"<b>Шаг 2:</b> Выберите тариф и оплатите\n\n"
        f"<b>Шаг 3:</b> Введите данные:\n"
        f"   • Токен бота\n"
        f"   • Ваш Telegram ID\n"
        f"   • Название компании\n\n"
        f"<b>Шаг 4:</b> Готово! ⚡\n"
        f"   Ваш бот активируется за 5-10 секунд\n\n"
        f"📱 <b>Узнать свой Telegram ID:</b>\n"
        f"Отправьте /start боту @userinfobot",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("buy_"))
async def start_purchase(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    tariff_id = callback.data.replace("buy_", "")
    tariff = TARIFFS.get(tariff_id)
    
    if not tariff:
        await callback.message.answer("❌ Тариф не найден")
        return
    
    await state.update_data(tariff_id=tariff_id, user_id=callback.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_purchase")]
    ])
    
    await callback.message.edit_text(
        f"🛒 <b>Покупка: {tariff['name']}</b>\n\n"
        f"💰 Стоимость: <b>{tariff['price']} ₽</b>\n"
        f"📅 Срок: <b>{tariff['duration_days']} дней</b>\n\n"
        f"<b>Шаг 1/3:</b> Создайте бота в @BotFather\n\n"
        f"📝 <b>Инструкция:</b>\n"
        f"1. Откройте @BotFather\n"
        f"2. Отправьте /newbot\n"
        f"3. Укажите название (например: <code>Салон Анны</code>)\n"
        f"4. Укажите username (например: <code>anna_salon_bot</code>)\n"
        f"5. Скопируйте токен\n\n"
        f"Отправьте мне токен бота (например: <code>123456789:ABCdef...</code>)",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(BuyStates.waiting_bot_token)

@dp.message(BuyStates.waiting_bot_token)
async def process_bot_token(message: Message, state: FSMContext):
    bot_token = message.text.strip()
    
    # Проверка формата токена
    if not ':' in bot_token or len(bot_token) < 40:
        await message.answer(
            "❌ Неверный формат токена!\n\n"
            "Токен должен выглядеть так:\n"
            "<code>123456789:ABCdef_1234567890...</code>\n\n"
            "Попробуйте еще раз:",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(bot_token=bot_token)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📱 Узнать мой ID",
                url="https://t.me/userinfobot"
            )
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_purchase")]
    ])
    
    await message.answer(
        f"✅ Токен сохранен!\n\n"
        f"<b>Шаг 2/3:</b> Ваш Telegram ID\n\n"
        f"📱 Это число, которое идентифицирует вас в Telegram.\n"
        f"Отправьте /start боту @userinfobot чтобы узнать свой ID.\n\n"
        f"Отправьте мне ваш Telegram ID:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(BuyStates.waiting_telegram_id)

@dp.message(BuyStates.waiting_telegram_id)
async def process_telegram_id(message: Message, state: FSMContext):
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ ID должен быть числом!\n\n"
            "Например: <code>123456789</code>\n\n"
            "Попробуйте еще раз:",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(admin_telegram_id=telegram_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_purchase")]
    ])
    
    await message.answer(
        f"✅ ID сохранен!\n\n"
        f"<b>Шаг 3/3:</b> Название компании\n\n"
        f"📝 Введите название вашей компании или бизнеса\n"
        f"(например: <code>Салон красоты Анна</code>):",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(BuyStates.waiting_company_name)

@dp.message(BuyStates.waiting_company_name)
async def process_company_name(message: Message, state: FSMContext):
    company_name = message.text.strip()
    
    if len(company_name) < 3:
        await message.answer(
            "❌ Название слишком короткое!\n\n"
            "Введите название не менее 3 символов:"
        )
        return
    
    await state.update_data(company_name=company_name)
    data = await state.get_data()
    
    tariff = TARIFFS[data['tariff_id']]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💳 Оплатить",
                callback_data="confirm_payment"
            )
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_purchase")]
    ])
    
    await message.answer(
        f"📋 <b>Проверьте данные:</b>\n\n"
        f"🏢 Компания: <b>{company_name}</b>\n"
        f"🤖 Токен бота: <code>{data['bot_token'][:20]}...</code>\n"
        f"👤 Ваш ID: <code>{data['admin_telegram_id']}</code>\n\n"
        f"💰 Тариф: <b>{tariff['name']}</b>\n"
        f"💵 К оплате: <b>{tariff['price']} ₽</b>\n"
        f"📅 Срок: <b>{tariff['duration_days']} дней</b>\n\n"
        f"Все верно?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(BuyStates.confirming_payment)

@dp.callback_query(F.data == "confirm_payment", BuyStates.confirming_payment)
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    tariff = TARIFFS[data['tariff_id']]
    
    # Создать заказ
    order_id = str(uuid.uuid4())
    orders[order_id] = {
        **data,
        'status': 'pending',
        'created_at': datetime.now(),
        'amount': tariff['price']
    }
    
    # Если YooKassa не настроена - тестовый режим
    if not YOOKASSA_AVAILABLE or not YOOKASSA_SHOP_ID:
        await callback.message.edit_text(
            f"⚠️ <b>ТЕСТОВЫЙ РЕЖИМ</b>\n\n"
            f"YooKassa не настроена.\n"
            f"Симулирую успешную оплату...\n\n"
            f"Активирую бота...",
            parse_mode="HTML"
        )
        
        await asyncio.sleep(2)
        await process_successful_payment(order_id, callback.from_user.id)
        await state.clear()
        return
    
    # Создать платеж YooKassa
    try:
        payment = Payment.create({
            "amount": {
                "value": f"{tariff['price']}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f"https://t.me/{(await bot.me()).username}"
            },
            "capture": True,
            "description": f"{tariff['name']} - {data['company_name']}",
            "metadata": {
                "order_id": order_id,
                "user_id": str(callback.from_user.id)
            }
        })
        
        orders[order_id]['payment_id'] = payment.id
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Перейти к оплате",
                    url=payment.confirmation.confirmation_url
                )
            ]
        ])
        
        await callback.message.edit_text(
            f"💳 <b>Счет создан!</b>\n\n"
            f"💰 Сумма: <b>{tariff['price']} ₽</b>\n"
            f"📝 Заказ: <code>{order_id[:8]}</code>\n\n"
            f"Нажмите кнопку для оплаты.\n"
            f"После оплаты бот активируется автоматически!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Начать проверку статуса платежа
        asyncio.create_task(check_payment_status(order_id, callback.from_user.id))
        
    except Exception as e:
        logger.error(f"❌ Payment creation error: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка создания платежа: {e}\n\n"
            f"Попробуйте позже или обратитесь в поддержку."
        )
    
    await state.clear()

async def check_payment_status(order_id: str, user_id: int, max_attempts: int = 60):
    """Проверка статуса платежа"""
    for attempt in range(max_attempts):
        await asyncio.sleep(10)
        
        order = orders.get(order_id)
        if not order or order['status'] != 'pending':
            return
        
        try:
            payment = Payment.find_one(order['payment_id'])
            
            if payment.status == 'succeeded':
                await process_successful_payment(order_id, user_id)
                return
            elif payment.status == 'canceled':
                orders[order_id]['status'] = 'canceled'
                await bot.send_message(
                    user_id,
                    "❌ Платеж отменен."
                )
                return
        
        except Exception as e:
            logger.error(f"❌ Error checking payment: {e}")

async def process_successful_payment(order_id: str, user_id: int):
    """Обработка успешного платежа"""
    
    order = orders.get(order_id)
    if not order:
        return
    
    orders[order_id]['status'] = 'paid'
    
    try:
        # 1. Найти свободный бот
        await bot.send_message(
            user_id,
            "🔍 Поиск свободного бота в пуле..."
        )
        
        free_bot = await pool_manager.find_free_bot()
        
        if not free_bot:
            await bot.send_message(
                user_id,
                "❌ К сожалению, все боты заняты.\n"
                "Попробуйте через несколько минут или обратитесь в поддержку."
            )
            orders[order_id]['status'] = 'no_bots'
            return
        
        # 2. Создать client_id
        client_id = f"client_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{free_bot['pool_id']}"
        
        # 3. Активировать бот
        await bot.send_message(
            user_id,
            f"⚡ Активирую бота #{free_bot['pool_id']}..."
        )
        
        success = await pool_manager.activate_bot(
            container_id=free_bot['container_id'],
            bot_token=order['bot_token'],
            admin_telegram_id=order['admin_telegram_id'],
            client_id=client_id,
            company_name=order['company_name']
        )
        
        if success:
            orders[order_id]['status'] = 'activated'
            orders[order_id]['client_id'] = client_id
            orders[order_id]['container_id'] = free_bot['container_id']
            
            # Получить username бота
            try:
                bot_info = await Bot(token=order['bot_token']).me()
                bot_username = f"@{bot_info.username}"
            except:
                bot_username = "ваш бот"
            
            tariff = TARIFFS[order['tariff_id']]
            expires_at = datetime.now() + timedelta(days=tariff['duration_days'])
            
            await bot.send_message(
                user_id,
                f"🎉 <b>ВАШ БОТ ГОТОВ!</b>\n\n"
                f"🤖 Бот: {bot_username}\n"
                f"🏢 Компания: {order['company_name']}\n"
                f"📅 Подписка до: {expires_at.strftime('%d.%m.%Y')}\n\n"
                f"✅ Бот активирован и готов к работе!\n"
                f"✅ База данных создана\n"
                f"✅ Все настройки применены\n\n"
                f"📱 Откройте {bot_username} и отправьте /start\n\n"
                f"💡 Если нужна помощь - обращайтесь в поддержку!",
                parse_mode="HTML"
            )
            
            logger.info(f"✅ Bot activated: {client_id} for user {user_id}")
        
        else:
            await bot.send_message(
                user_id,
                "❌ Ошибка активации бота.\n"
                "Обратитесь в поддержку."
            )
            orders[order_id]['status'] = 'activation_failed'
    
    except Exception as e:
        logger.error(f"❌ Error processing payment: {e}", exc_info=True)
        await bot.send_message(
            user_id,
            f"❌ Ошибка: {e}\n\n"
            f"Обратитесь в поддержку."
        )
        orders[order_id]['status'] = 'error'
        orders[order_id]['error'] = str(e)

@dp.callback_query(F.data == "cancel_purchase")
async def cancel_purchase(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "❌ Покупка отменена.\n\n"
        "Для повторной попытки отправьте /start"
    )

@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await cmd_start(callback.message, state)

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    total_orders = len(orders)
    paid_orders = len([o for o in orders.values() if o['status'] in ['paid', 'activated']])
    activated_orders = len([o for o in orders.values() if o['status'] == 'activated'])
    total_revenue = sum(o.get('amount', 0) for o in orders.values() if o['status'] in ['paid', 'activated'])
    
    await message.answer(
        f"📊 <b>Статистика Sales Bot</b>\n\n"
        f"📝 Всего заказов: <b>{total_orders}</b>\n"
        f"💳 Оплачено: <b>{paid_orders}</b>\n"
        f"✅ Активировано: <b>{activated_orders}</b>\n"
        f"💰 Выручка: <b>{total_revenue} ₽</b>",
        parse_mode="HTML"
    )

async def main():
    try:
        logger.info("✅ Sales Bot started successfully!")
        logger.info("👂 Listening for messages...")
        
        await dp.start_polling(bot)
    
    except Exception as e:
        logger.error(f"❌ Sales Bot crashed: {e}", exc_info=True)
    
    finally:
        await bot.session.close()
        logger.info("👋 Sales Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
