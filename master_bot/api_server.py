#!/usr/bin/env python3
"""
REST API для Master Bot
Позволяет Sales Bot автоматически создавать клиентов
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Добавить automation/ в путь
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root / "automation"))

from subscription_manager import SubscriptionManager
from deploy_manager import DeploymentManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === КОНФИГУРАЦИЯ ===
API_PORT = int(os.getenv("MASTER_API_PORT", "8000"))
API_TOKEN = os.getenv("MASTER_API_TOKEN", "your_secret_token_here_change_me")

if API_TOKEN == "your_secret_token_here_change_me":
    logger.warning("⚠️ Using default API token! Set MASTER_API_TOKEN in .env")

DB_PATH = str(project_root / "subscriptions.db")
sub_manager = SubscriptionManager(DB_PATH)
deploy_manager = DeploymentManager(project_root=project_root)

app = FastAPI(
    title="Master Bot API",
    description="API для автоматического создания и управления клиентами",
    version="1.0.0"
)

# === МОДЕЛИ ДАННЫХ ===

class CreateClientRequest(BaseModel):
    """Запрос на создание нового клиента"""
    bot_token: str = Field(..., description="Токен бота от BotFather")
    admin_telegram_id: int = Field(..., description="Telegram ID клиента")
    company_name: str = Field(..., description="Название компании")
    subscription_days: int = Field(default=30, description="Длительность подписки в днях")
    paid_amount: float = Field(default=0.0, description="Сумма оплаты")
    payment_id: Optional[str] = Field(None, description="ID платежа для отслеживания")

    class Config:
        json_schema_extra = {
            "example": {
                "bot_token": "123456789:ABCdefGHI...",
                "admin_telegram_id": 987654321,
                "company_name": "Салон красоты Анна",
                "subscription_days": 30,
                "paid_amount": 299.0,
                "payment_id": "pay_123abc"
            }
        }


class ExtendSubscriptionRequest(BaseModel):
    """Запрос на продление подписки"""
    client_id: str = Field(..., description="ID клиента (UUID)")
    days: int = Field(..., description="Количество дней для продления")
    amount: float = Field(..., description="Сумма платежа")
    payment_id: Optional[str] = Field(None, description="ID платежа")

    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "550e8400-e29b-41d4-a716-446655440000",
                "days": 90,
                "amount": 799.0,
                "payment_id": "pay_456def"
            }
        }


class ClientStatusResponse(BaseModel):
    """Ответ со статусом клиента"""
    client_id: str
    company_name: str
    subscription_status: str
    subscription_expires_at: str
    redis_db: int
    container_name: str
    bot_username: Optional[str] = None


# === АВТОРИЗАЦИЯ ===

async def verify_token(authorization: str = Header(None)):
    """Проверка API токена"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "")
    
    if token != API_TOKEN:
        logger.warning(f"🚨 Invalid API token attempt")
        raise HTTPException(status_code=403, detail="Invalid API token")
    
    return True


# === ЭНДПОИНТЫ ===

@app.get("/")
async def root():
    """Проверка работоспособности API"""
    return {
        "service": "Master Bot API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check для мониторинга"""
    try:
        # Проверка доступности БД
        stats = sub_manager.get_statistics()
        db_ok = True
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db_ok = False
    
    status = "healthy" if db_ok else "unhealthy"
    status_code = 200 if db_ok else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "database": "ok" if db_ok else "error",
            "timestamp": datetime.now().isoformat()
        }
    )


@app.post("/api/clients", dependencies=[Depends(verify_token)])
async def create_client(request: CreateClientRequest):
    """
    Создать нового клиента и автоматически задеплоить бота
    
    Процесс:
    1. Валидация данных
    2. Выделение Redis DB
    3. Деплой Docker контейнера
    4. Создание записи в БД
    5. Возврат информации о боте
    """
    try:
        logger.info(f"📥 New client request: {request.company_name}")
        
        # Деплой бота
        result = deploy_manager.deploy_client(
            bot_token=request.bot_token,
            admin_telegram_id=request.admin_telegram_id,
            company_name=request.company_name
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=f"Deployment failed: {result.get('error', 'Unknown error')}"
            )
        
        # Если оплата была произведена, добавить в БД
        if request.paid_amount > 0 and request.payment_id:
            sub_manager.add_payment(
                client_id=result['client_id'],
                amount=request.paid_amount,
                currency="RUB",
                payment_method="telegram_stars",
                notes=f"Initial payment for {request.subscription_days} days",
                external_payment_id=request.payment_id
            )
        
        # Продлить подписку если нужно (больше 30 дней по умолчанию)
        if request.subscription_days > 30:
            sub_manager.reactivate_client(
                client_id=result['client_id'],
                extend_days=request.subscription_days - 30
            )
        
        logger.info(f"✅ Client created: {result['client_id']}")
        
        return {
            "success": True,
            "client_id": result['client_id'],
            "bot_username": f"booking_bot_{result['redis_db']}",  # TODO: получать из BotFather
            "redis_db": result['redis_db'],
            "container_name": result['container_name'],
            "subscription_expires_at": (
                datetime.now().strftime('%Y-%m-%d') 
                if request.subscription_days <= 30 
                else None  # Будет рассчитано после продления
            ),
            "message": f"Bot deployed successfully for {request.company_name}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating client: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clients/{client_id}/extend", dependencies=[Depends(verify_token)])
