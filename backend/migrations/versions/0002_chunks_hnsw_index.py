"""ANN index for vector search (was postgres/migrations/005).

Without it every chat query scans every chunk of every company. Built
CONCURRENTLY so it does not block ingestion; build time grows with chunk count.

Revision ID: 0002
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("SET maintenance_work_mem = '1GB'")
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS chunks_embedding_hv_hnsw_idx
                ON chunks USING hnsw (embedding_hv halfvec_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS chunks_embedding_hv_hnsw_idx")
