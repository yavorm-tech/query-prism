"""Drop the unused full-precision chunks.embedding column (was manual migration 006).

Search has always used embedding_hv (halfvec); the fp32 copy doubled vector
storage (~12 KB per chunk) and nothing writes or reads it. A no-op on
databases built from the baseline, which never had it. Dropping a column is a
catalog change; the space comes back as rows are rewritten (or VACUUM FULL).

The downgrade re-adds the column empty: the values are gone.

Revision ID: 0010
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE knowledge.chunks DROP COLUMN IF EXISTS embedding")


def downgrade() -> None:
    op.execute("ALTER TABLE knowledge.chunks ADD COLUMN IF NOT EXISTS embedding vector(3072)")
