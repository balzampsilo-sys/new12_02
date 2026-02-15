#!/usr/bin/env python3
"""
Deploy Handlers - Хэндлеры для деплоя клиентских ботов

Интегрируется с DockerDeployManager для автономного создания ботов
"""

import sys
from pathlib import Path

# Добавить automation/ в путь
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

try:
    from automation.docker_deploy_manager import DockerDeployManager
    DOCKER_DEPLOY_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ DockerDeployManager not available: {e}")
    DOCKER_DEPLOY_AVAILABLE = False

router = Router()

# FSM States
class DeployStates(StatesGroup):
    waiting_for_bot_token = State()
    waiting_for_admin_id = State()
    waiting_for_company_name = State()
    waiting_for_subscription_days = State()
    confirmation = State()

# Инициализация Docker Deploy Manager
if DOCKER_DEPLOY_AVAILABLE:
    deploy_manager = DockerDeployManager()
else:
    deploy_manager = None


# ===========================
# COMMAND: /deploy
# ===========================

@router.message(Command("deploy"))
async def cmd_deploy_start(message: Message, state: FSMContext):
    """Начать процесс деплоя нового бота"""
    if not DOCKER_DEPLOY_AVAILABLE:
        await message.answer(
            "❌ **Docker Deploy Manager недоступен**\n\n"
            "Установите зависимости:\n"
            "`pip install docker psycopg2-binary`",
            parse_mode="Markdown"
        )
        return
    
    await message.answer(
        "🚀 **Деплой нового бота**\n\n"
        "Отправьте **токен Telegram Bot** клиента:\n\n"
        "🔑 Пример: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`\n\n"
        "ℹ️ Получите токен у @BotFather",
        parse_mode="Markdown"
    )
    
    await state.set_state(DeployStates.waiting_for_bot_token)


@router.message(DeployStates.waiting_for_bot_token)
async def process_bot_token(message: Message, state: FSMContext):
    """Проверка и сохранение токена"""
    bot_token = message.text.strip()
    
    # Простая валидация
    if ":" not in bot_token or len(bot_token) < 40:
        await message.answer(
            "❌ **Неверный формат токена**\n\n"
            "Правильный формат: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`",
            parse_mode="Markdown"
        )
        return
    
    await state.update_data(bot_token=bot_token)
    
    await message.answer(
        "✅ Токен принят!\n\n"
        "👤 Теперь отправьте **Telegram ID администратора**:\n\n"
        "🔢 Пример: `123456789`\n\n"
        "ℹ️ Узнать ID можно через @userinfobot",
        parse_mode="Markdown"
    )
    
    await state.set_state(DeployStates.waiting_for_admin_id)


@router.message(DeployStates.waiting_for_admin_id)
async def process_admin_id(message: Message, state: FSMContext):
    """Проверка и сохранение admin ID"""
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ **Неверный формат**\n\n"
            "Telegram ID должен быть числом.\n"
            "Пример: `123456789`",
            parse_mode="Markdown"
        )
        return
    
    await state.update_data(admin_id=admin_id)
    
    await message.answer(
        "✅ Admin ID принят!\n\n"
        "🏢 Отправьте **название компании**:\n\n"
        "📝 Пример: `Салон красоты \"Beatyful\"`",
        parse_mode="Markdown"
    )
    
    await state.set_state(DeployStates.waiting_for_company_name)


@router.message(DeployStates.waiting_for_company_name)
async def process_company_name(message: Message, state: FSMContext):
    """Сохранение названия компании"""
    company_name = message.text.strip()
    
    if len(company_name) < 3:
        await message.answer(
            "❌ **Название слишком короткое**\n\n"
            "Минимум 3 символа.",
            parse_mode="Markdown"
        )
        return
    
    await state.update_data(company_name=company_name)
    
    await message.answer(
        "✅ Название принято!\n\n"
        "📅 Отправьте **количество дней подписки**:\n\n"
        "🔢 Пример: `30` (месяц)\n\n"
        "ℹ️ Или нажмите /skip для 30 дней по умолчанию",
        parse_mode="Markdown"
    )
    
    await state.set_state(DeployStates.waiting_for_subscription_days)