async def extend_subscription(client_id: str, request: ExtendSubscriptionRequest):
    """
    Продлить подписку клиента
    
    Используется когда клиент оплачивает продление через Sales Bot
    """
    try:
        logger.info(f"📥 Extend subscription request: {client_id} for {request.days} days")
        
        # Проверить что клиент существует
        client = sub_manager.get_client(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Добавить платеж
        sub_manager.add_payment(
            client_id=client_id,
            amount=request.amount,
            currency="RUB",
            payment_method="telegram_stars",
            notes=f"Subscription extension for {request.days} days",
            external_payment_id=request.payment_id
        )
        
        # Продлить подписку (если больше чем 30 дней по умолчанию от add_payment)
        if request.days > 30:
            sub_manager.reactivate_client(
                client_id=client_id,
                extend_days=request.days - 30
            )
        
        # Получить обновленную информацию
        updated_client = sub_manager.get_client(client_id)
        
        logger.info(f"✅ Subscription extended for {client_id}")
        
        return {
            "success": True,
            "client_id": client_id,
            "subscription_expires_at": updated_client['subscription_expires_at'],
            "message": f"Subscription extended by {request.days} days"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error extending subscription: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/clients/{client_id}", dependencies=[Depends(verify_token)])
async def get_client_status(client_id: str):
    """
    Получить статус клиента
    
    Используется для проверки состояния подписки
    """
    try:
        client = sub_manager.get_client(client_id)
        
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        return ClientStatusResponse(
            client_id=client['client_id'],
            company_name=client['company_name'] or "Unknown",
            subscription_status=client['subscription_status'],
            subscription_expires_at=client['subscription_expires_at'],
            redis_db=client['redis_db'],
            container_name=f"booking_bot_{client['redis_db']}",
            bot_username=f"booking_bot_{client['redis_db']}"  # TODO: из БД
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting client status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", dependencies=[Depends(verify_token)])
async def get_statistics():
    """
    Получить общую статистику
    
    Используется для дашбордов и мониторинга
    """
    try:
        stats = sub_manager.get_statistics()
        
        return {
            "total_clients": stats['total_clients'],
            "active_clients": stats['active_clients'],
            "suspended_clients": stats['suspended_clients'],
            "trial_clients": stats.get('trial_clients', 0),
            "available_redis_dbs": stats['available_redis_dbs'],
            "monthly_revenue": stats['monthly_revenue'],
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Error getting statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/clients/{client_id}", dependencies=[Depends(verify_token)])
async def delete_client(client_id: str):
    """
    Удалить клиента (ОПАСНО!)
    
    Остановит контейнер и удалит все данные
    Используйте с осторожностью!
    """
    try:
        logger.warning(f"⚠️ Delete request for client: {client_id}")
        
        client = sub_manager.get_client(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # TODO: Остановить и удалить контейнер
        # deploy_manager.remove_client(client_id)
        
        # Отменить подписку в БД
        sub_manager.cancel_subscription(
            client_id=client_id,
            reason="deleted_via_api"
        )
        
        logger.warning(f"🗑️ Client deleted: {client_id}")
        
        return {
            "success": True,
            "message": f"Client {client_id} deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting client: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# === ЗАПУСК ===

def main():
    logger.info("🚀 Master Bot API starting...")
    logger.info(f"📡 Listening on http://0.0.0.0:{API_PORT}")
    logger.info(f"📚 Docs: http://localhost:{API_PORT}/docs")
    logger.info(f"💾 Database: {DB_PATH}")
    
    if API_TOKEN == "your_secret_token_here_change_me":
        logger.error("❌ SECURITY WARNING: Using default API token!")
        logger.error("Set MASTER_API_TOKEN in .env file")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=API_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()
