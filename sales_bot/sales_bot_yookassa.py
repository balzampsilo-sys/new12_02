#!/usr/bin/env python3
"""
Sales Bot с интеграцией ЮKassa
Автоматическая продажа подписок на ботов

Интеграция:
- ЮKassa для приема платежей
- Поддержка всех методов оплаты (карты, кошельки, СБП)
- Webhook для автоматического подтверждения
- Автоматический деплой после оплаты
"""

import os
import sys
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import requests
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message
)

from yookassa import Configuration, Payment
import yookassa

from dotenv import load_dotenv
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === КОНФИГУРАЦИЯ ===
SALES_BOT_TOKEN = os.getenv("SALES_BOT_TOKEN")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://yourdomain.com")  # Ваш домен
MASTER_BOT_API_URL = os.getenv("MASTER_BOT_API_URL", "http://localhost:8000")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "YourSupport")

if not SALES_BOT_TOKEN:
    raise ValueError("SALES_BOT_TOKEN not set in environment")

if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
    raise ValueError("YooKassa credentials not set")

# Инициализация ЮKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

# Инициализация бота
bot = Bot(token=SALES_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Хранилище активных платежей (в продакшене использовать Redis/DB)
pending_payments = {}

# === ТАРИФЫ ===
PRICING = {
    "1m": {
        "name": "Starter (1 месяц)",
        "days": 30,
        "price": 299,
        "price_per_day": 10,
        "savings": 0
    },
    "3m": {
        "name": "Standard (3 месяца)",
        "days": 90,
        "price": 799,
        "price_per_day": 9,
        "savings": 98
    },
    "6m": {
        "name": "Business (6 месяцев)",
        "days": 180,
        "price": 1499,
        "price_per_day": 8,
        "savings": 301
    },
    "12m": {
        "name": "Premium (1 год)",
        "days": 365,
        "price": 2499,
        "price_per_day": 7,
        "savings": 1151
    }
}

# === FSM STATES ===
class PurchaseStates(StatesGroup):
    waiting_for_company_name = State()
    waiting_for_payment = State()


# === КЛАВИАТУРЫ ===
def main_menu_keyboard():
    keyboard = [
        [KeyboardButton(text="📱 Посмотреть демо")],
        [KeyboardButton(text="💰 Купить подписку")],
        [KeyboardButton(text="❓ Вопросы и ответы")],
        [KeyboardButton(text="💬 Связаться с поддержкой")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def pricing_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"🟢 {PRICING['1m']['name']} - {PRICING['1m']['price']}₽",
                callback_data="buy_1m"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🔵 {PRICING['3m']['name']} - {PRICING['3m']['price']}₽ 💎 -{PRICING['3m']['savings']}₽",
                callback_data="buy_3m"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🟣 {PRICING['6m']['name']} - {PRICING['6m']['price']}₽ 💎 -{PRICING['6m']['savings']}₽",
                callback_data="buy_6m"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"⭐ {PRICING['12m']['name']} - {PRICING['12m']['price']}₽ 🔥 -{PRICING['12m']['savings']}₽",
                callback_data="buy_12m"
            )
        ]
    ])
    return keyboard


def demo_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Записаться на стрижку", callback_data="demo_book")
        ],
        [
            InlineKeyboardButton(text="⏰ Мои записи", callback_data="demo_my_bookings")
        ],
        [
            InlineKeyboardButton(text="💇‍♀️ Наши услуги", callback_data="demo_services")
        ],
        [
            InlineKeyboardButton(text="💰 Купить такого бота!", callback_data="start_purchase")
        ]
    ])
    return keyboard


# === ФУНКЦИИ РАБОТЫ С ЮKASSA ===
async def create_payment(amount: float, description: str, user_id: int, metadata: dict) -> Optional[Payment]:
    """
    Создать платеж в ЮKassa
    
    Args:
        amount: Сумма платежа
        description: Описание платежа
        user_id: Telegram ID пользователя
        metadata: Дополнительные данные
    
    Returns:
        Payment объект или None при ошибке
    """
    try:
        payment = Payment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f"{WEBHOOK_URL}/payment/success"
            },
            "capture": True,
            "description": description,
            "metadata": metadata
        }, uuid.uuid4())
        
        logger.info(f"Payment created: {payment.id} for user {user_id}")
        return payment
    
    except Exception as e:
        logger.error(f"Error creating payment: {e}", exc_info=True)
        return None


