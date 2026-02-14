#!/usr/bin/env python3
"""
YooKassa Webhook Server
Автоматическая обработка платежей от ЮКассы

Функции:
- Получение webhook от ЮКассы
- Проверка подписи (безопасность)
- Автоматическое создание бота через Master Bot API
- Уведомления пользователям в Telegram

Документация YooKassa:
https://yookassa.ru/developers/using-api/webhooks
"""

import os
import json
import hmac
import hashlib
import logging
import asyncio
from datetime import datetime
from typing import Optional

from aiohttp import web, ClientSession, ClientTimeout
from aiogram import Bot
from yookassa import Configuration
from yookassa.domain.notification import WebhookNotification

from dotenv import load_dotenv
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('yookassa_webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === КОНФИГУРАЦИЯ ===
SALES_BOT_TOKEN = os.getenv("SALES_BOT_TOKEN")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8001"))
MASTER_BOT_API_URL = os.getenv("MASTER_BOT_API_URL", "http://localhost:8000")
MASTER_API_TOKEN = os.getenv("MASTER_API_TOKEN")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "YourSupport")

if not all([SALES_BOT_TOKEN, YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY]):
    raise ValueError("Не указаны обязательные переменные окружения")

Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

bot = Bot(token=SALES_BOT_TOKEN)

