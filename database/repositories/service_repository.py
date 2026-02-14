"""Репозиторий для работы с услугами

✅ FIXED: Заменен aiosqlite на db_adapter для PostgreSQL поддержки
"""

import logging
from typing import Dict, List, Optional

from database.db_adapter import db_adapter  # ✅ NEW


class ServiceRepository:
    """Репозиторий для управления услугами
    
    ✅ FIXED: Использует db_adapter вместо aiosqlite
    """

    @staticmethod
    async def get_all_services() -> List[Dict]:
        """Получить все активные услуги"""
        try:
            rows = await db_adapter.fetch(
                """SELECT id, name, description, duration_minutes, price, is_active
                FROM services
                WHERE is_active = true
                ORDER BY id"""
            )
            
            if not rows:
                return []
            
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"] or "",
                    "duration_minutes": row["duration_minutes"],
                    "price": row["price"] or "—",
                    "is_active": row["is_active"],
                }
                for row in rows
            ]
        except Exception as e:
            logging.error(f"Error getting all services: {e}")
            return []

    @staticmethod
    async def get_service_by_id(service_id: int) -> Optional[Dict]:
        """Получить услугу по ID"""
        try:
            row = await db_adapter.fetchrow(
                """SELECT id, name, description, duration_minutes, price, is_active
                FROM services
                WHERE id = $1""",
                service_id
            )
            
            if not row:
                return None
            
            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"] or "",
                "duration_minutes": row["duration_minutes"],
                "price": row["price"] or "—",
                "is_active": row["is_active"],
            }
        except Exception as e:
            logging.error(f"Error getting service {service_id}: {e}")
            return None

    @staticmethod
    async def create_service(
        name: str,
        description: str,
        duration_minutes: int,
        price: str,
    ) -> Optional[int]:
        """Создать новую услугу"""
        try:
            service_id = await db_adapter.fetchval(
                """INSERT INTO services (name, description, duration_minutes, price, is_active)
                VALUES ($1, $2, $3, $4, true)
                RETURNING id""",
                name, description, duration_minutes, price
            )
            logging.info(f"Service created: {service_id} - {name}")
            return service_id
        except Exception as e:
            logging.error(f"Error creating service: {e}")
            return None

    @staticmethod
    async def update_service(
        service_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        price: Optional[str] = None,
    ) -> bool:
        """Обновить услугу"""
        try:
            updates = []
            params = []
            param_num = 1
            
            if name is not None:
                updates.append(f"name = ${param_num}")
                params.append(name)
                param_num += 1
            
            if description is not None:
                updates.append(f"description = ${param_num}")
                params.append(description)
                param_num += 1
            
            if duration_minutes is not None:
                updates.append(f"duration_minutes = ${param_num}")
                params.append(duration_minutes)
                param_num += 1
            
            if price is not None:
                updates.append(f"price = ${param_num}")
                params.append(price)
                param_num += 1
            
            if not updates:
                return False
            
            params.append(service_id)
            query = f"UPDATE services SET {', '.join(updates)} WHERE id = ${param_num}"
            
            result = await db_adapter.execute(query, *params)
            updated = "UPDATE 1" in result
            
            if updated:
                logging.info(f"Service updated: {service_id}")
            
            return updated
        except Exception as e:
            logging.error(f"Error updating service {service_id}: {e}")
            return False

    @staticmethod
    async def delete_service(service_id: int) -> bool:
        """Удалить услугу (мягкое удаление - установка is_active=false)"""
        try:
            result = await db_adapter.execute(
                "UPDATE services SET is_active = false WHERE id = $1",
                service_id
            )
            deleted = "UPDATE 1" in result
            
            if deleted:
                logging.info(f"Service deleted (soft): {service_id}")
            
            return deleted
        except Exception as e:
            logging.error(f"Error deleting service {service_id}: {e}")
            return False
