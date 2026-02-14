-- PostgreSQL схема для booking bot
-- Адаптирована из SQLite схемы в database/queries.py

-- ==============================================================================
-- ОСНОВНЫЕ ТАБЛИЦЫ
-- ==============================================================================

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    first_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Таблица услуг
CREATE TABLE IF NOT EXISTS services (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    display_order INTEGER NOT NULL DEFAULT 0
);

-- Таблица бронирований
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    username VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    service_id INTEGER NOT NULL DEFAULT 1 REFERENCES services(id) ON DELETE RESTRICT,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    UNIQUE(date, time)
);

-- Таблица заблокированных слотов
CREATE TABLE IF NOT EXISTS blocked_slots (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    reason TEXT,
    blocked_by BIGINT NOT NULL,
    blocked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, time)
);

-- Таблица администраторов
CREATE TABLE IF NOT EXISTS admins (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    added_by BIGINT,
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    role VARCHAR(50) NOT NULL DEFAULT 'moderator'
);

-- ==============================================================================
-- АНАЛИТИКА И ОТЗЫВЫ
-- ==============================================================================

-- Аналитика событий
CREATE TABLE IF NOT EXISTS analytics (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    event VARCHAR(100) NOT NULL,
    data TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Отзывы
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    booking_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- АУДИТ И ИСТОРИЯ
-- ==============================================================================

-- Аудит лог
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_id TEXT,
    details TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- История изменений бронирований
CREATE TABLE IF NOT EXISTS booking_history (
    id SERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL,
    changed_by BIGINT NOT NULL,
    changed_by_type VARCHAR(20) NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_date DATE,
    old_time TIME,
    new_date DATE,
    new_time TIME,
    old_service_id INTEGER,
    new_service_id INTEGER,
    reason TEXT,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- СЕССИИ И НАСТРОЙКИ
-- ==============================================================================

-- Сессии админов
CREATE TABLE IF NOT EXISTS admin_sessions (
    user_id BIGINT PRIMARY KEY,
    message_id INTEGER NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Настройки
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- КАЛЕНДАРЬ
-- ==============================================================================

-- Календарные настройки
CREATE TABLE IF NOT EXISTS calendar_settings (
    id SERIAL PRIMARY KEY,
    slot_interval_minutes INTEGER NOT NULL DEFAULT 60,
    work_hours_start INTEGER NOT NULL DEFAULT 9,
    work_hours_end INTEGER NOT NULL DEFAULT 18,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Интервалы слотов по дням
CREATE TABLE IF NOT EXISTS slot_intervals (
    id SERIAL PRIMARY KEY,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    interval_minutes INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(weekday)
);

-- ==============================================================================
-- ЛОКАЛИЗАЦИЯ (i18n)
-- ==============================================================================

-- Текстовые шаблоны
CREATE TABLE IF NOT EXISTS text_templates (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) NOT NULL UNIQUE,
    text TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- ИНДЕКСЫ
-- ==============================================================================

-- Бронирования
CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date, time);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_service ON bookings(service_id);
CREATE INDEX IF NOT EXISTS idx_bookings_date_time ON bookings(date, time);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_active_bookings ON bookings(user_id, date, time);

-- Аналитика
CREATE INDEX IF NOT EXISTS idx_analytics_user ON analytics(user_id, event);
CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics(timestamp);

-- Отзывы
CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp);
CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id);

-- Заблокированные слоты
CREATE INDEX IF NOT EXISTS idx_blocked_date ON blocked_slots(date, time);

-- Админы
CREATE INDEX IF NOT EXISTS idx_admins_added ON admins(added_at);

-- Аудит лог
CREATE INDEX IF NOT EXISTS idx_audit_admin ON audit_log(admin_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);

-- История бронирований
CREATE INDEX IF NOT EXISTS idx_booking_history_booking ON booking_history(booking_id);
CREATE INDEX IF NOT EXISTS idx_booking_history_changed_by ON booking_history(changed_by);
CREATE INDEX IF NOT EXISTS idx_booking_history_timestamp ON booking_history(changed_at);

-- ==============================================================================
-- ДЕФОЛТНЫЕ ДАННЫЕ
-- ==============================================================================

-- Дефолтная услуга
INSERT INTO services (name, duration_minutes, description, display_order)
VALUES ('Консультация', 60, 'Стандартная консультация 60 мин', 0)
ON CONFLICT DO NOTHING;

-- Дефолтные календарные настройки
INSERT INTO calendar_settings (slot_interval_minutes, work_hours_start, work_hours_end)
VALUES (60, 9, 18)
ON CONFLICT DO NOTHING;

-- ==============================================================================
-- ЗАКЛЮЧЕНИЕ
-- ==============================================================================
-- Все таблицы созданы с индексами и constraints
-- Готово к использованию в production
