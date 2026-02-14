#!/usr/bin/env python3
"""
Webhook обработчик для уведомлений от ЮKassa

Запускается отдельно как веб-сервер для приема уведомлений о платежах
"""

import os
import json
import logging
from datetime import datetime

from aiohttp import web
from aiogram import Bot
from yookassa import Configuration
from yookassa.domain.notification import WebhookNotification

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
SALES_BOT_TOKEN = os.getenv("SALES_BOT_TOKEN")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))

Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

bot = Bot(token=SALES_BOT_TOKEN)

# Хранилище обработанных платежей (в продакшене использовать Redis/DB)
processed_payments = set()


async def handle_yookassa_webhook(request):
    """
    Обработчик webhook от ЮKassa
    
    ЮKassa отправляет уведомления о изменении статуса платежа
    """
    try:
        # Получить JSON от ЮKassa
        body = await request.text()
        logger.info(f"Webhook received: {body[:200]}")
        
        # Парсить уведомление
        notification = WebhookNotification(json.loads(body))
        payment = notification.object
        
        logger.info(f"Payment notification: {payment.id}, status: {payment.status}")
        
        # Проверить что платеж еще не обработан
        if payment.id in processed_payments:
            logger.info(f"Payment {payment.id} already processed")
            return web.Response(status=200)
        
        # Обработать только успешные платежи
        if payment.status == "succeeded":
            await process_successful_payment(payment)
            processed_payments.add(payment.id)
        
        elif payment.status == "canceled":
            logger.info(f"Payment {payment.id} was canceled")
            # Можно отправить уведомление пользователю
            if payment.metadata and 'user_id' in payment.metadata:
                user_id = int(payment.metadata['user_id'])
                await bot.send_message(
                    user_id,
                    "❌ Платеж был отменен.\n\n"
                    "Вы можете попробовать снова: /start"
                )
        
        return web.Response(status=200)
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return web.Response(status=500)


async def process_successful_payment(payment):
    """
    Обработать успешный платеж
    """
    metadata = payment.metadata
    
    if not metadata or 'user_id' not in metadata:
        logger.error(f"Payment {payment.id} has no user_id in metadata")
        return
    
    user_id = int(metadata['user_id'])
    company_name = metadata.get('company_name', 'Не указано')
    plan = metadata.get('plan', '1m')
    days = int(metadata.get('days', 30))
    
    logger.info(f"Processing successful payment for user {user_id}, company: {company_name}")
    
    # Отправить уведомление пользователю
    await bot.send_message(
        user_id,
        "✅ **ОПЛАТА ПОЛУЧЕНА!**\n\n"
        "⏳ Создаю вашего бота...\n"
        "Это займет 1-2 минуты.",
        parse_mode="Markdown"
    )
    
    try:
        # Здесь должна быть интеграция с Master Bot API
        # TODO: Вызов API для создания бота
        # result = await create_client_via_master_bot_api(
        #     admin_telegram_id=user_id,
        #     company_name=company_name,
        #     subscription_days=days,
        #     paid_amount=float(payment.amount.value)
        # )
        
        # Для демо - заглушка
        import asyncio
        await asyncio.sleep(2)
        
        bot_username = f"booking_{user_id}_bot"
        
        success_text = f"""
🎉 **ВАШ БОТ ГОТОВ!**

🤖 Бот: @{bot_username}
🏢 Название: {company_name}
📅 Подписка: {days} дней
💰 Оплачено: {payment.amount.value}₽

**Что делать дальше:**

1️⃣ Откройте бота: @{bot_username}
2️⃣ Нажмите /start
3️⃣ Настройте расписание и услуги
4️⃣ Поделитесь ссылкой с клиентами

📚 **Инструкция:** https://docs.example.com
💬 **Поддержка:** @{os.getenv('SUPPORT_USERNAME', 'YourSupport')}

✨ Спасибо за покупку! Ваш бот уже работает 24/7
        """
        
        await bot.send_message(
            user_id,
            success_text,
            parse_mode="Markdown"
        )
        
        logger.info(f"Bot created successfully for user {user_id}")
    
    except Exception as e:
        logger.error(f"Error creating bot for payment {payment.id}: {e}", exc_info=True)
        await bot.send_message(
            user_id,
            f"❌ Произошла ошибка при создании бота.\n\n"
            f"Не волнуйтесь, ваша оплата сохранена!\n"
            f"Напишите в поддержку: @{os.getenv('SUPPORT_USERNAME')}\n\n"
            f"ID платежа: `{payment.id}`",
            parse_mode="Markdown"
        )


async def health_check(request):
    """
    Health check endpoint
    """
    return web.json_response({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })


def create_app():
    """
    Создать aiohttp приложение
    """
    app = web.Application()
    
    # Роуты
    app.router.add_post('/webhook/yookassa', handle_yookassa_webhook)
    app.router.add_get('/health', health_check)
    app.router.add_get('/payment/success', lambda r: web.Response(text="Платеж успешно выполнен! Вернитесь в Telegram."))
    
    return app


if __name__ == '__main__':
    logger.info(f"🚀 Starting webhook server on port {WEBHOOK_PORT}")
    logger.info(f"YooKassa Shop ID: {YOOKASSA_SHOP_ID}")
    logger.info(f"Webhook endpoint: /webhook/yookassa")
    
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=WEBHOOK_PORT)
