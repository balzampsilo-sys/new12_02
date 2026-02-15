#!/usr/bin/env python3
"""
🧪 Тестовый скрипт для проверки автономного деплоя клиентских ботов

Использование:
    python scripts/test_deploy.py

Требования:
    - Master Bot запущен
    - Docker socket доступен
    - PostgreSQL и Redis работают
"""

import asyncio
import sys
import os

# Добавить корневую директорию в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.docker_deploy_manager import DockerDeployManager
from config import Config


async def test_deploy():
    """Тестовый деплой клиентского бота"""
    
    print("=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ АВТОНОМНОГО ДЕПЛОЯ КЛИЕНТСКОГО БОТА")
    print("=" * 70)
    
    # Инициализация менеджера
    print("\n📦 Инициализация DockerDeployManager...")
    
    try:
        deploy_manager = DockerDeployManager(
            database_url=Config.DATABASE_URL,
            schema="master_bot"
        )
        print("✅ DockerDeployManager инициализирован")
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        return
    
    # Тестовые данные
    print("\n📋 Тестовые данные:")
    test_data = {
        "bot_token": input("Введите BOT_TOKEN для тестового бота: ").strip(),
        "admin_telegram_id": int(input("Введите Telegram ID администратора: ").strip()),
        "company_name": input("Введите название компании: ").strip() or "Тестовая компания",
        "subscription_days": 30
    }
    
    print(f"\n🏪 Компания: {test_data['company_name']}")
    print(f"👤 Админ ID: {test_data['admin_telegram_id']}")
    print(f"📅 Подписка: {test_data['subscription_days']} дней")
    
    # Подтверждение
    confirm = input("\n❓ Запустить деплой? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y', 'да']:
        print("❌ Деплой отменён")
        return
    
    # Деплой
    print("\n⏳ Запуск деплоя...")
    print("-" * 70)
    
    try:
        result = await deploy_manager.deploy_client(
            bot_token=test_data['bot_token'],
            admin_telegram_id=test_data['admin_telegram_id'],
            company_name=test_data['company_name'],
            subscription_days=test_data['subscription_days']
        )
        
        print("-" * 70)
        
        if result['success']:
            print("\n" + "=" * 70)
            print("✅ БОТ УСПЕШНО РАЗВЁРНУТ!")
            print("=" * 70)
            print(f"\n🏪 Компания:      {result['company_name']}")
            print(f"🆔 Client ID:    {result['client_id']}")
            print(f"🐳 Container:    {result['container_name']}")
            print(f"📊 Redis DB:     {result['redis_db']}")
            print(f"🗄️  Schema:       {result['schema']}")
            print(f"👤 Admin ID:     {result['admin_telegram_id']}")
            
            print("\n" + "=" * 70)
            print("📋 КОМАНДЫ ДЛЯ ПРОВЕРКИ:")
            print("=" * 70)
            print(f"\n# Проверить контейнер:")
            print(f"docker ps --filter name={result['container_name']}")
            print(f"\n# Посмотреть логи:")
            print(f"docker logs {result['container_name']} -f")
            print(f"\n# Проверить статус:")
            print(f"docker inspect {result['container_name']} --format='{{{{.State.Status}}}}'")
            print(f"\n# Остановить бота:")
            print(f"docker stop {result['container_name']}")
            print(f"\n# Удалить бота:")
            print(f"docker rm {result['container_name']}")
            
        else:
            print("\n" + "=" * 70)
            print("❌ ОШИБКА ДЕПЛОЯ")
            print("=" * 70)
            print(f"\n❌ {result['error']}")
            
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ КРИТИЧЕСКАЯ ОШИБКА")
        print("=" * 70)
        print(f"\n{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def test_docker_connection():
    """Проверить подключение к Docker"""
    
    print("\n🔍 ПРОВЕРКА ПОДКЛЮЧЕНИЯ К DOCKER")
    print("-" * 70)
    
    try:
        import docker
        client = docker.from_env()
        version = client.version()
        
        print("✅ Docker подключен!")
        print(f"   Version: {version.get('Version')}")
        print(f"   API Version: {version.get('ApiVersion')}")
        
        # Список контейнеров
        containers = client.containers.list()
        print(f"\n📦 Найдено контейнеров: {len(containers)}")
        for container in containers:
            print(f"   - {container.name} ({container.status})")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения к Docker: {e}")
        return False


async def main():
    """Главная функция"""
    
    # Проверить Docker
    if not await test_docker_connection():
        print("\n⚠️  Убедитесь что:")
        print("   1. Docker Desktop запущен")
        print("   2. В Settings → General включено: 'Expose daemon on tcp://localhost:2375 without TLS'")
        print("   3. DOCKER_HOST=tcp://host.docker.internal:2375 установлено")
        return
    
    # Запустить тест
    await test_deploy()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
