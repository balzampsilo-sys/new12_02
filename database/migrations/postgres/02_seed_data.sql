-- Initial seed data
-- Version: 1.0.0
-- Date: 2026-02-14

BEGIN;

-- Default service
INSERT INTO services (id, name, description, duration_minutes, price, display_order, is_active)
VALUES (1, 'Консультация', 'Стандартная консультация', 60, 1000.00, 1, TRUE)
ON CONFLICT (id) DO NOTHING;

-- Reset sequence
SELECT setval('services_id_seq', COALESCE((SELECT MAX(id) FROM services), 1));

-- Default settings
INSERT INTO settings (key, value, value_type, description) VALUES
    ('work_hours_start', '9', 'integer', 'Начало рабочего дня'),
    ('work_hours_end', '18', 'integer', 'Конец рабочего дня'),
    ('max_bookings_per_user', '3', 'integer', 'Максимум активных записей на пользователя'),
    ('cancellation_hours', '24', 'integer', 'За сколько часов можно отменить запись'),
    ('reminder_hours_before_24h', '24', 'integer', 'Напоминание за 24 часа'),
    ('reminder_hours_before_2h', '2', 'integer', 'Напоминание за 2 часа'),
    ('reminder_hours_before_1h', '1', 'integer', 'Напоминание за 1 час'),
    ('feedback_hours_after', '2', 'integer', 'Запрос отзыва через N часов после встречи'),
    ('service_location', 'Москва, ул. Примерная, 1', 'string', 'Адрес оказания услуг'),
    ('calendar_max_months_ahead', '3', 'integer', 'На сколько месяцев вперёд можно бронировать')
ON CONFLICT (key) DO NOTHING;

COMMIT;
