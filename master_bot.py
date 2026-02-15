#!/usr/bin/env python3
"""
Master Bot - Бот администратора
Мониторинг и управление пулом ботов
"""

import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

import sys
sys.path.insert(0, '/app')

from automation.bot_pool_manager import BotPoolManager

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

REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

logger.info("=" * 60)
logger.info("🔧 MASTER BOT STARTING")
logger.info("=" * 60)
logger.info(f"🤖 Token: {BOT_TOKEN[:20]}...")
logger.info(f"👥 Admins: {ADMIN_IDS}")
logger.info(f"📡 Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
logger.info("=" * 60)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Менеджер пула
pool_manager = BotPoolManager(
    redis_host=REDIS_HOST,
    redis_port=REDIS_PORT,
    redis_db=REDIS_DB,
    pool_size=100  # Максимум для проверки
)

def is_admin(user_id: int) -> bool:
    """Проверка что пользователь - админ"""
    return user_id in ADMIN_IDS

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        f"🔧 <b>Master Bot - Панель управления</b>\n\n"
        f"📊 <b>Доступные команды:</b>\n\n"
        f"/pool - Статус пула ботов\n"
        f"/stats - Общая статистика\n"
        f"/clients - Список клиентов\n"
        f"/help - Помощь",
        parse_mode="HTML"
    )

@dp.message(Command("pool"))
async def cmd_pool(message: Message):
    """Показать статус пула ботов"""
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        return
    
    try:
        status = await pool_manager.get_pool_status()
        
        text = f"🏊 <b>СТАТУС ПУЛА БОТОВ</b>\n\n"
        text += f"📊 Всего: <b>{status['total']}</b>\n"
        text += f"⚪ Свободно: <b>{status['waiting']}</b>\n"
        text += f"🟢 Занято: <b>{status['active']}</b>\n"
        text += f"⚫ Неизвестно: <b>{status['unknown']}</b>\n\n"
        
        if status['active'] > 0:
            text += f"🟢 <b>Активные боты:</b>\n"
            for bot in status['bots']:
                if bot['status'] == 'active':
                    text += f"• Pool #{bot['pool_id']}: {bot['client_id']}\n"
        
        await message.answer(text, parse_mode="HTML")
    
    except Exception as e:
        logger.error(f"❌ Error getting pool status: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Общая статистика"""
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        f"📊 <b>ОБЩАЯ СТАТИСТИКА</b>\n\n"
        f"👥 Всего клиентов: <b>0</b>\n"
        f"🟢 Активных подписок: <b>0</b>\n"
        f"💰 Выручка: <b>0 ₽</b>\n\n"
        f"⚠️ <i>Это тестовая версия</i>",
        parse_mode="HTML"
    )

@dp.message(Command("clients"))
async def cmd_clients(message: Message):
    """Список клиентов"""
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        f"👥 <b>СПИСОК КЛИЕНТОВ</b>\n\n"
        f"📄 Клиентов пока нет\n\n"
        f"⚠️ <i>Это тестовая версия</i>",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь"""
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        f"🔧 <b>MASTER BOT - Помощь</b>\n\n"
        f"📊 <b>Команды мониторинга:</b>\n"
        f"/pool - Показать статус пула ботов\n"
        f"/stats - Общая статистика системы\n"
        f"/clients - Список всех клиентов\n\n"
        f"🔍 <b>Информация:</b>\n"
        f"• Pool - пул готовых ботов\n"
        f"• WAITING - бот ждёт клиента\n"
        f"• ACTIVE - бот работает с клиентом\n\n"
        f"📞 <b>Поддержка:</b>\n"
        f"@your_support",
        parse_mode="HTML"
    )

@dp.message()
async def echo_handler(message: Message):
    """Обработка всех остальных сообщений"""
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        f"🤔 Не понимаю эту команду.\n\n"
        f"Используйте /help для справки."
    )

async def main():
    """Главная функция"""
    
    try:
        logger.info("✅ Master Bot started successfully!")
        logger.info("👂 Listening for commands...")
        
        await dp.start_polling(bot)
    
    except Exception as e:
        logger.error(f"❌ Master Bot crashed: {e}", exc_info=True)
    
    finally:
        await bot.session.close()
        logger.info("👋 Master Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
