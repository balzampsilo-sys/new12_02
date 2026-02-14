-- =====================================================
-- PostgreSQL Database Initialization Script
-- =====================================================
-- Создает отдельные базы данных для каждого клиента
-- Для изоляции данных в multi-tenant архитектуре
--
-- Usage: Добавьте новые строки CREATE DATABASE для новых клиентов
-- =====================================================

-- Проверяем версию PostgreSQL
DO $$
BEGIN
    IF current_setting('server_version_num')::int < 140000 THEN
        RAISE EXCEPTION 'PostgreSQL 14+ required. Current version: %', version();
    END IF;
END $$;

-- Отключаем автокоммит для транзакции
SET client_min_messages TO WARNING;

-- =====================================================
-- Создание БД для клиентов (Template)
-- =====================================================

-- Client 001 - Первый клиент
CREATE DATABASE client_001_db
    WITH 
    OWNER = booking_admin
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1
    TEMPLATE = template0;

COMMENT ON DATABASE client_001_db IS 'Booking bot database for client 001';

-- Client 002 - Второй клиент
CREATE DATABASE client_002_db
    WITH 
    OWNER = booking_admin
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1
    TEMPLATE = template0;

COMMENT ON DATABASE client_002_db IS 'Booking bot database for client 002';

-- Client 003 - Третий клиент
CREATE DATABASE client_003_db
    WITH 
    OWNER = booking_admin
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1
    TEMPLATE = template0;

COMMENT ON DATABASE client_003_db IS 'Booking bot database for client 003';

-- =====================================================
-- Для добавления новых клиентов:
-- =====================================================
-- Скопируйте блок выше и измените номер клиента:
--
-- CREATE DATABASE client_004_db
--     WITH OWNER = booking_admin
--     ENCODING = 'UTF8'
--     LC_COLLATE = 'en_US.utf8'
--     LC_CTYPE = 'en_US.utf8'
--     TABLESPACE = pg_default
--     CONNECTION LIMIT = -1
--     TEMPLATE = template0;
--
-- COMMENT ON DATABASE client_004_db IS 'Booking bot database for client 004';
-- =====================================================

-- Вывод информации
\echo ''
\echo '✅ Databases created successfully'
\echo ''
\echo 'Created databases:'
\echo '  - client_001_db'
\echo '  - client_002_db'
\echo '  - client_003_db'
\echo ''
\echo 'Next step: Create users and grant permissions (init_users.sql)'
\echo ''