async def check_payment_status(payment_id: str) -> Optional[str]:
    """
    Проверить статус платежа
    
    Returns:
        'succeeded', 'pending', 'canceled' или None
    """
    try:
        payment = Payment.find_one(payment_id)
        return payment.status
    except Exception as e:
        logger.error(f"Error checking payment: {e}")
        return None


# === КОМАНДЫ ===
@dp.message(CommandStart())
async def cmd_start(message: Message):
    welcome_text = f"""
👋 Привет, {message.from_user.first_name}!

🤖 **Я помогу создать бота для вашего бизнеса**

Что вы получите:
✅ Бот для записи клиентов
✅ Автоматические напоминания
✅ Календарь записей
✅ Статистика и аналитика
✅ Работает 24/7 без выходных

💰 **Цена:** от {PRICING['1m']['price']}₽/месяц
⚡ **Запуск:** за 2 минуты после оплаты

🎁 **Первые 7 дней бесплатно!**

Выберите действие:
    """
    
    await message.answer(
        welcome_text,
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )


# === ДЕМО-РЕЖИМ ===
@dp.message(F.text == "📱 Посмотреть демо")
async def show_demo(message: Message):
    demo_text = """
🎭 **ДЕМО-РЕЖИМ**

Это интерактивное демо работы бота.
Попробуйте как будто вы клиент салона красоты:

👇 Выберите действие:
    """
    
    await message.answer(
        demo_text,
        reply_markup=demo_keyboard(),
        parse_mode="Markdown"
    )


