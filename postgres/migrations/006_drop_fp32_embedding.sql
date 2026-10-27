-- Migration 006: drop the full-precision embedding column
--
-- Search has always used embedding_hv (halfvec); the fp32 copy doubled vector
-- storage (~12 KB per chunk) and is no longer written by the worker.
-- DESTRUCTIVE: take a backup first (procedures/backup.sh). Kept out of the
-- automatic Alembic chain on purpose; run by hand once the release is stable:
--   docker exec -i rag_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < postgres/migrations/006_drop_fp32_embedding.sql

ALTER TABLE chunks DROP COLUMN IF EXISTS embedding;
