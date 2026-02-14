-- PostgreSQL Schema для Booking Bot
-- Version: 1.0.0
-- Date: 2026-02-14

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- TABLE: users
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    first_seen TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMPTZ,
    booking_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active);

-- =====================================================
-- TABLE: services
-- =====================================================
CREATE TABLE IF NOT EXISTS services (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    price DECIMAL(10, 2),
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_service_duration CHECK (duration_minutes > 0 AND duration_minutes <= 480)
);

CREATE INDEX IF NOT EXISTS idx_services_active ON services(is_active, display_order);

-- =====================================================
-- TABLE: bookings
-- =====================================================
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    user_id BIGINT NOT NULL,
    username VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    service_id INTEGER NOT NULL DEFAULT 1,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    
    CONSTRAINT unique_booking_slot UNIQUE (date, time),
    CONSTRAINT valid_booking_duration CHECK (duration_minutes > 0),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE RESTRICT
);

-- Composite indexes для производительности
CREATE INDEX IF NOT EXISTS idx_bookings_date_time ON bookings(date, time);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_service ON bookings(service_id);
CREATE INDEX IF NOT EXISTS idx_bookings_user_date ON bookings(user_id, date);
CREATE INDEX IF NOT EXISTS idx_bookings_created_at ON bookings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bookings_upcoming ON bookings(date, time) WHERE date >= CURRENT_DATE;