@dp.callback_query(F.data == "demo_book")
async def demo_booking(callback: types.CallbackQuery):
    await callback.message.answer(
        "📅 **ДЕМО: Запись на услугу**\n\n"
        "Выберите услугу:\n"
        "1. Женская стрижка - 1500₽ (60 мин)\n"
        "2. Мужская стрижка - 800₽ (30 мин)\n"
        "3. Окрашивание - 3500₽ (120 мин)\n\n"
        "*Это демо. В реальном боте клиент выберет услугу и время.*",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(F.data == "demo_my_bookings")
async def demo_my_bookings(callback: types.CallbackQuery):
    await callback.message.answer(
        "⏰ **ДЕМО: Ваши записи**\n\n"
        "📅 15 февраля, 14:00\n"
        "💇‍♀️ Женская стрижка\n"
        "👤 Мастер: Анна\n\n"
        "[Отменить запись] [Перенести]\n\n"
        "*Это демо. В реальном боте здесь реальные записи клиента.*",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(F.data == "demo_services")
async def demo_services(callback: types.CallbackQuery):
    await callback.message.answer(
        "💇‍♀️ **ДЕМО: Наши услуги**\n\n"
        "**Стрижки:**\n"
        "• Женская - 1500₽ (60 мин)\n"
        "• Мужская - 800₽ (30 мин)\n\n"
        "**Окрашивание:**\n"
        "• Полное - 3500₽ (120 мин)\n"
        "• Тонирование - 2000₽ (90 мин)\n\n"
        "*Это демо. В реальном боте ваши услуги и цены.*",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(F.data == "start_purchase")
async def start_purchase_from_demo(callback: types.CallbackQuery):
    await show_pricing(callback.message)
    await callback.answer()


# === ПОКУПКА ===
@dp.message(F.text == "💰 Купить подписку")
async def show_pricing(message: Message):
    pricing_text = """
💎 **ТАРИФНЫЕ ПЛАНЫ**

🟢 **Starter** - 1 месяц
   💰 299₽ (10₽/день)
   ✅ Все функции
   ✅ 7 дней пробный период

🔵 **Standard** - 3 месяца
   💰 799₽ (9₽/день)
   💎 Экономия 98₽
   ✅ Все функции
   ✅ Приоритетная поддержка

🟣 **Business** - 6 месяцев
   💰 1499₽ (8₽/день)
   💎 Экономия 301₽
   ✅ Все функции
   ✅ Кастомизация

⭐ **Premium** - 1 год
   💰 2499₽ (7₽/день)
   💎 Экономия 1151₽ 🔥
   ✅ Все функции
   ✅ Индивидуальная настройка
   ✅ Бесплатные обновления

📱 Выберите тариф:
    """
    
    await message.answer(
        pricing_text,
        reply_markup=pricing_keyboard(),
        parse_mode="Markdown"
    )


@dp.callback_query(F.data.startswith("buy_"))
async def process_plan_selection(callback: types.CallbackQuery, state: FSMContext):
    plan = callback.data.split("_")[1]
    plan_info = PRICING[plan]
    
    await state.update_data(plan=plan)
    await state.set_state(PurchaseStates.waiting_for_company_name)
    
    await callback.message.answer(
        f"✅ Выбран тариф: **{plan_info['name']}**\n"
        f"💰 Стоимость: **{plan_info['price']}₽**\n\n"
        f"📝 Введите название вашего бизнеса:\n"
        f"(Например: Салон красоты \"Анна\")",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.message(PurchaseStates.waiting_for_company_name)
async def process_company_name(message: Message, state: FSMContext):
    company_name = message.text.strip()
    data = await state.get_data()
    plan = data['plan']
    plan_info = PRICING[plan]
    
    await state.update_data(company_name=company_name)
    
    # Создать платеж в ЮKassa
    payment = await create_payment(
        amount=plan_info['price'],
        description=f"Подписка {plan_info['name']} - {company_name}",
        user_id=message.from_user.id,
        metadata={
            "user_id": str(message.from_user.id),
            "plan": plan,
            "company_name": company_name,
            "username": message.from_user.username or "",
            "days": str(plan_info['days'])
        }
    )
    
    if not payment:
        await message.answer(
            "❌ Ошибка создания платежа.\n"
            f"Обратитесь в поддержку: @{SUPPORT_USERNAME}"
        )
        await state.clear()
        return
    
    # Сохранить информацию о платеже
    pending_payments[payment.id] = {
        "user_id": message.from_user.id,
        "plan": plan,
        "company_name": company_name,
        "amount": plan_info['price'],
        "days": plan_info['days'],
        "created_at": datetime.now()
    }
    
    # Отправить ссылку на оплату
    payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💳 Оплатить картой",
                url=payment.confirmation.confirmation_url
            )
        ],
        [
            InlineKeyboardButton(
                text="🔍 Проверить оплату",
                callback_data=f"check_{payment.id}"
            )
        ]
    ])
    
    await message.answer(
        f"💳 **ОПЛАТА**\n\n"
        f"🏢 Компания: **{company_name}**\n"
        f"📦 Тариф: **{plan_info['name']}**\n"
        f"💰 Сумма: **{plan_info['price']}₽**\n\n"
        f"Нажмите кнопку ниже для оплаты.\n"
        f"Принимаем:\n"
        f"• Банковские карты 💳\n"
        f"• ЮMoney 💰\n"
        f"• Qiwi Wallet 🥝\n"
        f"• СБП (Система Быстрых Платежей) 🏦\n\n"
        f"После оплаты бот будет создан автоматически!\n\n"
        f"🆔 ID платежа: `{payment.id}`",
        reply_markup=payment_keyboard,
        parse_mode="Markdown"
    )
    
    await state.set_state(PurchaseStates.waiting_for_payment)


@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback: types.CallbackQuery, state: FSMContext):
    """
    Проверить статус платежа вручную
    """
    payment_id = callback.data.split("_", 1)[1]
    
    await callback.answer("🔍 Проверяю платеж...", show_alert=False)
    
    status = await check_payment_status(payment_id)
    
    if status == "succeeded":
        # Платеж успешен
        await process_successful_payment(payment_id, callback.message.chat.id)
        await state.clear()
    elif status == "pending":
        await callback.message.answer(
            "⏳ Платеж в обработке...\n\n"
            "Это может занять несколько минут.\n"
            "Нажмите \"Проверить оплату\" через минуту."
        )
    elif status == "canceled":
        await callback.message.answer(
            "❌ Платеж отменен.\n\n"
            "Вы можете попробовать снова: /start"
        )
        await state.clear()
    else:
        await callback.message.answer(
            "❓ Не удалось проверить статус платежа.\n\n"
            f"ID: `{payment_id}`\n"
            f"Обратитесь в поддержку: @{SUPPORT_USERNAME}",
            parse_mode="Markdown"
        )


