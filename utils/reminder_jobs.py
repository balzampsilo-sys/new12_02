"""Module-level reminder job functions for APScheduler

Эти функции должны быть на уровне модуля, чтобы APScheduler
мог их сериализовать в PostgreSQL jobstore.

ДО: Функции были внутри setup_reminder_jobs() -> ошибка сериализации
ПОСЛЕ: Функции на уровне модуля -> APScheduler может их сохранить в БД
"""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot

from services.reminder_service import ReminderService

logger = logging.getLogger(__name__)

# Глобальная переменная для Bot instance
_bot_instance = None


def set_bot_instance(bot: 'Bot'):
    """Установить Bot instance для использования в job функциях
    
    Args:
        bot: Aiogram Bot instance
    """
    global _bot_instance
    _bot_instance = bot
    logger.info("✅ Bot instance set for reminder jobs")


def reminder_24h_job():
    """Синхронный wrapper для отправки напоминаний за 24 часа
    
    Вызывается APScheduler каждый день в 10:00
    """
    try:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_reminder_24h_async())
        except RuntimeError:
            logger.critical(
                "❌ No running event loop in reminder_24h_job! "
                "This should never happen in APScheduler context."
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_reminder_24h_async())
            finally:
                loop.close()
    except Exception as e:
        logger.error(f"❌ Reminder 24h job wrapper failed: {e}", exc_info=True)


def reminder_2h_job():
    """Синхронный wrapper для отправки напоминаний за 2 часа
    
    Вызывается APScheduler каждые 2 часа
    """
    try:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_reminder_2h_async())
        except RuntimeError:
            logger.critical(
                "❌ No running event loop in reminder_2h_job! "
                "This should never happen in APScheduler context."
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_reminder_2h_async())
            finally:
                loop.close()
    except Exception as e:
        logger.error(f"❌ Reminder 2h job wrapper failed: {e}", exc_info=True)


def reminder_1h_job():
    """Синхронный wrapper для отправки напоминаний за 1 час
    
    Вызывается APScheduler каждый час
    """
    try:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_reminder_1h_async())
        except RuntimeError:
            logger.critical(
                "❌ No running event loop in reminder_1h_job! "
                "This should never happen in APScheduler context."
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_reminder_1h_async())
            finally:
                loop.close()
    except Exception as e:
        logger.error(f"❌ Reminder 1h job wrapper failed: {e}", exc_info=True)


async def _reminder_24h_async():
    """Async логика отправки напоминаний за 24 часа"""
    if not _bot_instance:
        logger.error("❌ Bot instance not set! Call set_bot_instance() first.")
        return
    
    try:
        success, total = await ReminderService.send_reminders_24h(_bot_instance)
        if total > 0:
            logger.info(f"⏰ Reminder 24h job completed: {success}/{total} sent")
    except Exception as e:
        logger.error(f"❌ Reminder 24h async failed: {e}", exc_info=True)


async def _reminder_2h_async():
    """Async логика отправки напоминаний за 2 часа"""
    if not _bot_instance:
        logger.error("❌ Bot instance not set! Call set_bot_instance() first.")
        return
    
    try:
        success, total = await ReminderService.send_reminders_2h(_bot_instance)
        if total > 0:
            logger.info(f"⏰ Reminder 2h job completed: {success}/{total} sent")
    except Exception as e:
        logger.error(f"❌ Reminder 2h async failed: {e}", exc_info=True)


async def _reminder_1h_async():
    """Async логика отправки напоминаний за 1 час"""
    if not _bot_instance:
        logger.error("❌ Bot instance not set! Call set_bot_instance() first.")
        return
    
    try:
        success, total = await ReminderService.send_reminders_1h(_bot_instance)
        if total > 0:
            logger.info(f"🔔 Reminder 1h job completed: {success}/{total} sent")
    except Exception as e:
        logger.error(f"❌ Reminder 1h async failed: {e}", exc_info=True)
