#!/usr/bin/env python3
"""
Subscription Manager - PostgreSQL Edition
Управление клиентами, подписками и Redis DB

Функции:
- Автоматическое выделение Redis DB (0-127)
- Отслеживание статуса подписок
- История платежей
- CRUD операции для клиентов
"""

import os
import uuid
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from contextlib import contextmanager

# Константы
MAX_REDIS_DBS = 128  # Максимальное количество Redis баз


class SubscriptionManager:
    """Управление подписками клиентов"""
    
    def __init__(self, database_url: Optional[str] = None, schema: str = "master_bot"):
        """
        Инициализация менеджера подписок
        
        Args:
            database_url: PostgreSQL connection string (если None - берется из ENV)
            schema: PostgreSQL schema для таблиц (по умолчанию master_bot)
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://booking_user:SecurePass2026!@localhost:5432/booking_saas"
        )
        self.schema = schema
        self.max_redis_dbs = MAX_REDIS_DBS
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """Context manager для работы с подключением"""
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Создание schema и таблиц при первом запуске"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Создать schema если не существует
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema}")
            
            # Таблица клиентов
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema}.clients (
                    client_id UUID PRIMARY KEY,
                    bot_token TEXT UNIQUE NOT NULL,
                    bot_username TEXT,
                    admin_telegram_id BIGINT NOT NULL,
                    company_name TEXT,
                    
                    -- Redis configuration
                    redis_db INTEGER UNIQUE NOT NULL CHECK (redis_db >= 0 AND redis_db <= 127),
                    
                    -- Subscription
                    subscription_status TEXT DEFAULT 'active' CHECK (subscription_status IN ('trial', 'active', 'suspended', 'cancelled')),
                    subscription_started_at TIMESTAMPTZ DEFAULT NOW(),
                    subscription_expires_at TIMESTAMPTZ NOT NULL,
                    subscription_plan TEXT DEFAULT 'monthly' CHECK (subscription_plan IN ('monthly', 'quarterly', 'yearly')),
                    
                    -- Technical
                    container_name TEXT,
                    container_running BOOLEAN DEFAULT FALSE,
                    
                    -- Timestamps
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Таблица платежей
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema}.payments (
                    payment_id SERIAL PRIMARY KEY,
                    client_id UUID NOT NULL REFERENCES {self.schema}.clients(client_id) ON DELETE CASCADE,
                    amount NUMERIC(10, 2) NOT NULL,
                    currency TEXT DEFAULT 'RUB',
                    payment_method TEXT,
                    payment_status TEXT DEFAULT 'completed' CHECK (payment_status IN ('pending', 'completed', 'failed', 'refunded')),
                    payment_date TIMESTAMPTZ DEFAULT NOW(),
                    transaction_id TEXT,
                    notes TEXT
                )
            """)
            
            # Таблица логов действий
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema}.audit_log (
                    log_id SERIAL PRIMARY KEY,
                    client_id UUID REFERENCES {self.schema}.clients(client_id) ON DELETE CASCADE,
                    action TEXT NOT NULL,
                    details TEXT,
                    performed_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Индексы для быстрого поиска
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_clients_redis_db 
                ON {self.schema}.clients(redis_db)
            """)
            
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_clients_status 
                ON {self.schema}.clients(subscription_status)
            """)
            
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_payments_client 
                ON {self.schema}.payments(client_id)
            """)
            
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_audit_log_client 
                ON {self.schema}.audit_log(client_id)
            """)
    
    def _find_available_redis_db(self) -> Optional[int]:
        """
        Найти первый свободный Redis DB номер (0-127)
        
        Returns:
            Номер свободного DB или None если все заняты
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Получить все занятые номера
            cursor.execute(f"SELECT redis_db FROM {self.schema}.clients ORDER BY redis_db")
            used_dbs = {row[0] for row in cursor.fetchall()}
        
        # Найти первый свободный (0-127)
        for db_num in range(self.max_redis_dbs):
            if db_num not in used_dbs:
                return db_num
        
        return None
    
    def add_client(
        self,
        bot_token: str,
        admin_telegram_id: int,
        company_name: Optional[str] = None,
        subscription_days: int = 30,
        bot_username: Optional[str] = None
    ) -> Tuple[str, int]:
        """
        Добавить нового клиента
        
        Args:
            bot_token: Токен бота
            admin_telegram_id: Telegram ID администратора
            company_name: Название компании
            subscription_days: Дней подписки (по умолчанию 30)
            bot_username: Username бота
        
        Returns:
            (client_id, redis_db)
        
        Raises:
            ValueError: Если нет свободных Redis DB или клиент уже существует
        """
        # Найти свободный Redis DB
        redis_db = self._find_available_redis_db()
        
        if redis_db is None:
            raise ValueError(f"No available Redis DB slots (max {self.max_redis_dbs} clients)")
        
        client_id = str(uuid.uuid4())
        container_name = f"bot-client-{client_id[:8]}"
        expires_at = datetime.now() + timedelta(days=subscription_days)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(f"""
                    INSERT INTO {self.schema}.clients (
                        client_id, bot_token, bot_username, admin_telegram_id,
                        company_name, redis_db, container_name, subscription_expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    client_id, bot_token, bot_username, admin_telegram_id,
                    company_name, redis_db, container_name, expires_at
                ))
                
                # Логирование
                cursor.execute(f"""
                    INSERT INTO {self.schema}.audit_log (client_id, action, details)
                    VALUES (%s, %s, %s)
                """, (client_id, 'client_created', f"Redis DB: {redis_db}, Company: {company_name}"))
            
            return client_id, redis_db
        
        except psycopg2.IntegrityError as e:
            raise ValueError(f"Client already exists or Redis DB conflict: {e}")
    
    def get_client(self, client_id: str) -> Optional[Dict]:
        """
        Получить информацию о клиенте
        
        Args:
            client_id: ID клиента
        
        Returns:
            Словарь с данными клиента или None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute(f"SELECT * FROM {self.schema}.clients WHERE client_id = %s", (client_id,))
            row = cursor.fetchone()
        
        if row:
            result = dict(row)
            # Конвертировать UUID в строку
            if 'client_id' in result:
                result['client_id'] = str(result['client_id'])
            # Конвертировать datetime в строку ISO
            for key in ['subscription_started_at', 'subscription_expires_at', 'created_at', 'updated_at']:
                if key in result and result[key]:
                    result[key] = result[key].isoformat()
            return result
        return None
    
    def list_clients(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Получить список клиентов
        
        Args:
            status: Фильтр по статусу (active/suspended/cancelled)
            limit: Максимальное количество результатов
        
        Returns:
            Список клиентов
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            if status:
                cursor.execute(f"""
                    SELECT * FROM {self.schema}.clients 
                    WHERE subscription_status = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (status, limit))
            else:
                cursor.execute(f"""
                    SELECT * FROM {self.schema}.clients 
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
            
            rows = cursor.fetchall()
        
        # Конвертировать данные
        results = []
        for row in rows:
            result = dict(row)
            if 'client_id' in result:
                result['client_id'] = str(result['client_id'])
            for key in ['subscription_started_at', 'subscription_expires_at', 'created_at', 'updated_at']:
                if key in result and result[key]:
                    result[key] = result[key].isoformat()
            results.append(result)
        
        return results
    
    def check_expired_subscriptions(self) -> List[Dict]:
        """
        Найти клиентов с истекшей подпиской
        
        Returns:
            Список клиентов с истекшей подпиской
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute(f"""
                SELECT * FROM {self.schema}.clients
                WHERE subscription_status = 'active'
                  AND subscription_expires_at < NOW()
                  AND container_running = TRUE
            """)
            
            rows = cursor.fetchall()
        
        results = []
        for row in rows:
            result = dict(row)
            if 'client_id' in result:
                result['client_id'] = str(result['client_id'])
            for key in ['subscription_started_at', 'subscription_expires_at', 'created_at', 'updated_at']:
                if key in result and result[key]:
                    result[key] = result[key].isoformat()
            results.append(result)
        
        return results
    
    def suspend_client(self, client_id: str, reason: str = "subscription_expired"):
        """
        Приостановить клиента
        
        Args:
            client_id: ID клиента
            reason: Причина приостановки
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(f"""
                UPDATE {self.schema}.clients
                SET subscription_status = 'suspended',
                    container_running = FALSE,
                    updated_at = NOW()
                WHERE client_id = %s
            """, (client_id,))
            
            # Логирование
            cursor.execute(f"""
                INSERT INTO {self.schema}.audit_log (client_id, action, details)
                VALUES (%s, %s, %s)
            """, (client_id, 'client_suspended', reason))
    
    def reactivate_client(self, client_id: str, extend_days: int = 30):
        """
        Возобновить клиента после оплаты
        
        Args:
            client_id: ID клиента
            extend_days: На сколько дней продлить
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Продлить подписку
            cursor.execute(f"""
                UPDATE {self.schema}.clients
                SET subscription_status = 'active',
                    subscription_expires_at = CASE 
                        WHEN subscription_expires_at > NOW() 
                        THEN subscription_expires_at + INTERVAL '%s days'
                        ELSE NOW() + INTERVAL '%s days'
                    END,
                    updated_at = NOW()
                WHERE client_id = %s
            """ % (extend_days, extend_days, '%s'), (client_id,))
            
            # Логирование
            cursor.execute(f"""
                INSERT INTO {self.schema}.audit_log (client_id, action, details)
                VALUES (%s, %s, %s)
            """, (client_id, 'client_reactivated', f"Extended by {extend_days} days"))
    
    def extend_subscription(self, client_id: str, days: int) -> bool:
        """
        Продлить подписку (алиас для reactivate_client)
        
        Args:
            client_id: ID клиента
            days: Количество дней
        
        Returns:
            True если успешно
        """
        try:
            self.reactivate_client(client_id, extend_days=days)
            return True
        except Exception:
            return False
    
    def add_payment(
        self,
        client_id: str,
        amount: float,
        currency: str = "RUB",
        payment_method: str = "manual",
        transaction_id: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """
        Добавить платеж и продлить подписку
        
        Args:
            client_id: ID клиента
            amount: Сумма
            currency: Валюта
            payment_method: Способ оплаты
            transaction_id: ID транзакции
            notes: Заметки
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Добавить платеж
            cursor.execute(f"""
                INSERT INTO {self.schema}.payments (
                    client_id, amount, currency, payment_method,
                    transaction_id, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (client_id, amount, currency, payment_method, transaction_id, notes))
    
    def update_container_status(self, client_id: str, running: bool):
        """
        Обновить статус контейнера
        
        Args:
            client_id: ID клиента
            running: Запущен ли контейнер
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(f"""
                UPDATE {self.schema}.clients
                SET container_running = %s,
                    updated_at = NOW()
                WHERE client_id = %s
            """, (running, client_id))
    
    def delete_client(self, client_id: str):
        """
        Удалить клиента (освобождает Redis DB)
        
        Args:
            client_id: ID клиента
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Логирование перед удалением
            cursor.execute(f"""
                INSERT INTO {self.schema}.audit_log (client_id, action, details)
                VALUES (%s, %s, %s)
            """, (client_id, 'client_deleted', 'Client removed from system'))
            
            # Удалить клиента (каскадное удаление настроено)
            cursor.execute(f"DELETE FROM {self.schema}.clients WHERE client_id = %s", (client_id,))
    
    def get_statistics(self) -> Dict:
        """
        Получить статистику по клиентам
        
        Returns:
            Словарь со статистикой
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Общее количество клиентов
            cursor.execute(f"SELECT COUNT(*) FROM {self.schema}.clients")
            total_clients = cursor.fetchone()[0]
            
            # По статусам
            cursor.execute(f"""
                SELECT subscription_status, COUNT(*)
                FROM {self.schema}.clients
                GROUP BY subscription_status
            """)
            status_counts = dict(cursor.fetchall())
            
            # Свободные Redis DB
            cursor.execute(f"SELECT COUNT(DISTINCT redis_db) FROM {self.schema}.clients")
            used_redis_dbs = cursor.fetchone()[0]
            available_redis_dbs = self.max_redis_dbs - used_redis_dbs
            
            # Доход за месяц
            cursor.execute(f"""
                SELECT COALESCE(SUM(amount), 0)
                FROM {self.schema}.payments
                WHERE payment_date >= NOW() - INTERVAL '30 days'
                  AND payment_status = 'completed'
            """)
            monthly_revenue = float(cursor.fetchone()[0])
        
        return {
            "total_clients": total_clients,
            "active_clients": status_counts.get("active", 0),
            "suspended_clients": status_counts.get("suspended", 0),
            "trial_clients": status_counts.get("trial", 0),
            "available_redis_dbs": available_redis_dbs,
            "monthly_revenue": monthly_revenue
        }


if __name__ == "__main__":
    # Пример использования
    manager = SubscriptionManager()
    
    print("📊 Subscription Manager Statistics (PostgreSQL):")
    print(f"  Max Redis DBs: {manager.max_redis_dbs}")
    print(f"  Schema: {manager.schema}")
    stats = manager.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