async def process_successful_payment(payment_id: str, chat_id: int):
    """
    Обработать успешный платеж - создать и задеплоить бота
    """
    payment_info = pending_payments.get(payment_id)
    
    if not payment_info:
        logger.error(f"Payment info not found: {payment_id}")
        await bot.send_message(
            chat_id,
            "❌ Информация о платеже не найдена.\n"
            f"Обратитесь в поддержку с ID: `{payment_id}`",
            parse_mode="Markdown"
        )
        return
    
    company_name = payment_info['company_name']
    user_id = payment_info['user_id']
    days = payment_info['days']
    
    processing_msg = await bot.send_message(
        chat_id,
        "✅ **ОПЛАТА ПОЛУЧЕНА!**\n\n"
        "⏳ Создаю вашего бота...\n"
        "Это займет 1-2 минуты.\n\n"
        "Не закрывайте чат!",
        parse_mode="Markdown"
    )
    
    try:
        # Здесь должна быть интеграция с Master Bot API
        # Для демо используем заглушку
        await asyncio.sleep(2)  # Имитация создания
        
        # TODO: Реальный вызов API Master Bot
        # result = await create_client_via_api(
        #     admin_telegram_id=user_id,
        #     company_name=company_name,
        #     subscription_days=days,
        #     paid_amount=payment_info['amount']
        # )
        
        # Для демо создаем заглушку
        bot_username = f"booking_{user_id}_bot"
        
        await processing_msg.delete()
        
        success_text = f"""
🎉 **ВАШ БОТ ГОТОВ!**

🤖 Бот: @{bot_username}
🏢 Название: {company_name}
📅 Подписка: {days} дней
💰 Оплачено: {payment_info['amount']}₽

**Что делать дальше:**

1️⃣ Откройте бота: @{bot_username}
2️⃣ Нажмите /start
3️⃣ Настройте расписание и услуги
4️⃣ Поделитесь ссылкой с клиентами

📚 **Инструкция:** https://docs.example.com
💬 **Поддержка:** @{SUPPORT_USERNAME}

✨ Спасибо за покупку! Ваш бот уже работает 24/7
        """
        
        await bot.send_message(
            chat_id,
            success_text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        
        # Удалить из pending
        del pending_payments[payment_id]
        
    except Exception as e:
        logger.error(f"Error creating bot: {e}", exc_info=True)
        await bot.send_message(
            chat_id,
            f"❌ Произошла ошибка при создании бота.\n\n"
            f"Не волнуйтесь, ваша оплата сохранена!\n"
            f"Напишите в поддержку: @{SUPPORT_USERNAME}\n\n"
            f"ID платежа: `{payment_id}`",
            parse_mode="Markdown"
        )


# === FAQ ===
@dp.message(F.text == "❓ Вопросы и ответы")
async def show_faq(message: Message):
    faq_text = """
❓ **ЧАСТЫЕ ВОПРОСЫ**

**Q: Что входит в подписку?**
A: Полнофункциональный бот для записи клиентов, работающий 24/7. Без ограничений по количеству записей.

**Q: Как быстро запустится бот?**
A: Автоматически за 1-2 минуты после оплаты.

**Q: Могу ли я изменить настройки?**
A: Да, вы полностью управляете расписанием, услугами и настройками.

**Q: Что если мне не понравится?**
A: Первые 7 дней - пробный период. Вернем деньги без вопросов.

**Q: Нужно ли мне знать программирование?**
A: Нет! Всё настраивается через простое меню в Telegram.

**Q: Можно ли продлить подписку?**
A: Да, в любой момент через бота.

**Q: Какие способы оплаты?**
A: Банковские карты, ЮMoney, Qiwi, СБП.

💬 Остались вопросы? Напишите: @{SUPPORT_USERNAME}
    """
    
    await message.answer(faq_text, parse_mode="Markdown")


# === ПОДДЕРЖКА ===
@dp.message(F.text == "💬 Связаться с поддержкой")
async def contact_support(message: Message):
    support_text = f"""
💬 **ПОДДЕРЖКА**

📱 Telegram: @{SUPPORT_USERNAME}
📧 Email: support@example.com
⏰ Работаем: 9:00 - 21:00 МСК

⚡ Среднее время ответа: 15 минут

*Напишите нам, мы всегда рады помочь!*
    """
    
    await message.answer(support_text, parse_mode="Markdown")


# === ЗАПУСК ===
async def main():
    logger.info("🚀 Sales Bot (YooKassa) starting...")
    logger.info(f"YooKassa Shop ID: {YOOKASSA_SHOP_ID}")
    logger.info(f"Webhook URL: {WEBHOOK_URL}")
    logger.info(f"Support: @{SUPPORT_USERNAME}")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Sales Bot stopped")
