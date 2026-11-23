"""Transactional outbox for domain events (ADR-010).

Events are written in the same transaction as the change they describe and
delivered after commit; a relay redelivers what did not finish.

Revision ID: 0008
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS shared")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS shared.outbox (
            id            BIGSERIAL PRIMARY KEY,
            event_type    TEXT NOT NULL,
            payload       JSONB NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            claimed_at    TIMESTAMPTZ,
            processed_at  TIMESTAMPTZ,
            attempts      INT NOT NULL DEFAULT 0,
            available_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_error    TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outbox_pending ON shared.outbox (id) WHERE processed_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outbox_processed ON shared.outbox (processed_at) WHERE processed_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS shared.outbox")
    op.execute("DROP SCHEMA IF EXISTS shared")
