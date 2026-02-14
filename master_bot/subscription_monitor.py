#!/usr/bin/env python3
"""
Subscription Monitor - Мониторинг и автоматическое управление подписками

Функции:
- Проверка истекающих подписок
- Уведомления клиентам (3/1 дня до истечения)
- Автоматическая остановка ботов
- Уведомления админам
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

# Добавить automation/ в путь
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root / "automation"))

from subscription_manager import SubscriptionManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === КОНФИГУРАЦИЯ ===
MASTER_BOT_TOKEN = os.getenv("MASTER_BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
CHECK_INTERVAL = int(os.getenv("SUBSCRIPTION_CHECK_INTERVAL", "3600"))  # 1 час по умолчанию

if not MASTER_BOT_TOKEN:
    raise ValueError("MASTER_BOT_TOKEN not set")

if not ADMIN_IDS:
    raise ValueError("ADMIN_IDS not set")

DB_PATH = str(project_root / "subscriptions.db")
sub_manager = SubscriptionManager(DB_PATH)
bot = Bot(token=MASTER_BOT_TOKEN)


class SubscriptionMonitor:
    """Монитор подписок"""

    @staticmethod
    async def check_expiring_subscriptions() -> Dict[str, List]:
        """
        Проверить истекающие подписки
        
        Returns:
            Dict с ключами:
            - expired: подписки уже истекли
            - expires_today: истекают сегодня
            - expires_in_3_days: истекают через 3 дня
        """
        try:
            all_clients = sub_manager.list_clients(limit=1000)
            now = datetime.now()
            today = now.date()
            
            result = {
                'expired': [],
                'expires_today': [],
                'expires_in_3_days': [],
                'expires_in_7_days': []
            }
            
            for client in all_clients:
                if client['subscription_status'] != 'active':
                    continue
                
                expires_at = datetime.fromisoformat(client['subscription_expires_at'])
                expires_date = expires_at.date()
                days_left = (expires_date - today).days
                
                if days_left < 0:
                    result['expired'].append(client)
                elif days_left == 0:
                    result['expires_today'].append(client)
                elif days_left == 3:
                    result['expires_in_3_days'].append(client)
                elif days_left == 7:
                    result['expires_in_7_days'].append(client)
            
            logger.info(
                f"📊 Subscription check: "
                f"Expired: {len(result['expired'])}, "
                f"Today: {len(result['expires_today'])}, "
                f"3 days: {len(result['expires_in_3_days'])}, "
                f"7 days: {len(result['expires_in_7_days'])}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Error checking subscriptions: {e}", exc_info=True)
            return {'expired': [], 'expires_today': [], 'expires_in_3_days': [], 'expires_in_7_days': []}

    @staticmethod
    async def notify_client_expiring(client: Dict, days_left: int) -> bool:
        """
        Уведомить клиента о скором истечении подписки
        
        Args:
            client: Информация о клиенте
            days_left: Осталось дней
        
        Returns:
            True если успешно
        """
        try:
            company = client.get('company_name', 'Ваш бизнес')
            expires_at = client['subscription_expires_at'][:10]
            
            if days_left == 7:
                emoji = "🚨"
                title = "ПОДПИСКА ИСТЕКАЕТ ЧЕРЕЗ 7 ДНЕЙ"
            elif days_left == 3:
                emoji = "⚠️"
                title = "ПОДПИСКА ИСТЕКАЕТ ЧЕРЕЗ 3 ДНЯ"
            else:
                emoji = "⏰"
                title = "ПОДПИСКА ИСТЕКАЕТ СЕГОДНЯ"
            
            message = (
                f"{emoji} **{title}**\n\n"
                f"🏢 Компания: **{company}**\n"
                f"📅 Истекает: **{expires_at}**\n"
                f"⌛ Осталось: **{days_left} дней**\n\n"
                f"💳 Чтобы продлить подписку:\n"
                f"1. Напишите нам в поддержку\n"
                f"2. Или оплатите через бот\n\n"
                f"❗ Без продления бот будет остановлен!"
            )
            
            await bot.send_message(
                client['admin_telegram_id'],
                message,
                parse_mode="Markdown"
            )
            
            logger.info(f"✅ Expiration notice sent to client {client['client_id']} ({days_left} days)")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error notifying client {client.get('client_id')}: {e}")
            return False

    @staticmethod
    async def suspend_expired_client(client: Dict) -> bool:
        """
        Остановить бота с истекшей подпиской
        
        Args:
            client: Информация о клиенте
        
        Returns:
            True если успешно
        """
        try:
            client_id = client['client_id']
            company = client.get('company_name', 'Unknown')
            
            # Остановить Docker контейнер
            container_name = f"booking_bot_{client['redis_db']}"
            
            # TODO: Добавить в deploy_manager.py
            # deploy_manager.stop_container(container_name)
            
            # Обновить статус в БД
            sub_manager.suspend_client(
                client_id=client_id,
                reason="subscription_expired"
            )
            
            # Уведомить клиента
            message = (
                "❌ **ПОДПИСКА ИСТЕКЛА**\n\n"
                f"🏢 Компания: **{company}**\n\n"
                "🚫 Ваш бот был остановлен.\n\n"
                "🔄 **Чтобы возобновить работу:**\n"
                "1. Продлите подписку\n"
                "2. Напишите в поддержку\n\n"
                "💾 Все ваши данные сохранены!"
            )
            
            await bot.send_message(
                client['admin_telegram_id'],
                message,
                parse_mode="Markdown"
            )
            
            logger.warning(f"⚠️ Client {client_id} ({company}) suspended - subscription expired")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error suspending client {client.get('client_id')}: {e}", exc_info=True)
            return False

    @staticmethod
    async def notify_admins_summary(expiring_data: Dict):
        """
        Отправить админам сводку по истекающим подпискам
        
        Args:
            expiring_data: Данные от check_expiring_subscriptions()
        """
        try:
            expired = len(expiring_data['expired'])
            today = len(expiring_data['expires_today'])
            in_3_days = len(expiring_data['expires_in_3_days'])
            in_7_days = len(expiring_data['expires_in_7_days'])
            
            # Отправлять только если есть что сообщить
            if expired == 0 and today == 0 and in_3_days == 0 and in_7_days == 0:
                return
            
            message = "📊 **СВОДКА ПО ПОДПИСКАМ**\n\n"
            
            if expired > 0:
                message += f"❌ **Истекли:** {expired}\n"
                for client in expiring_data['expired'][:5]:  # Первые 5
                    company = client.get('company_name', 'Unknown')
                    message += f"   • {company}\n"
                if expired > 5:
                    message += f"   ... и еще {expired - 5}\n"
                message += "\n"
            
            if today > 0:
                message += f"⏰ **Истекают сегодня:** {today}\n"
                for client in expiring_data['expires_today']:
                    company = client.get('company_name', 'Unknown')
                    message += f"   • {company}\n"
                message += "\n"
            
            if in_3_days > 0:
                message += f"⚠️ **Истекают через 3 дня:** {in_3_days}\n"
            
            if in_7_days > 0:
                message += f"🚨 **Истекают через 7 дней:** {in_7_days}\n"
            
            # Отправить всем админам
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        message,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Error notifying admin {admin_id}: {e}")
            
            logger.info("✅ Admin summary sent")
        
        except Exception as e:
            logger.error(f"❌ Error sending admin summary: {e}", exc_info=True)

    @staticmethod
    async def run_check():
        """Запустить полную проверку подписок"""
        logger.info("🔍 Starting subscription check...")
        
        # 1. Проверить все подписки
        expiring_data = await SubscriptionMonitor.check_expiring_subscriptions()
        
        # 2. Остановить истекшие
        for client in expiring_data['expired']:
            await SubscriptionMonitor.suspend_expired_client(client)
            await asyncio.sleep(1)  # Чтобы не спамить
        
        # 3. Уведомить о скором истечении (7 дней)
        for client in expiring_data['expires_in_7_days']:
            await SubscriptionMonitor.notify_client_expiring(client, 7)
            await asyncio.sleep(1)
        
        # 4. Уведомить о скором истечении (3 дня)
        for client in expiring_data['expires_in_3_days']:
            await SubscriptionMonitor.notify_client_expiring(client, 3)
            await asyncio.sleep(1)
        
        # 5. Уведомить о сегодняшнем истечении
        for client in expiring_data['expires_today']:
            await SubscriptionMonitor.notify_client_expiring(client, 0)
            await asyncio.sleep(1)
        
        # 6. Отправить сводку админам
        await SubscriptionMonitor.notify_admins_summary(expiring_data)
        
        logger.info("✅ Subscription check completed")


async def main():
    """Главный цикл мониторинга"""
    logger.info("🚀 Subscription Monitor starting...")
    logger.info(f"⏰ Check interval: {CHECK_INTERVAL} seconds ({CHECK_INTERVAL // 3600} hours)")
    logger.info(f"📄 Database: {DB_PATH}")
    
    while True:
        try:
            await SubscriptionMonitor.run_check()
        except Exception as e:
            logger.error(f"❌ Error in monitoring cycle: {e}", exc_info=True)
        
        # Подождать до следующей проверки
        logger.info(f"⏸️ Sleeping for {CHECK_INTERVAL} seconds...")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Subscription Monitor stopped")