@router.message(DeployStates.waiting_for_subscription_days, Command("skip"))
@router.message(DeployStates.waiting_for_subscription_days)
async def process_subscription_days(message: Message, state: FSMContext):
    """Проверка и подтверждение"""
    if message.text == "/skip":
        subscription_days = 30
    else:
        try:
            subscription_days = int(message.text.strip())
            if subscription_days < 1 or subscription_days > 3650:  # Max 10 years
                await message.answer(
                    "❌ **Некорректное количество дней**\n\n"
                    "Введите число от 1 до 3650.",
                    parse_mode="Markdown"
                )
                return
        except ValueError:
            await message.answer(
                "❌ **Неверный формат**\n\n"
                "Введите число или /skip",
                parse_mode="Markdown"
            )
            return
    
    await state.update_data(subscription_days=subscription_days)
    
    # Получить все данные
    data = await state.get_data()
    
    # Подтверждение
    await message.answer(
        "📝 **Проверьте данные:**\n\n"
        f"🔑 **Bot Token:** `{data['bot_token'][:20]}...`\n"
        f"👤 **Admin ID:** `{data['admin_id']}`\n"
        f"🏢 **Компания:** {data['company_name']}\n"
        f"📅 **Подписка:** {subscription_days} дней\n\n"
        "❓ **Подтвердить деплой?**\n\n"
        "✅ /confirm - Да, запустить\n"
        "❌ /cancel - Отменить",
        parse_mode="Markdown"
    )
    
    await state.set_state(DeployStates.confirmation)


@router.message(DeployStates.confirmation, Command("confirm"))
async def process_deploy_confirm(message: Message, state: FSMContext):
    """Запустить деплой"""
    if not DOCKER_DEPLOY_AVAILABLE or not deploy_manager:
        await message.answer("❌ Docker Deploy Manager недоступен")
        await state.clear()
        return
    
    data = await state.get_data()
    
    # Отправить начало
    progress_msg = await message.answer(
        "⌛ **Запуск деплоя...**\n\n"
        "🔄 Выделение ресурсов...\n"
        "🔄 Создание PostgreSQL schema...\n"
        "🔄 Запуск Docker контейнера...\n\n"
        "⏳ Это может занять 30-60 секунд...",
        parse_mode="Markdown"
    )
    
    # Выполнить деплой
    try:
        result = await deploy_manager.deploy_client(
            bot_token=data['bot_token'],
            admin_telegram_id=data['admin_id'],
            company_name=data['company_name'],
            subscription_days=data['subscription_days']
        )
        
        if result['success']:
            await progress_msg.edit_text(
                "✅ **БОТ УСПЕШНО РАЗВЁРНУТ!**\n\n"
                f"🏢 **Компания:** {result['company_name']}\n"
                f"🆔 **Client ID:** `{result['client_id']}`\n"
                f"📊 **Redis DB:** {result['redis_db']}\n"
                f"📦 **Schema:** `{result['schema']}`\n"
                f"🐳 **Container:** `{result['container_name']}`\n\n"
                f"✅ Бот работает 24/7\n"
                f"✅ Автоматический перезапуск\n"
                f"✅ Полная изоляция данных\n\n"
                f"💬 Клиент может начинать использовать бота!",
                parse_mode="Markdown"
            )
            
            # Отправить уведомление клиенту
            try:
                from aiogram import Bot
                bot = Bot(token=data['bot_token'])
                await bot.send_message(
                    chat_id=data['admin_id'],
                    text=(
                        f"🎉 **Ваш бот готов!**\n\n"
                        f"✅ Бот развёрнут и работает\n"
                        f"✅ Вы можете начать использовать\n\n"
                        f"🚀 Нажмите /start для начала работы"
                    ),
                    parse_mode="Markdown"
                )
                await bot.session.close()
            except Exception as e:
                # Не критично
                print(f"Failed to notify client: {e}")
        
        else:
            await progress_msg.edit_text(
                "❌ **ОШИБКА ДЕПЛОЯ**\n\n"
                f"❌ {result['error']}\n\n"
                f"ℹ️ Обратитесь к техподдержке.",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        await progress_msg.edit_text(
            "❌ **КРИТИЧЕСКАЯ ОШИБКА**\n\n"
            f"❌ {str(e)}\n\n"
            "ℹ️ Проверьте логи сервера.",
            parse_mode="Markdown"
        )
    
    await state.clear()


@router.message(DeployStates.confirmation, Command("cancel"))
async def process_deploy_cancel(message: Message, state: FSMContext):
    """Отменить деплой"""
    await message.answer(
        "❌ Деплой отменён.\n\n"
        "ℹ️ Используйте /deploy для новой попытки."
    )
    await state.clear()


# ===========================
# COMMAND: /manage_clients
# ===========================

@router.message(Command("manage_clients"))
async def cmd_manage_clients(message: Message):
    """Управление клиентскими ботами"""
    if not DOCKER_DEPLOY_AVAILABLE or not deploy_manager:
        await message.answer("❌ Docker Deploy Manager недоступен")
        return
    
    # TODO: Реализовать список клиентов с кнопками
    await message.answer(
        "📋 **Управление клиентами**\n\n"
        "🔧 Функция в разработке...",
        parse_mode="Markdown"
    )
