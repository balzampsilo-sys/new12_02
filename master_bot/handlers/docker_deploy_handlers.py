#!/usr/bin/env python3
"""
🐳 Docker автономный деплой - хэндлеры для Master Bot

Особенности:
- Master Bot самостоятельно создаёт Docker контейнеры
- Не требует Deploy Worker
- Работает напрямую через Docker API
- Автоматический rollback при ошибках
"""

import sys
import os
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

# Добавить automation/ в путь
project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(project_root / "automation"))

from automation.docker_deploy_manager import DockerDeployManager
from config import Config

logger = logging.getLogger(__name__)

# Инициализация Docker Deploy Manager
try:
    docker_deploy = DockerDeployManager(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql://booking_user:SecurePass2026!@postgres:5432/booking_saas"
        ),
        schema=os.getenv("PG_SCHEMA", "master_bot")
    )
    DOCKER_AVAILABLE = True
    logger.info("✅ DockerDeployManager initialized successfully")
except Exception as e:
    DOCKER_AVAILABLE = False
    logger.error(f"❌ Failed to initialize DockerDeployManager: {e}")


# Router
router = Router()


# === FSM STATES ===
class DockerDeployStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_admin_id = State()
    waiting_for_company_name = State()
    waiting_for_confirmation = State()


class ManageClientStates(StatesGroup):
    waiting_for_action = State()
    waiting_for_client_search = State()


