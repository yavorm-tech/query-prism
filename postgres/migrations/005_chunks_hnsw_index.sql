-- Migration 005: ANN index for vector search
--
-- Without this index every chat query scans every chunk of every company.
-- Run outside a transaction block (CONCURRENTLY), e.g.:
--   docker exec -i rag_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < postgres/migrations/005_chunks_hnsw_index.sql
-- Build time scales with chunk count; maintenance_work_mem (1GB in postgresql.conf)
-- should hold the graph, otherwise the build spills and slows down sharply.
-- Requires pgvector >= 0.8 for the iterative scan the retriever enables.

SET maintenance_work_mem = '1GB';

CREATE INDEX CONCURRENTLY IF NOT EXISTS chunks_embedding_hv_hnsw_idx
    ON chunks USING hnsw (embedding_hv halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);

ANALYZE chunks;
