#!/usr/bin/env python3
"""
Sales Bot - Автоматическая продажа подписок на ботов

Функции:
- Демо-режим для потенциальных клиентов
- Прием оплаты через Telegram Stars
- Автоматическое создание и деплой бота
- Интеграция с Master Bot
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
import requests

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
    LabeledPrice,
    PreCheckoutQuery,
    Message
)

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
MASTER_BOT_API_URL = os.getenv("MASTER_BOT_API_URL", "http://localhost:8000")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "YourSupport")

if not SALES_BOT_TOKEN:
    raise ValueError("SALES_BOT_TOKEN not set in environment")

# Инициализация
bot = Bot(token=SALES_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

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
                text=f"🔵 {PRICING['3m']['name']} - {PRICING['3m']['price']}₽ 💎 Экономия {PRICING['3m']['savings']}₽",
                callback_data="buy_3m"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🟣 {PRICING['6m']['name']} - {PRICING['6m']['price']}₽ 💎 Экономия {PRICING['6m']['savings']}₽",
                callback_data="buy_6m"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"⭐ {PRICING['12m']['name']} - {PRICING['12m']['price']}₽ 💎 Экономия {PRICING['12m']['savings']}₽",
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
    
    # Создать invoice для оплаты через Telegram Stars
    prices = [
        LabeledPrice(
            label=f"Подписка {plan_info['name']}",
            amount=plan_info['price'] * 100  # В копейках для Stars
        )
    ]
    
    await bot.send_invoice(
        chat_id=message.chat.id,
        title=f"Подписка на бота - {plan_info['name']}",
        description=f"Бот для записи клиентов '{company_name}' на {plan_info['days']} дней",
        payload=f"subscription_{plan}_{message.from_user.id}",
        provider_token="",  # Empty for Telegram Stars
        currency="XTR",  # Telegram Stars
        prices=prices,
        start_parameter="bot_subscription"
    )
    
    await message.answer(
        "💳 Счет на оплату отправлен выше ⬆️\n\n"
        "После оплаты бот будет создан автоматически за 2 минуты!"
    )


# === ОБРАБОТКА ОПЛАТЫ ===
@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение возможности оплаты"""
    await bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=True
    )


@dp.message(F.successful_payment)
async def process_successful_payment(message: Message, state: FSMContext):
    """Обработка успешной оплаты"""
    payment = message.successful_payment
    data = await state.get_data()
    
    plan = data.get('plan')
    company_name = data.get('company_name')
    plan_info = PRICING[plan]
    
    logger.info(f"Payment received: {payment.total_amount} XTR from {message.from_user.id}")
    
    # Уведомление о начале создания
    processing_msg = await message.answer(
        "✅ **Оплата получена!**\n\n"
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
        #     admin_telegram_id=message.from_user.id,
        #     company_name=company_name,
        #     subscription_days=plan_info['days'],
        #     paid_amount=plan_info['price']
        # )
        
        # Для демо создаем заглушку
        bot_username = f"booking_{message.from_user.id}_bot"
        
        await processing_msg.delete()
        
        success_text = f"""
🎉 **ВАШ БОТ ГОТОВ!**

🤖 Бот: @{bot_username}
🏢 Название: {company_name}
📅 Подписка: {plan_info['days']} дней
💰 Оплачено: {plan_info['price']}₽

**Что делать дальше:**

1️⃣ Откройте бота: @{bot_username}
2️⃣ Нажмите /start
3️⃣ Настройте расписание и услуги
4️⃣ Поделитесь ссылкой с клиентами

📚 **Инструкция:** https://docs.example.com
💬 **Поддержка:** @{SUPPORT_USERNAME}

✨ Спасибо за покупку! Ваш бот уже работает 24/7
        """
        
        await message.answer(
            success_text,
            parse_mode="Markdown"
        )
        
        # Уведомление админу (в Master Bot)
        # TODO: Отправить уведомление админу о новой продаже
        
    except Exception as e:
        logger.error(f"Error creating bot: {e}", exc_info=True)
        await message.answer(
            f"❌ Произошла ошибка при создании бота.\n\n"
            f"Не волнуйтесь, ваша оплата сохранена!\n"
            f"Напишите в поддержку: @{SUPPORT_USERNAME}\n\n"
            f"ID платежа: {payment.telegram_payment_charge_id}"
        )
    
    await state.clear()


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
    logger.info("🚀 Sales Bot starting...")
    logger.info(f"Support: @{SUPPORT_USERNAME}")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Sales Bot stopped")
