-- =============================================================
-- SignalStream — PostgreSQL Database Initialization Script
-- =============================================================
-- Runs automatically on container startup via /docker-entrypoint-initdb.d

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. Verify Extensions
DO $$
BEGIN
    RAISE NOTICE 'SignalStream PostgreSQL extensions successfully initialized:';
    RAISE NOTICE '  - uuid-ossp';
    RAISE NOTICE '  - pgcrypto';
    RAISE NOTICE '  - vector (pgvector)';
    RAISE NOTICE '  - pg_trgm';
END $$;
