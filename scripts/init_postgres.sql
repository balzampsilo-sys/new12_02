-- PostgreSQL инициализация для multi-tenant SaaS
-- Создает отдельные БД для каждого клиента с изоляцией

-- ==============================================================================
-- ФУНКЦИЯ: Создание БД и пользователя для клиента
-- ==============================================================================
CREATE OR REPLACE FUNCTION create_client_database(
    p_client_id TEXT,
    p_password TEXT DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_db_name TEXT;
    v_user_name TEXT;
    v_password TEXT;
BEGIN
    -- Генерация имен
    v_db_name := 'booking_' || p_client_id;
    v_user_name := 'user_' || p_client_id;
    
    -- Генерация пароля если не передан
    IF p_password IS NULL THEN
        v_password := md5(random()::text || clock_timestamp()::text);
    ELSE
        v_password := p_password;
    END IF;
    
    -- Создание БД
    EXECUTE format('CREATE DATABASE %I OWNER booking_admin ENCODING ''UTF8'' LC_COLLATE ''en_US.UTF-8'' LC_CTYPE ''en_US.UTF-8'' TEMPLATE template0', v_db_name);
    
    -- Создание пользователя
    EXECUTE format('CREATE USER %I WITH PASSWORD %L', v_user_name, v_password);
    
    -- Выдача прав
    EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE %I TO %I', v_db_name, v_user_name);
    
    RAISE NOTICE '✅ Client database created: % (user: %, password: %)', v_db_name, v_user_name, v_password;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- СОЗДАНИЕ БД ДЛЯ КЛИЕНТОВ (примеры)
-- ==============================================================================
-- Раскомментируйте и замените client_001 на реальные ID клиентов

-- Пример 1: Создание БД для client_001
-- SELECT create_client_database('client_001', 'secure_password_here');

-- Пример 2: Создание БД с авто-генерацией пароля
-- SELECT create_client_database('client_002');

-- ==============================================================================
-- ИЗОЛЯЦИЯ ШЕМ
-- ==============================================================================
-- После создания БД нужно выполнить изоляцию:
--
-- \c booking_client_001
-- REVOKE ALL ON SCHEMA public FROM PUBLIC;
-- GRANT ALL ON SCHEMA public TO user_client_001;
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO user_client_001;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO user_client_001;

-- ==============================================================================
-- УТИЛИТЫ
-- ==============================================================================

-- Просмотр всех БД клиентов
CREATE OR REPLACE FUNCTION list_client_databases()
RETURNS TABLE (database_name TEXT, owner TEXT, size TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        datname::TEXT,
        pg_catalog.pg_get_userbyid(datdba)::TEXT,
        pg_size_pretty(pg_database_size(datname))::TEXT
    FROM pg_database
    WHERE datname LIKE 'booking_%'
    ORDER BY datname;
END;
$$ LANGUAGE plpgsql;

-- Удаление БД клиента
CREATE OR REPLACE FUNCTION drop_client_database(p_client_id TEXT)
RETURNS VOID AS $$
DECLARE
    v_db_name TEXT;
    v_user_name TEXT;
BEGIN
    v_db_name := 'booking_' || p_client_id;
    v_user_name := 'user_' || p_client_id;
    
    -- Отключение активных соединений
    EXECUTE format(
        'SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %L AND pid <> pg_backend_pid()',
        v_db_name
    );
    
    -- Удаление БД
    EXECUTE format('DROP DATABASE IF EXISTS %I', v_db_name);
    
    -- Удаление пользователя
    EXECUTE format('DROP USER IF EXISTS %I', v_user_name);
    
    RAISE NOTICE '✅ Client database dropped: %', v_db_name;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- ЗАКЛЮЧЕНИЕ
-- ==============================================================================
RAISE NOTICE '';
RAISE NOTICE '✅ PostgreSQL initialization complete!';
RAISE NOTICE '📌 To create a client database, run:';
RAISE NOTICE '   SELECT create_client_database(''client_001'', ''your_password'');';
RAISE NOTICE '📌 To list all client databases, run:';
RAISE NOTICE '   SELECT * FROM list_client_databases();';
RAISE NOTICE '';
