#!/usr/bin/env python3
"""
Sales Bot - Бот для продажи подписок
Заглушка для тестирования системы
"""

import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получить токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not set!")
    exit(1)

ADMIN_IDS = os.getenv('ADMIN_IDS', '').split(',')
ADMIN_IDS = [int(aid.strip()) for aid in ADMIN_IDS if aid.strip()]

logger.info("=" * 60)
logger.info("💰 SALES BOT STARTING")
logger.info("=" * 60)
logger.info(f"🤖 Token: {BOT_TOKEN[:20]}...")
logger.info(f"👥 Admins: {ADMIN_IDS}")
logger.info("=" * 60)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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
            "✅ Белый label (ваш бренд)",
            "💸 Скидка 33%"
        ]
    }
}

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""
    
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

@dp.message(Command("tariffs"))
async def cmd_tariffs(message: Message):
    """Показать тарифы"""
    
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
                text=f"🛋️ {tariff['name']} - {tariff['price']} ₽",
                callback_data=f"buy_{tariff_id}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика (только для админов)"""
    
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        f"📊 <b>Статистика Sales Bot</b>\n\n"
        f"👥 Всего пользователей: <b>0</b>\n"
        f"💰 Продаж: <b>0</b>\n"
        f"💵 Выручка: <b>0 ₽</b>\n\n"
        f"⚠️ <i>Это тестовая версия</i>",
        parse_mode="HTML"
    )

@dp.message()
async def echo_handler(message: Message):
    """Обработка всех остальных сообщений"""
    await message.answer(
        f"🤔 Не понимаю эту команду.\n\n"
        f"Используйте:\n"
        f"/start - Главное меню\n"
        f"/tariffs - Тарифы\n"
        f"/stats - Статистика (для админов)"
    )

async def main():
    """Главная функция"""
    
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
