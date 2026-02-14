#!/usr/bin/env python3
"""
Subscription Checker
Автоматическая проверка подписок

Использование:
  python check_subscriptions.py

Для cron job (1 раз в час):
  0 * * * * cd /path/to/project && python3 automation/check_subscriptions.py >> logs/subscription_check.log 2>&1
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Добавить automation/ в путь
script_dir = Path(__file__).parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from subscription_manager import SubscriptionManager


class SubscriptionChecker:
    """Проверка и остановка ботов с истекшей подпиской"""
    
    def __init__(self, subscription_db: str = "subscriptions.db", notify_admin: bool = True):
        """
        Инициализация
        
        Args:
            subscription_db: Путь к БД подписок
            notify_admin: Отправлять ли уведомления
        """
        self.sub_manager = SubscriptionManager(subscription_db)
        self.notify_admin = notify_admin
    
    def check_and_suspend_expired(self):
        """Проверить и остановить боты с истекшей подпиской"""
        print("="*60)
        print(f"🔍 SUBSCRIPTION CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        print("")
        
        # Получить клиентов с истекшей подпиской
        expired_clients = self.sub_manager.check_expired_subscriptions()
        
        if not expired_clients:
            print("✅ Все подписки активны")
            print("")
            return 0
        
        print(f"⚠️ Найдено истекших подписок: {len(expired_clients)}")
        print("")
        
        suspended_count = 0
        failed_count = 0
        
        for client in expired_clients:
            client_id = client['client_id']
            company_name = client['company_name'] or client_id[:8]
            container_name = client['container_name']
            expires_at = client['subscription_expires_at']
            
            print(f"🗓️ Клиент: {company_name}")
            print(f"   ID: {client_id}")
            print(f"   Истекло: {expires_at}")
            print(f"   Container: {container_name}")
            
            # Остановить Docker контейнер
            if self._stop_container(container_name):
                # Обновить статус в БД
                self.sub_manager.suspend_client(
                    client_id,
                    reason=f"Subscription expired on {expires_at}"
                )
                
                suspended_count += 1
                print("✅ Бот остановлен")
                
                # Уведомить клиента (если настроено)
                if self.notify_admin:
                    self._notify_client(client)
            else:
                failed_count += 1
                print("❌ Ошибка остановки")
            
            print("")
        
        # Итоги
        print("="*60)
        print(f"✅ Остановлено: {suspended_count}")
        if failed_count > 0:
            print(f"❌ Ошибки: {failed_count}")
        print("="*60)
        print("")
        
        return suspended_count
    
    def check_expiring_soon(self, days_before: int = 3):
        """
        Проверить подписки, которые истекают скоро
        
        Args:
            days_before: За сколько дней предупреждать
        """
        from datetime import timedelta
        
        print("📢 Проверка истекающих подписок...")
        
        # TODO: Найти клиентов с подпиской истекающей через N дней
        # Отправить уведомление
        
        print("✅ Done")
        print("")
    
    def _stop_container(self, container_name: str) -> bool:
        """
        Остановить Docker контейнер
        
        Args:
            container_name: Имя контейнера
        
        Returns:
            True если успешно
        """
        try:
            result = subprocess.run(
                ["docker", "stop", container_name],
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"   Error: {e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            print("   Error: Timeout")
            return False
    
    def _notify_client(self, client: dict):
        """
        Отправить уведомление клиенту
        
        Args:
            client: Данные клиента
        """
        # TODO: Интеграция с Telegram Bot API
        # Отправить сообщение админу:
        # "⚠️ Ваша подписка истекла!
        #  Бот остановлен.
        #  Для возобновления свяжитесь с @your_username"
        
        admin_id = client['admin_telegram_id']
        company = client['company_name'] or "Your bot"
        
        print(f"   📧 Notification sent to {admin_id} (simulated)")


def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Проверка подписок")
    parser.add_argument(
        "--db",
        default="subscriptions.db",
        help="Путь к БД подписок"
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Не отправлять уведомления"
    )
    parser.add_argument(
        "--check-expiring",
        action="store_true",
        help="Проверить истекающие скоро подписки"
    )
    
    args = parser.parse_args()
    
    checker = SubscriptionChecker(
        subscription_db=args.db,
        notify_admin=not args.no_notify
    )
    
    # Проверить истекшие
    suspended = checker.check_and_suspend_expired()
    
    # Проверить истекающие скоро (если запрошено)
    if args.check_expiring:
        checker.check_expiring_soon(days_before=3)
    
    return 0 if suspended == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
