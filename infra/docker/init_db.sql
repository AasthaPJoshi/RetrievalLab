-- =============================================================================
-- RetrievalLab — infra/docker/init_db.sql
-- =============================================================================
-- PURPOSE : Initialization script run by PostgreSQL on first container start.
--           Enables the pgvector extension so we can store embedding vectors
--           directly in Postgres alongside relational metadata.
--
-- WHEN IT RUNS : Automatically on first `docker compose up`, not on subsequent
--                restarts (Postgres skips init scripts if data dir exists).
--
-- WHAT IT DOES:
--   1. Enables pgvector extension (provides the `vector` column type)
--   2. Creates a dedicated schema for RetrievalLab tables
--   3. Sets default search path
-- =============================================================================

-- Enable pgvector extension (provided by pgvector/pgvector:pg16 image)
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation support
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable full-text search dictionary
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Set default search path for the retrievallab user
ALTER USER retrievallab SET search_path TO public;

-- Confirm setup
DO $$
BEGIN
  RAISE NOTICE 'RetrievalLab database initialized with pgvector, uuid-ossp, pg_trgm';
END $$;
