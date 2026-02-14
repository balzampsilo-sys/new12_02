-- =====================================================
-- PostgreSQL Users & Permissions Initialization
-- =====================================================
-- Создает отдельных пользователей с ограниченными правами
-- Для безопасности и изоляции
--
-- SECURITY NOTE:
-- - Каждый клиент имеет доступ только к своей БД
-- - Пароли должны храниться в Vault или secrets manager
-- =====================================================

SET client_min_messages TO WARNING;

-- =====================================================
-- Client 001 User
-- =====================================================

-- Создание пользователя
CREATE USER client_001_user WITH
    LOGIN
    PASSWORD 'client_001_strong_password_CHANGE_ME'
    CONNECTION LIMIT 50
    VALID UNTIL 'infinity';

COMMENT ON ROLE client_001_user IS 'Application user for client 001';

-- Предоставление прав на БД
\c client_001_db

-- Отзываем публичные права
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE client_001_db FROM PUBLIC;

-- Предоставляем права клиенту
GRANT CONNECT ON DATABASE client_001_db TO client_001_user;
GRANT USAGE, CREATE ON SCHEMA public TO client_001_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO client_001_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO client_001_user;

-- Автоматические права для будущих таблиц
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO client_001_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO client_001_user;

-- =====================================================
-- Client 002 User
-- =====================================================

\c postgres

CREATE USER client_002_user WITH
    LOGIN
    PASSWORD 'client_002_strong_password_CHANGE_ME'
    CONNECTION LIMIT 50
    VALID UNTIL 'infinity';

COMMENT ON ROLE client_002_user IS 'Application user for client 002';

\c client_002_db

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE client_002_db FROM PUBLIC;

GRANT CONNECT ON DATABASE client_002_db TO client_002_user;
GRANT USAGE, CREATE ON SCHEMA public TO client_002_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO client_002_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO client_002_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO client_002_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO client_002_user;

-- =====================================================
-- Client 003 User
-- =====================================================

\c postgres

CREATE USER client_003_user WITH
    LOGIN
    PASSWORD 'client_003_strong_password_CHANGE_ME'
    CONNECTION LIMIT 50
    VALID UNTIL 'infinity';

COMMENT ON ROLE client_003_user IS 'Application user for client 003';

\c client_003_db

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE client_003_db FROM PUBLIC;

GRANT CONNECT ON DATABASE client_003_db TO client_003_user;
GRANT USAGE, CREATE ON SCHEMA public TO client_003_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO client_003_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO client_003_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO client_003_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO client_003_user;

-- =====================================================
-- Read-only monitoring user (optional)
-- =====================================================

\c postgres

CREATE USER monitoring_user WITH
    LOGIN
    PASSWORD 'monitoring_readonly_password_CHANGE_ME'
    CONNECTION LIMIT 10;

COMMENT ON ROLE monitoring_user IS 'Read-only user for monitoring and metrics';

-- Даем права только на чтение на всех БД
DO $$
DECLARE
    db_name TEXT;
BEGIN
    FOR db_name IN
        SELECT datname FROM pg_database
        WHERE datname LIKE 'client_%_db'
    LOOP
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO monitoring_user', db_name);
    END LOOP;
END $$;

-- =====================================================
-- Вывод информации
-- =====================================================

\c postgres

\echo ''
\echo '✅ Users created successfully'
\echo ''
\echo 'Created users:'
\echo '  - client_001_user (access to client_001_db)'
\echo '  - client_002_user (access to client_002_db)'
\echo '  - client_003_user (access to client_003_db)'
\echo '  - monitoring_user (read-only access)'
\echo ''
\echo '⚠️  SECURITY WARNING:'
\echo '  CHANGE ALL DEFAULT PASSWORDS IMMEDIATELY!'
\echo '  Store passwords in Vault or secure secrets manager'
\echo ''
\echo 'Password change command:'
\echo "  ALTER USER client_001_user WITH PASSWORD 'new_secure_password';"
\echo ''