# === КЛАВИАТУРЫ ===
def docker_menu_keyboard():
    keyboard = [
        [KeyboardButton(text="🚀 Создать бота (быстро)")],
        [KeyboardButton(text="🐳 Список Docker контейнеров")],
        [KeyboardButton(text="🔧 Управление клиентом")],
        [KeyboardButton(text="🔙 Главное меню")]
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


def client_actions_keyboard():
    keyboard = [
        [KeyboardButton(text="⏸️ Остановить")],
        [KeyboardButton(text="🔄 Перезапустить")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="❌ Удалить")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# === КОМАНДЫ ===
@router.message(F.text == "🐳 Docker Деплой")
async def show_docker_menu(message: Message):
    """Docker меню"""
    if not DOCKER_AVAILABLE:
        await message.answer(
            "❌ DOCKER НЕДОСТУПЕН\n\n"
            "Проверьте:\n"
            "1. Docker Desktop запущен\n"
            "2. TCP включён в Settings\n"
            "3. Модуль docker установлен"
        )
        return
    
    await message.answer(
        "🐳 DOCKER АВТОНОМНЫЙ ДЕПЛОЙ\n\n"
        "🚀 Master Bot создаёт клиентских ботов самостоятельно!\n\n"
        "✅ Быстрый деплой (30-60 сек)\n"
        "✅ Автоматический rollback\n"
        "✅ Real-time мониторинг\n\n"
        "Выберите действие:",
        reply_markup=docker_menu_keyboard()
    )


# === СОЗДАНИЕ БОТА ===
@router.message(F.text == "🚀 Создать бота (быстро)")
async def start_docker_deploy(message: Message, state: FSMContext):
    """ Начать быстрый деплой через Docker API"""
    
    if not DOCKER_AVAILABLE:
        await message.answer("❌ Docker недоступен")
        return
    
    await state.set_state(DockerDeployStates.waiting_for_token)
    await message.answer(
        "🚀 БЫСТРЫЙ ДЕПЛОЙ\n\n"
        "Шаг 1/3: Отправьте токен бота\n\n"
        "🔑 Как получить:\n"
        "1. @BotFather → /newbot\n"
        "2. Копируйте токен\n\n"
        "📝 Отправьте токен:",
        reply_markup=cancel_keyboard()
    )


@router.message(DockerDeployStates.waiting_for_token)
async def process_docker_token(message: Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=docker_menu_keyboard())
        return
    
    token = message.text.strip()
    
    if ":" not in token or len(token) < 20:
        await message.answer(
            "❌ Неверный формат токена\n\n"
            "📝 Формат: 123456789:ABC-DEF...\n\n"
            "Попробуйте ещё раз:"
        )
        return
    
    await state.update_data(bot_token=token)
    await state.set_state(DockerDeployStates.waiting_for_admin_id)
    await message.answer(
        "✅ Токен принят\n\n"
        "Шаг 2/3: Отправьте Telegram ID администратора\n\n"
        "👤 Как узнать:\n"
        "1. @userinfobot → /start\n"
        "2. Скопируйте ID\n\n"
        "📝 Отправьте ID:"
    )


@router.message(DockerDeployStates.waiting_for_admin_id)
async def process_docker_admin_id(message: Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=docker_menu_keyboard())
        return
    
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ ID должен быть числом\n\n"
            "📝 Пример: 987654321\n\n"
            "Попробуйте ещё раз:"
        )
        return
    
    await state.update_data(admin_telegram_id=admin_id)
    await state.set_state(DockerDeployStates.waiting_for_company_name)
    await message.answer(
        "✅ ID принят\n\n"
        "Шаг 3/3: Введите название компании\n\n"
        "🏪 Примеры:\n"
        "- Салон красоты Анны\n"
        "- Барбершоп Max\n"
        "- Фитнес-студия\n\n"
        "📝 Введите название:"
    )


@router.message(DockerDeployStates.waiting_for_company_name)
async def process_docker_company_name(message: Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=docker_menu_keyboard())
        return
    
    company_name = message.text.strip()
    await state.update_data(company_name=company_name)
    data = await state.get_data()
    
    confirmation_text = f"""📋 ПОДТВЕРЖДЕНИЕ ДЕПЛОЯ

🏪 Компания: {data['company_name']}
🤖 Токен: {data['bot_token'][:20]}...
👤 Admin ID: {data['admin_telegram_id']}
📅 Подписка: 30 дней

⚡ Деплой займёт 30-60 секунд.
🐳 Master Bot создаст Docker контейнер автоматически.

Продолжить?"""
    
    await state.set_state(DockerDeployStates.waiting_for_confirmation)
    await message.answer(
        confirmation_text,
        reply_markup=confirm_keyboard()
    )


@router.message(DockerDeployStates.waiting_for_confirmation)
async def process_docker_confirmation(message: Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=docker_menu_keyboard())
        return
    
    if message.text != "✅ Подтвердить":
        await message.answer("Нажмите кнопку подтверждения")
        return
    
    data = await state.get_data()
    
    # Запустить деплой
    await message.answer(
        "⏳ ЗАПУСК ДЕПЛОЯ...\n\n"
        "🐳 Создаю PostgreSQL schema\n"
        "📊 Выделяю Redis DB\n"
        "📦 Запускаю Docker контейнер...\n\n"
        "⚙️ Это может занять 30-60 секунд."
    )
    
    try:
        # Деплой через DockerDeployManager
        result = await docker_deploy.deploy_client(
            bot_token=data['bot_token'],
            admin_telegram_id=data['admin_telegram_id'],
            company_name=data['company_name'],
            subscription_days=30
        )
        
        if result['success']:
            success_text = f"""✅ БОТ УСПЕШНО РАЗВЁРНУТ!

🏪 Компания:      {result['company_name']}
🆔 Client ID:    {result['client_id']}
🐳 Container:    {result['container_name']}
📊 Redis DB:     {result['redis_db']}
🗄️  Schema:       {result['schema']}
👤 Admin ID:     {result['admin_telegram_id']}

✅ Бот работает 24/7 в Docker!

📋 Команды для проверки:
• docker logs {result['container_name']}
• docker ps --filter name={result['container_name']}"""
            
            await message.answer(success_text)
            logger.info(f"✅ Successfully deployed {result['company_name']} - {result['container_name']}")
        else:
            error_text = f"""❌ ОШИБКА ДЕПЛОЯ

❌ {result['error']}

🔄 Rollback выполнен автоматически.

📝 Проверьте:
1. Токен бота корректен
2. PostgreSQL доступен
3. Redis доступен
4. Docker работает"""
            
            await message.answer(error_text)
            logger.error(f"❌ Deploy failed for {data['company_name']}: {result['error']}")
    
    except Exception as e:
        logger.error(f"Critical error during deploy: {e}", exc_info=True)
        await message.answer(
            f"❌ КРИТИЧЕСКАЯ ОШИБКА\n\n"
            f"{type(e).__name__}: {str(e)}\n\n"
            "🔧 Обратитесь к техподдержке"
        )
    
    finally:
        await state.clear()
        await message.answer(
            "Выберите действие:",
            reply_markup=docker_menu_keyboard()
        )


# === СПИСОК КОНТЕЙНЕРОВ ===
@router.message(F.text == "🐳 Список Docker контейнеров")
async def list_docker_containers(message: Message):
    """ Показать все клиентские контейнеры"""
    
    if not DOCKER_AVAILABLE:
        await message.answer("❌ Docker недоступен")
        return
    
    try:
        import docker
        client = docker.from_env()
        
        # Получить все контейнеры с меткой managed_by=master_bot
        containers = client.containers.list(
            all=True,
            filters={"label": "managed_by=master_bot"}
        )
        
        if not containers:
            await message.answer(
                "📦 Клиентских контейнеров пока нет\n\n"
                "🚀 Создайте первого бота!"
            )
            return
        
        container_list = f"🐳 DOCKER КОНТЕЙНЕРЫ ({len(containers)})\n\n"
        
        for container in containers:
            status_emoji = {
                'running': '✅',
                'exited': '❌',
                'paused': '⏸️',
                'restarting': '🔄'
            }.get(container.status, '❓')
            
            # Получить метки
            labels = container.labels
            company = labels.get('company_name', 'Unknown')
            
            container_list += f"{status_emoji} {container.name}\n"
            container_list += f"   🏪 {company}\n"
            container_list += f"   📊 Status: {container.status}\n\n"
        
        await message.answer(container_list)
    
    except Exception as e:
        logger.error(f"Error listing containers: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")


# === УПРАВЛЕНИЕ КЛИЕНТОМ ===
@router.message(F.text == "🔧 Управление клиентом")
async def start_manage_client(message: Message, state: FSMContext):
    """ Начать управление клиентом"""
    
    if not DOCKER_AVAILABLE:
        await message.answer("❌ Docker недоступен")
        return
    
    await state.set_state(ManageClientStates.waiting_for_client_search)
    await message.answer(
        "🔍 ПОИСК КЛИЕНТА\n\n"
        "Введите название компании:\n"
        "(можно часть названия)",
        reply_markup=cancel_keyboard()
    )


@router.message(ManageClientStates.waiting_for_client_search)
async def process_client_search(message: Message, state: FSMContext):
    if message.text == "🚫 Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=docker_menu_keyboard())
        return
    
    # TODO: Реализовать поиск и управление
    await message.answer(
        "🚧 Функция в разработке\n\n"
        "🔜 Пока используйте Docker команды:",
        reply_markup=docker_menu_keyboard()
    )
    await state.clear()


@router.message(F.text == "🔙 Главное меню")
async def back_to_main(message: Message, state: FSMContext):
    """ Вернуться в главное меню"""
    await state.clear()
    # Вызов главного меню из master_bot.py
    from master_bot import main_menu_keyboard
    await message.answer(
        "🏠 Главное меню",
        reply_markup=main_menu_keyboard()
    )