-- =====================================================
-- TABLE: analytics
-- =====================================================
CREATE TABLE IF NOT EXISTS analytics (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    event VARCHAR(100) NOT NULL,
    data TEXT,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analytics_user_event ON analytics(user_id, event);
CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_event ON analytics(event);

-- =====================================================
-- TABLE: feedback
-- =====================================================
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    booking_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    CONSTRAINT unique_feedback_per_booking UNIQUE (booking_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);

-- =====================================================
-- TABLE: blocked_slots
-- =====================================================
CREATE TABLE IF NOT EXISTS blocked_slots (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    reason TEXT,
    blocked_by BIGINT NOT NULL,
    blocked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_blocked_slot UNIQUE (date, time)
);

CREATE INDEX IF NOT EXISTS idx_blocked_date_time ON blocked_slots(date, time);
CREATE INDEX IF NOT EXISTS idx_blocked_by ON blocked_slots(blocked_by);

-- =====================================================
-- TABLE: admin_sessions
-- =====================================================
CREATE TABLE IF NOT EXISTS admin_sessions (
    user_id BIGINT PRIMARY KEY,
    message_id BIGINT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_admin_sessions_updated ON admin_sessions(updated_at);

-- =====================================================
-- TABLE: admins
-- =====================================================
CREATE TABLE IF NOT EXISTS admins (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    added_by BIGINT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    role VARCHAR(50) DEFAULT 'moderator',
    
    CONSTRAINT valid_role CHECK (role IN ('super_admin', 'moderator'))
);

CREATE INDEX IF NOT EXISTS idx_admins_added_at ON admins(added_at);
CREATE INDEX IF NOT EXISTS idx_admins_role ON admins(role);

-- =====================================================
-- TABLE: audit_log
-- =====================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_id VARCHAR(255),
    details JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (admin_id) REFERENCES admins(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_audit_admin ON audit_log(admin_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_details_gin ON audit_log USING gin (details);

-- =====================================================
-- TABLE: booking_history
-- =====================================================
CREATE TABLE IF NOT EXISTS booking_history (
    id SERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL,
    changed_by BIGINT NOT NULL,
    changed_by_type VARCHAR(20) NOT NULL CHECK (changed_by_type IN ('user', 'admin', 'system')),
    action VARCHAR(50) NOT NULL CHECK (action IN ('create', 'reschedule', 'cancel', 'service_change')),
    old_date DATE,
    old_time TIME,
    new_date DATE,
    new_time TIME,
    old_service_id INTEGER,
    new_service_id INTEGER,
    reason TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_booking_history_booking ON booking_history(booking_id);
CREATE INDEX IF NOT EXISTS idx_booking_history_changed_by ON booking_history(changed_by);
CREATE INDEX IF NOT EXISTS idx_booking_history_timestamp ON booking_history(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_booking_history_action ON booking_history(action);

-- =====================================================
-- TABLE: settings
-- =====================================================
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    value_type VARCHAR(20) DEFAULT 'string',
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: calendar_exceptions
-- =====================================================
CREATE TABLE IF NOT EXISTS calendar_exceptions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    is_working BOOLEAN NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_calendar_exceptions_date ON calendar_exceptions(date);

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Function: Проверка пересечения слотов
CREATE OR REPLACE FUNCTION check_slot_overlap(
    p_date DATE,
    p_time TIME,
    p_duration INTEGER
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM bookings
        WHERE date = p_date
        AND tsrange(
            (date + time)::timestamp,
            (date + time + make_interval(mins => duration_minutes))::timestamp
        ) && tsrange(
            (p_date + p_time)::timestamp,
            (p_date + p_time + make_interval(mins => p_duration))::timestamp
        )
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- Function: Автоудаление старых записей
CREATE OR REPLACE FUNCTION cleanup_old_bookings(days_to_keep INTEGER DEFAULT 90) 
RETURNS TABLE(deleted_count BIGINT, oldest_deleted DATE) AS $$
DECLARE
    v_deleted_count BIGINT;
    v_oldest_date DATE;
BEGIN
    SELECT MIN(date) INTO v_oldest_date
    FROM bookings
    WHERE date < CURRENT_DATE - make_interval(days => days_to_keep);
    
    DELETE FROM bookings
    WHERE date < CURRENT_DATE - make_interval(days => days_to_keep);
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    RETURN QUERY SELECT v_deleted_count, v_oldest_date;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Trigger: Обновление user stats при создании записи
CREATE OR REPLACE FUNCTION update_user_stats_on_booking()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO users (user_id, first_seen, last_active, booking_count)
    VALUES (NEW.user_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
    ON CONFLICT (user_id) DO UPDATE SET
        last_active = CURRENT_TIMESTAMP,
        booking_count = users.booking_count + 1;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_user_stats ON bookings;
CREATE TRIGGER trigger_update_user_stats
AFTER INSERT ON bookings
FOR EACH ROW
EXECUTE FUNCTION update_user_stats_on_booking();

-- Trigger: Обновление updated_at в settings
CREATE OR REPLACE FUNCTION update_settings_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_settings_timestamp ON settings;
CREATE TRIGGER trigger_update_settings_timestamp
BEFORE UPDATE ON settings
FOR EACH ROW
EXECUTE FUNCTION update_settings_timestamp();

-- =====================================================
-- VIEWS
-- =====================================================

-- View: Статистика по пользователям
CREATE OR REPLACE VIEW v_user_stats AS
SELECT 
    u.user_id,
    u.first_seen,
    u.last_active,
    u.booking_count,
    COUNT(DISTINCT b.id) FILTER (WHERE b.date >= CURRENT_DATE) as active_bookings,
    COALESCE(AVG(f.rating), 0) as avg_rating,
    COUNT(f.id) as feedback_count
FROM users u
LEFT JOIN bookings b ON u.user_id = b.user_id
LEFT JOIN feedback f ON u.user_id = f.user_id
GROUP BY u.user_id, u.first_seen, u.last_active, u.booking_count;

-- View: Загрузка по дням
CREATE OR REPLACE VIEW v_daily_load AS
SELECT 
    date,
    COUNT(*) as booking_count,
    SUM(duration_minutes) as total_minutes,
    COUNT(DISTINCT service_id) as service_variety,
    ROUND(SUM(duration_minutes)::NUMERIC / 60, 1) as total_hours
FROM bookings
WHERE date >= CURRENT_DATE
GROUP BY date
ORDER BY date;

-- View: Top клиенты
CREATE OR REPLACE VIEW v_top_clients AS
SELECT 
    u.user_id,
    u.booking_count,
    u.last_active,
    COALESCE(AVG(f.rating), 0) as avg_rating,
    COUNT(f.id) as feedback_given
FROM users u
LEFT JOIN feedback f ON u.user_id = f.user_id
WHERE u.booking_count > 0
GROUP BY u.user_id, u.booking_count, u.last_active
ORDER BY u.booking_count DESC, avg_rating DESC
LIMIT 100;
