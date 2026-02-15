#!/usr/bin/env python3
"""
Docker Deploy Manager - Автономное создание клиентских ботов

Использует Docker Python SDK для:
- Создания контейнеров без внешних зависимостей
- Управления жизненным циклом ботов
- Real-time мониторинга
- Автоматического rollback при ошибках

Master Bot может создавать ботов самостоятельно!
"""

import os
import json
import uuid
import asyncio
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from pathlib import Path

try:
    import docker
    from docker.errors import DockerException, APIError, ContainerError
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    print("⚠️ Docker SDK not installed: pip install docker")

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    print("⚠️ psycopg2 not installed: pip install psycopg2-binary")

logger = logging.getLogger(__name__)


class DockerDeployManager:
    """
    Управление деплоем через Docker API
    
    Запускается ВНУТРИ Master Bot контейнера и управляет
    клиентскими контейнерами через Docker Socket
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        schema: str = "master_bot",
        docker_socket: str = "unix://var/run/docker.sock",
        network_name: str = "booking-network"
    ):
        """
        Инициализация Docker Deploy Manager
        
        Args:
            database_url: PostgreSQL connection string
            schema: PostgreSQL schema для master_bot
            docker_socket: Путь к Docker socket
            network_name: Имя Docker network
        """
        if not DOCKER_AVAILABLE:
            raise RuntimeError("Docker SDK not available. Install: pip install docker")
        
        if not POSTGRES_AVAILABLE:
            raise RuntimeError("psycopg2 not available. Install: pip install psycopg2-binary")
        
        # Docker client
        try:
            self.docker = docker.DockerClient(base_url=docker_socket)
            self.docker.ping()
            logger.info(f"✅ Connected to Docker: {self.docker.version()['Version']}")
        except DockerException as e:
            raise RuntimeError(f"Failed to connect to Docker: {e}")
        
        # Database
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://booking_user:SecurePass2026!@postgres:5432/booking_saas"
        )
        self.schema = schema
        self.network_name = network_name
        
        # Проверить сеть
        self._ensure_network()
    
    def _ensure_network(self):
        """Проверить/создать Docker network"""
        try:
            self.docker.networks.get(self.network_name)
            logger.info(f"✅ Network exists: {self.network_name}")
        except docker.errors.NotFound:
            logger.info(f"📡 Creating network: {self.network_name}")
            self.docker.networks.create(
                self.network_name,
                driver="bridge",
                check_duplicate=True
            )
    
    def _get_db_connection(self):
        """Получить PostgreSQL connection"""
        return psycopg2.connect(self.database_url)
    
    def _allocate_redis_db(self) -> int:
        """
        Атомарное выделение Redis DB
        
        Returns:
            Номер свободного Redis DB (0-127)
        
        Raises:
            RuntimeError: Если все DB заняты
        """
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Атомарная операция: найти и зарезервировать
            cursor.execute(f"""
                WITH available AS (
                    SELECT generate_series(0, 127) AS db_num
                    EXCEPT
                    SELECT redis_db FROM {self.schema}.clients
                )
                SELECT db_num FROM available ORDER BY db_num LIMIT 1
            """)
            
            result = cursor.fetchone()
            if not result:
                raise RuntimeError("All Redis DB slots are occupied (max 128)")
            
            conn.commit()
            return result[0]
    
    def _register_client(
        self,
        bot_token: str,
        admin_telegram_id: int,
        company_name: str,
        redis_db: int,
        container_name: str,
        subscription_days: int = 30,
        bot_username: Optional[str] = None
    ) -> str:
        """
        Зарегистрировать клиента в БД
        
        Returns:
            client_id (UUID)
        """
        client_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(days=subscription_days)
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute(f"""
                    INSERT INTO {self.schema}.clients (
                        client_id, bot_token, bot_username, admin_telegram_id,
                        company_name, redis_db, container_name, 
                        subscription_expires_at, subscription_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    client_id, bot_token, bot_username, admin_telegram_id,
                    company_name, redis_db, container_name,
                    expires_at, 'active'
                ))
                
                # Audit log
                cursor.execute(f"""
                    INSERT INTO {self.schema}.audit_log (client_id, action, details)
                    VALUES (%s, %s, %s)
                """, (
                    client_id,
                    'client_created',
                    json.dumps({
                        'company': company_name,
                        'redis_db': redis_db,
                        'container': container_name
                    })
                ))
                
                conn.commit()
                return client_id
            
            except psycopg2.IntegrityError as e:
                conn.rollback()
                raise ValueError(f"Client registration failed: {e}")
    
    def _delete_client_record(self, client_id: str):
        """Удалить клиента из БД (rollback)"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.schema}.clients WHERE client_id = %s", (client_id,))
            conn.commit()
    
    def _create_schema_in_postgres(self, schema_name: str):
        """
        Создать отдельную schema для клиента
        
        Args:
            schema_name: Имя schema (например client_abc123)
        """
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Создать schema
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            
            # Скопировать структуру таблиц из public schema
            # (предполагается, что в репозитории есть init_schema.sql)
            tables = [
                'bookings', 'services', 'users', 'admins', 
                'blocked_slots', 'feedback', 'statistics',
                'reminders', 'service_categories', 'working_hours',
                'holidays', 'custom_texts'
            ]
            
            for table in tables:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {schema_name}.{table} 
                    (LIKE public.{table} INCLUDING ALL)
                """)
            
            conn.commit()
            logger.info(f"✅ Schema created: {schema_name}")
    
    async def deploy_client(
        self,
        bot_token: str,
        admin_telegram_id: int,
        company_name: str,
        subscription_days: int = 30,
        bot_username: Optional[str] = None
    ) -> Dict:
        """
        Полный цикл деплоя клиента
        
        Args:
            bot_token: Токен Telegram бота
            admin_telegram_id: ID администратора
            company_name: Название компании
            subscription_days: Длительность подписки
            bot_username: Username бота
        
        Returns:
            Dict с результатом деплоя
        """
        client_id = None
        container = None
        redis_db = None
        
        try:
            logger.info(f"🚀 Starting deployment: {company_name}")
            
            # 1. Выделить Redis DB (атомарно)
            redis_db = self._allocate_redis_db()
            logger.info(f"📊 Allocated Redis DB: {redis_db}")
            
            # 2. Сгенерировать имена
            client_short_id = str(uuid.uuid4())[:8]
            container_name = f"booking-client-{client_short_id}"
            client_schema = f"client_{client_short_id}"
            
            # 3. Создать schema в PostgreSQL
            self._create_schema_in_postgres(client_schema)
            
            # 4. Зарегистрировать в БД
            client_id = self._register_client(
                bot_token=bot_token,
                admin_telegram_id=admin_telegram_id,
                company_name=company_name,
                redis_db=redis_db,
                container_name=container_name,
                subscription_days=subscription_days,
                bot_username=bot_username
            )
            logger.info(f"✅ Client registered: {client_id}")
            
            # 5. Создать и запустить контейнер
            container = await self._create_container(
                container_name=container_name,
                bot_token=bot_token,
                admin_id=admin_telegram_id,
                redis_db=redis_db,
                pg_schema=client_schema,
                redis_key_prefix=f"client_{client_short_id}:"
            )
            
            logger.info(f"✅ Container started: {container_name}")
            
            # 6. Обновить статус
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE {self.schema}.clients
                    SET container_running = TRUE, updated_at = NOW()
                    WHERE client_id = %s
                """, (client_id,))
                conn.commit()
            
            # 7. Успех!
            return {
                'success': True,
                'client_id': client_id,
                'container_name': container_name,
                'redis_db': redis_db,
                'schema': client_schema,
                'company_name': company_name,
                'admin_telegram_id': admin_telegram_id
            }
        
        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}", exc_info=True)
            
            # ROLLBACK
            if container:
                try:
                    container.stop(timeout=5)
                    container.remove()
                    logger.info("🔄 Rolled back container")
                except Exception as re:
                    logger.error(f"Failed to remove container: {re}")
            
            if client_id:
                try:
                    self._delete_client_record(client_id)
                    logger.info("🔄 Rolled back database record")
                except Exception as re:
                    logger.error(f"Failed to delete client: {re}")
            
            return {
                'success': False,
                'error': str(e),
                'company_name': company_name
            }
    
    async def _create_container(
        self,
        container_name: str,
        bot_token: str,
        admin_id: int,
        redis_db: int,
        pg_schema: str,
        redis_key_prefix: str
    ):
        """
        Создать и запустить Docker контейнер
        
        Returns:
            Docker container object
        """
        # Получить образ master bot (переиспользуем)
        try:
            image = self.docker.images.get("new12_02-bot-master")
        except docker.errors.ImageNotFound:
            # Собрать если не существует
            logger.info("🔨 Building bot image...")
            image, logs = self.docker.images.build(
                path=".",
                tag="new12_02-bot-master",
                rm=True
            )
        
        # Переменные окружения
        environment = {
            'BOT_TOKEN': bot_token,
            'ADMIN_IDS': str(admin_id),
            'DB_TYPE': 'postgresql',
            'DATABASE_URL': self.database_url,
            'PG_SCHEMA': pg_schema,
            'REDIS_ENABLED': 'true',
            'REDIS_HOST': 'redis',
            'REDIS_PORT': '6379',
            'REDIS_DB': str(redis_db),
            'REDIS_KEY_PREFIX': redis_key_prefix,
            'TIMEZONE': 'Europe/Moscow',
            'WORK_HOURS_START': '9',
            'WORK_HOURS_END': '21',
            'MAX_BOOKINGS_PER_USER': '3',
            'CANCELLATION_HOURS': '24',
        }
        
        # Создать контейнер
        container = self.docker.containers.create(
            image=image.id,
            name=container_name,
            command="python main.py",
            environment=environment,
            network=self.network_name,
            restart_policy={'Name': 'unless-stopped'},
            detach=True,
            labels={
                'managed_by': 'master_bot',
                'client_type': 'booking_bot',
                'schema': pg_schema
            },
            healthcheck={
                'test': ['CMD-SHELL', 'pgrep -f main.py || exit 1'],
                'interval': 30000000000,  # 30s in nanoseconds
                'timeout': 10000000000,   # 10s
                'retries': 3
            },
            log_config={
                'type': 'json-file',
                'config': {
                    'max-size': '10m',
                    'max-file': '3'
                }
            }
        )
        
        # Запустить
        container.start()
        
        # Подождать готовности (до 30 секунд)
        for i in range(30):
            await asyncio.sleep(1)
            container.reload()
            
            if container.status == 'running':
                # Проверить логи на ошибки
                logs = container.logs(tail=50).decode('utf-8')
                if 'Bot started successfully' in logs or '🤖' in logs:
                    logger.info(f"✅ Container healthy: {container_name}")
                    return container
                elif 'error' in logs.lower() or 'exception' in logs.lower():
                    raise RuntimeError(f"Container started but has errors: {logs[-500:]}")
            elif container.status == 'exited':
                logs = container.logs().decode('utf-8')
                raise RuntimeError(f"Container exited immediately: {logs}")
        
        # Timeout
        raise RuntimeError("Container failed to become healthy within 30 seconds")
    
    def stop_client(self, client_id: str) -> bool:
        """
        Остановить клиентского бота
        
        Args:
            client_id: UUID клиента
        
        Returns:
            True если успешно
        """
        try:
            # Получить container_name из БД
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT container_name FROM {self.schema}.clients WHERE client_id = %s",
                    (client_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    logger.error(f"Client not found: {client_id}")
                    return False
                
                container_name = result[0]
            
            # Остановить контейнер
            container = self.docker.containers.get(container_name)
            container.stop(timeout=10)
            
            # Обновить статус
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE {self.schema}.clients
                    SET container_running = FALSE, updated_at = NOW()
                    WHERE client_id = %s
                """, (client_id,))
                conn.commit()
            
            logger.info(f"✅ Client stopped: {client_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to stop client: {e}")
            return False
    
    def restart_client(self, client_id: str) -> bool:
        """
        Перезапустить клиентского бота
        
        Args:
            client_id: UUID клиента
        
        Returns:
            True если успешно
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT container_name FROM {self.schema}.clients WHERE client_id = %s",
                    (client_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return False
                
                container_name = result[0]
            
            container = self.docker.containers.get(container_name)
            container.restart(timeout=10)
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE {self.schema}.clients
                    SET container_running = TRUE, updated_at = NOW()
                    WHERE client_id = %s
                """, (client_id,))
                conn.commit()
            
            logger.info(f"✅ Client restarted: {client_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to restart client: {e}")
            return False
    
    def delete_client(self, client_id: str) -> bool:
        """
        Полностью удалить клиента (контейнер + БД)
        
        Args:
            client_id: UUID клиента
        
        Returns:
            True если успешно
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT container_name, redis_db FROM {self.schema}.clients WHERE client_id = %s",
                    (client_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return False
                
                container_name, redis_db = result
            
            # Удалить контейнер
            try:
                container = self.docker.containers.get(container_name)
                container.stop(timeout=5)
                container.remove()
                logger.info(f"✅ Container removed: {container_name}")
            except docker.errors.NotFound:
                logger.warning(f"Container not found: {container_name}")
            
            # Удалить из БД
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Audit log
                cursor.execute(f"""
                    INSERT INTO {self.schema}.audit_log (client_id, action, details)
                    VALUES (%s, %s, %s)
                """, (client_id, 'client_deleted', f'Container: {container_name}, Redis DB: {redis_db}'))
                
                # Удалить клиента
                cursor.execute(
                    f"DELETE FROM {self.schema}.clients WHERE client_id = %s",
                    (client_id,)
                )
                
                conn.commit()
            
            logger.info(f"✅ Client deleted: {client_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to delete client: {e}")
            return False
    
    def get_container_stats(self, client_id: str) -> Optional[Dict]:
        """
        Получить статистику контейнера
        
        Args:
            client_id: UUID клиента
        
        Returns:
            Dict со статистикой или None
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT container_name FROM {self.schema}.clients WHERE client_id = %s",
                    (client_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return None
                
                container_name = result[0]
            
            container = self.docker.containers.get(container_name)
            stats = container.stats(stream=False)
            
            # Упростить статистику
            return {
                'status': container.status,
                'cpu_usage': stats.get('cpu_stats', {}),
                'memory_usage': stats.get('memory_stats', {}),
                'network': stats.get('networks', {})
            }
        
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return None


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Тест
    async def test():
        manager = DockerDeployManager()
        
        result = await manager.deploy_client(
            bot_token="TEST_TOKEN",
            admin_telegram_id=123456789,
            company_name="Test Company",
            subscription_days=30
        )
        
        print(json.dumps(result, indent=2))
    
    asyncio.run(test())
