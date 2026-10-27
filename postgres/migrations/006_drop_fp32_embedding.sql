-- Migration 006: drop the full-precision embedding column
--
-- Search has always used embedding_hv (halfvec); the fp32 copy doubled vector
-- storage (~12 KB per chunk) and is no longer written by the worker.
-- DESTRUCTIVE: take a backup first (procedures/backup.sh). Apply after 005.

ALTER TABLE chunks DROP COLUMN IF EXISTS embedding;
