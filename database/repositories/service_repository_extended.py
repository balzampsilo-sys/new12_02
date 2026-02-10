"""Расширенные методы для ServiceRepository"""

import logging
from typing import Any
import aiosqlite
from config import DATABASE_PATH


class ServiceRepositoryExtended:
    """Дополнительные методы для управления услугами"""
    
    @staticmethod
    async def create_service(
        name: str,
        description: str,
        duration_minutes: int,
        price: str,
        is_active: bool = True,
        display_order: int = 999,
        color: str = "#4A90E2"
    ) -> int:
        """Создать новую услугу (упрощенный интерфейс)"""
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute(
                    """INSERT INTO services 
                    (name, description, duration_minutes, price, color, display_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (name, description, duration_minutes, price, color, display_order, int(is_active))
                )
                await db.commit()
                service_id = cursor.lastrowid
                logging.info(f"Created service {service_id}: {name}")
                return service_id
        except Exception as e:
            logging.error(f"Error creating service: {e}")
            return 0
    
    @staticmethod
    async def update_service_field(
        service_id: int,
        field: str,
        value: Any
    ) -> bool:
        """Обновить одно поле услуги"""
        valid_fields = {
            "name", "description", "duration_minutes", 
            "price", "color", "is_active", "display_order"
        }
        
        if field not in valid_fields:
            logging.error(f"Invalid field: {field}")
            return False
        
        # Преобразуем duration в правильное поле
        if field == "duration":
            field = "duration_minutes"
        
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                query = f"UPDATE services SET {field}=? WHERE id=?"
                cursor = await db.execute(query, (value, service_id))
                await db.commit()
                
                success = cursor.rowcount > 0
                if success:
                    logging.info(f"Updated service {service_id}, field {field} = {value}")
                return success
        except Exception as e:
            logging.error(f"Error updating service field: {e}")
            return False
    
    @staticmethod
    async def delete_service(service_id: int, hard_delete: bool = False) -> bool:
        """Удалить услугу"""
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                if hard_delete:
                    # Полное удаление
                    cursor = await db.execute(
                        "DELETE FROM services WHERE id=?",
                        (service_id,)
                    )
                else:
                    # Мягкое удаление (отключение)
                    cursor = await db.execute(
                        "UPDATE services SET is_active=0 WHERE id=?",
                        (service_id,)
                    )
                
                await db.commit()
                success = cursor.rowcount > 0
                
                if success:
                    action = "deleted" if hard_delete else "deactivated"
                    logging.info(f"Service {service_id} {action}")
                
                return success
        except Exception as e:
            logging.error(f"Error deleting service: {e}")
            return False
    
    @staticmethod
    async def reorder_service(service_id: int, direction: str) -> bool:
        """Переместить услугу вверх или вниз"""
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                # Получаем текущий display_order
                async with db.execute(
                    "SELECT display_order FROM services WHERE id=?",
                    (service_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return False
                    current_order = row[0]
                
                # Находим соседнюю услугу
                if direction == "up":
                    # Находим услугу с меньшим display_order
                    async with db.execute(
                        """SELECT id, display_order FROM services 
                        WHERE display_order < ? 
                        ORDER BY display_order DESC LIMIT 1""",
                        (current_order,)
                    ) as cursor:
                        neighbor = await cursor.fetchone()
                else:  # down
                    # Находим услугу с большим display_order
                    async with db.execute(
                        """SELECT id, display_order FROM services 
                        WHERE display_order > ? 
                        ORDER BY display_order ASC LIMIT 1""",
                        (current_order,)
                    ) as cursor:
                        neighbor = await cursor.fetchone()
                
                if not neighbor:
                    return False
                
                neighbor_id, neighbor_order = neighbor
                
                # Меняем местами display_order
                await db.execute(
                    "UPDATE services SET display_order=? WHERE id=?",
                    (neighbor_order, service_id)
                )
                await db.execute(
                    "UPDATE services SET display_order=? WHERE id=?",
                    (current_order, neighbor_id)
                )
                
                await db.commit()
                logging.info(f"Service {service_id} moved {direction}")
                return True
                
        except Exception as e:
            logging.error(f"Error reordering service: {e}")
            return False
    
    @staticmethod
    async def get_active_services():
        """Получить активные услуги - алиас для совместимости"""
        from database.repositories.service_repository import ServiceRepository
        return await ServiceRepository.get_all_services(active_only=True)
    
    @staticmethod
    async def get_all_services():
        """Получить все услуги - алиас для совместимости"""
        from database.repositories.service_repository import ServiceRepository
        return await ServiceRepository.get_all_services(active_only=False)
    
    @staticmethod
    async def get_service_by_id(service_id: int):
        """Получить услугу по ID - алиас для совместимости"""
        from database.repositories.service_repository import ServiceRepository
        return await ServiceRepository.get_service_by_id(service_id)
