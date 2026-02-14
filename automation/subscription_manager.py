#!/usr/bin/env python3
"""
Subscription Manager
Управление клиентами, подписками и Redis DB

Функции:
- Автоматическое выделение Redis DB (0-127)
- Отслеживание статуса подписок
- История платежей
- CRUD операции для клиентов
"""

import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# Константы
MAX_REDIS_DBS = 128  # Максимальное количество Redis баз


class SubscriptionManager:
    """Управление подписками клиентов"""
    
    def __init__(self, db_path: str = "subscriptions.db"):
        """
        Инициализация менеджера подписок
        
        Args:
            db_path: Путь к базе данных подписок
        """
        self.db_path = db_path
        self.max_redis_dbs = MAX_REDIS_DBS
        self._init_db()
    
    def _init_db(self):
        """Создание таблиц при первом запуске"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица клиентов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                client_id TEXT PRIMARY KEY,
                bot_token TEXT UNIQUE NOT NULL,
                bot_username TEXT,
                admin_telegram_id INTEGER NOT NULL,
                company_name TEXT,
                
                -- Redis configuration
                redis_db INTEGER UNIQUE NOT NULL,
                
                -- Subscription
                subscription_status TEXT DEFAULT 'active',
                subscription_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subscription_expires_at TIMESTAMP NOT NULL,
                subscription_plan TEXT DEFAULT 'monthly',
                
                -- Technical
                container_name TEXT,
                container_running INTEGER DEFAULT 0,
                
                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                CHECK (subscription_status IN ('trial', 'active', 'suspended', 'cancelled')),
                CHECK (redis_db >= 0 AND redis_db <= 127),
                CHECK (subscription_plan IN ('monthly', 'quarterly', 'yearly'))
            )
        """)
        
        # Таблица платежей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'RUB',
                payment_method TEXT,
                payment_status TEXT DEFAULT 'completed',
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transaction_id TEXT,
                notes TEXT,
                
                FOREIGN KEY (client_id) REFERENCES clients(client_id),
                CHECK (payment_status IN ('pending', 'completed', 'failed', 'refunded'))
            )
        """)
        
        # Таблица логов действий
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                action TEXT NOT NULL,
                details TEXT,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (client_id) REFERENCES clients(client_id)
            )
        """)
        
        # Индексы для быстрого поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clients_redis_db 
            ON clients(redis_db)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clients_status 
            ON clients(subscription_status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_client 
            ON payments(client_id)
        """)
        
        conn.commit()
        conn.close()
    
    def _find_available_redis_db(self) -> Optional[int]:
        """
        Найти первый свободный Redis DB номер (0-127)
        
        Returns:
            Номер свободного DB или None если все заняты
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Получить все занятые номера
        cursor.execute("SELECT redis_db FROM clients ORDER BY redis_db")
        used_dbs = {row[0] for row in cursor.fetchall()}
        conn.close()
        
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
            (client_id, redis_db) или None если нет свободных Redis DB
        
        Raises:
            ValueError: Если нет свободных Redis DB
        """
        # Найти свободный Redis DB
        redis_db = self._find_available_redis_db()
        
        if redis_db is None:
            raise ValueError(f"No available Redis DB slots (max {self.max_redis_dbs} clients)")
        
        client_id = str(uuid.uuid4())
        container_name = f"bot-client-{client_id[:8]}"
        expires_at = datetime.now() + timedelta(days=subscription_days)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO clients (
                    client_id, bot_token, bot_username, admin_telegram_id,
                    company_name, redis_db, container_name, subscription_expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                client_id, bot_token, bot_username, admin_telegram_id,
                company_name, redis_db, container_name, expires_at
            ))
            
            # Логирование
            cursor.execute("""
                INSERT INTO audit_log (client_id, action, details)
                VALUES (?, 'client_created', ?)
            """, (client_id, f"Redis DB: {redis_db}, Company: {company_name}"))
            
            conn.commit()
            return client_id, redis_db
        
        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise ValueError(f"Client already exists or Redis DB conflict: {e}")
        
        finally:
            conn.close()
    
    def get_client(self, client_id: str) -> Optional[Dict]:
        """
        Получить информацию о клиенте
        
        Args:
            client_id: ID клиента
        
        Returns:
            Словарь с данными клиента или None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM clients WHERE client_id = ?", (client_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT * FROM clients 
                WHERE subscription_status = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT * FROM clients 
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def check_expired_subscriptions(self) -> List[Dict]:
        """
        Найти клиентов с истекшей подпиской
        
        Returns:
            Список клиентов с истекшей подпиской
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        now = datetime.now()
        
        cursor.execute("""
            SELECT * FROM clients
            WHERE subscription_status = 'active'
              AND subscription_expires_at < ?
              AND container_running = 1
        """, (now,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def suspend_client(self, client_id: str, reason: str = "subscription_expired"):
        """
        Приостановить клиента
        
        Args:
            client_id: ID клиента
            reason: Причина приостановки
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE clients
            SET subscription_status = 'suspended',
                container_running = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ?
        """, (client_id,))
        
        # Логирование
        cursor.execute("""
            INSERT INTO audit_log (client_id, action, details)
            VALUES (?, 'client_suspended', ?)
        """, (client_id, reason))
        
        conn.commit()
        conn.close()
    
    def reactivate_client(self, client_id: str, extend_days: int = 30):
        """
        Возобновить клиента после оплаты
        
        Args:
            client_id: ID клиента
            extend_days: На сколько дней продлить
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Продлить подписку
        cursor.execute("""
            UPDATE clients
            SET subscription_status = 'active',
                subscription_expires_at = datetime(
                    CASE 
                        WHEN subscription_expires_at > CURRENT_TIMESTAMP 
                        THEN subscription_expires_at
                        ELSE CURRENT_TIMESTAMP
                    END,
                    '+' || ? || ' days'
                ),
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ?
        """, (extend_days, client_id))
        
        # Логирование
        cursor.execute("""
            INSERT INTO audit_log (client_id, action, details)
            VALUES (?, 'client_reactivated', ?)
        """, (client_id, f"Extended by {extend_days} days"))
        
        conn.commit()
        conn.close()
    
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Добавить платеж
        cursor.execute("""
            INSERT INTO payments (
                client_id, amount, currency, payment_method,
                transaction_id, notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (client_id, amount, currency, payment_method, transaction_id, notes))
        
        conn.commit()
        conn.close()
    
    def update_container_status(self, client_id: str, running: bool):
        """
        Обновить статус контейнера
        
        Args:
            client_id: ID клиента
            running: Запущен ли контейнер
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE clients
            SET container_running = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ?
        """, (1 if running else 0, client_id))
        
        conn.commit()
        conn.close()
    
    def delete_client(self, client_id: str):
        """
        Удалить клиента (освобождает Redis DB)
        
        Args:
            client_id: ID клиента
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Логирование перед удалением
        cursor.execute("""
            INSERT INTO audit_log (client_id, action, details)
            VALUES (?, 'client_deleted', 'Client removed from system')
        """, (client_id,))
        
        # Удалить клиента (каскадное удаление для audit_log настроено)
        cursor.execute("DELETE FROM clients WHERE client_id = ?", (client_id,))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict:
        """
        Получить статистику по клиентам
        
        Returns:
            Словарь со статистикой
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Общее количество клиентов
        cursor.execute("SELECT COUNT(*) FROM clients")
        total_clients = cursor.fetchone()[0]
        
        # По статусам
        cursor.execute("""
            SELECT subscription_status, COUNT(*)
            FROM clients
            GROUP BY subscription_status
        """)
        status_counts = dict(cursor.fetchall())
        
        # Свободные Redis DB
        cursor.execute("SELECT COUNT(DISTINCT redis_db) FROM clients")
        used_redis_dbs = cursor.fetchone()[0]
        available_redis_dbs = self.max_redis_dbs - used_redis_dbs
        
        # Доход за месяц
        cursor.execute("""
            SELECT SUM(amount)
            FROM payments
            WHERE payment_date >= datetime('now', '-30 days')
              AND payment_status = 'completed'
        """)
        monthly_revenue = cursor.fetchone()[0] or 0.0
        
        conn.close()
        
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
    
    print("📊 Subscription Manager Statistics:")
    print(f"  Max Redis DBs: {manager.max_redis_dbs}")
    stats = manager.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