# Хранилище обрабатываемых платежей (предотвращение дублей)
processed_payments = set()


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """
    Проверить подпись webhook от ЮКассы
    
    Args:
        body: Тело запроса (байты)
        signature: Подпись из заголовка
    
    Returns:
        True если подпись валидна
    """
    if not signature:
        return False
    
    expected_signature = hmac.new(
        YOOKASSA_SECRET_KEY.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


async def create_bot_via_master_api(
    user_id: int,
    company_name: str,
    subscription_days: int,
    paid_amount: float,
    payment_id: str
) -> Optional[dict]:
    """
    Создать бота через Master Bot API
    
    Returns:
        Результат создания или None при ошибке
    """
    try:
        async with ClientSession() as session:
            payload = {
                "admin_telegram_id": user_id,
                "company_name": company_name,
                "subscription_days": subscription_days,
                "paid_amount": paid_amount,
                "payment_id": payment_id,
                "payment_method": "yookassa"
            }
            
            headers = {
                "Authorization": f"Bearer {MASTER_API_TOKEN}",
                "Content-Type": "application/json"
            }
            
            async with session.post(
                f"{MASTER_BOT_API_URL}/api/clients",
                json=payload,
                headers=headers,
                timeout=ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"✅ Bot created via API: {result}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(
                        f"❌ Failed to create bot: "
                        f"status={response.status}, error={error_text}"
                    )
                    return None
    
    except Exception as e:
        logger.error(f"❌ Error calling Master Bot API: {e}", exc_info=True)
        return None


async def process_successful_payment(payment):
    """
    Обработать успешный платеж
    """
    payment_id = payment.id
    
    # Предотвратить дублирование
    if payment_id in processed_payments:
        logger.warning(f"⚠️ Payment already processed: {payment_id}")
        return
    
    processed_payments.add(payment_id)
    
    metadata = payment.metadata
    if not metadata or 'user_id' not in metadata:
        logger.error(f"❌ No user_id in payment metadata: {payment_id}")
        return
    
    user_id = int(metadata['user_id'])
    company_name = metadata.get('company_name', '')
    plan = metadata.get('plan', '')
    days = int(metadata.get('days', 30))
    amount = float(payment.amount.value)
    
    logger.info(
        f"💰 Processing successful payment:\n"
        f"   • Payment ID: {payment_id}\n"
        f"   • User ID: {user_id}\n"
        f"   • Company: {company_name}\n"
        f"   • Plan: {plan} ({days} days)\n"
        f"   • Amount: {amount}₽"
    )
    
    try:
        # Уведомить о начале создания
        await bot.send_message(
            user_id,
            "✅ **ОПЛАТА ПОЛУЧЕНА!**\n\n"
            "⌛ Создаю вашего бота...\n"
            "Это займет 1-2 минуты.\n\n"
            "Не закрывайте чат!",
            parse_mode="Markdown"
        )
        
        # Создать бота
        result = await create_bot_via_master_api(
            user_id=user_id,
            company_name=company_name,
            subscription_days=days,
            paid_amount=amount,
            payment_id=payment_id
        )
        
        if result and result.get("success"):
            bot_username = result.get("bot_username", "unknown")
            client_id = result.get("client_id", "")
            expires_at = result.get("subscription_expires_at", "")
            
            await bot.send_message(
                user_id,
                f"🎉 **ВАШ БОТ ГОТОВ!**\n\n"
                f"🤖 Бот: @{bot_username}\n"
                f"🏢 Название: {company_name}\n"
                f"📅 Подписка: {days} дней\n"
                f"💰 Оплачено: {amount}₽\n"
                f"⏰ Действует до: {expires_at}\n\n"
                f"**Что делать дальше:**\n\n"
                f"1️⃣ Откройте бота: @{bot_username}\n"
                f"2️⃣ Нажмите /start\n"
                f"3️⃣ Настройте расписание и услуги\n"
                f"4️⃣ Поделитесь ссылкой с клиентами\n\n"
                f"✨ Спасибо за покупку!\n\n"
                f"🆔 ID: `{client_id}`",
                parse_mode="Markdown"
            )
            
            logger.info(f"✅ User {user_id} notified about bot {bot_username}")
        
        else:
            await bot.send_message(
                user_id,
                f"❌ Ошибка при создании бота.\n\n"
                f"Напишите в поддержку: @{SUPPORT_USERNAME}\n\n"
                f"🆔 ID: `{payment_id}`",
                parse_mode="Markdown"
            )
            logger.error(f"❌ Failed to create bot for payment {payment_id}")
    
    except Exception as e:
        logger.error(f"❌ Error processing payment {payment_id}: {e}", exc_info=True)


async def handle_yookassa_webhook(request):
    """
    Webhook endpoint для ЮКассы
    """
    try:
        # 1. Получить данные
        body = await request.read()
        
        # 2. Проверить подпись (опционально, но рекомендуется)
        signature = request.headers.get('X-Yookassa-Signature', '')
        
        if signature and not verify_webhook_signature(body, signature):
            logger.warning(
                f"⚠️ Invalid webhook signature from IP: {request.remote}"
            )
            return web.json_response({"error": "Invalid signature"}, status=403)
        
        # 3. Распарсить уведомление
        notification = WebhookNotification(json.loads(body.decode('utf-8')))
        payment = notification.object
        
        logger.info(
            f"🔔 Webhook received:\n"
            f"   • Event: {notification.event}\n"
            f"   • Payment ID: {payment.id}\n"
            f"   • Status: {payment.status}\n"
            f"   • IP: {request.remote}"
        )
        
        # 4. Обработать событие
        if payment.status == "succeeded":
            # Запустить обработку в фоне
            asyncio.create_task(process_successful_payment(payment))
        
        elif payment.status == "canceled":
            if payment.metadata and 'user_id' in payment.metadata:
                user_id = int(payment.metadata['user_id'])
                await bot.send_message(
                    user_id,
                    "❌ Платеж отменен.\n\n"
                    "Вы можете попробовать снова: /start"
                )
        
        return web.json_response({"status": "ok"})
    
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def health_check(request):
    """
    Health check endpoint
    """
    return web.json_response({
        "status": "ok",
        "service": "YooKassa Webhook Server",
        "timestamp": datetime.now().isoformat(),
        "processed_payments": len(processed_payments)
    })


async def payment_success_page(request):
    """
    Success page after payment redirect
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Платеж успешен</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; }
            h1 { color: #4CAF50; }
        </style>
    </head>
    <body>
        <h1>✅ Платеж успешно выполнен!</h1>
        <p>Вернитесь в Telegram чтобы получить своего бота.</p>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')


def create_app():
    """
    Создать aiohttp приложение
    """
    app = web.Application()
    
    app.router.add_post('/webhook/yookassa', handle_yookassa_webhook)
    app.router.add_get('/health', health_check)
    app.router.add_get('/payment/success', payment_success_page)
    app.router.add_get('/', health_check)
    
    return app


if __name__ == '__main__':
    logger.info(
        f"🚀 Starting YooKassa Webhook Server\n"
        f"   • Port: {WEBHOOK_PORT}\n"
        f"   • Master Bot API: {MASTER_BOT_API_URL}\n"
        f"   • Support: @{SUPPORT_USERNAME}"
    )
    
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=WEBHOOK_PORT)
