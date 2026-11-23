"""Refresh tokens for short-lived access tokens (ADR-009).

Access JWTs now live 15 minutes. A refresh token (opaque, stored only as a
SHA-256 hash) is rotated on every use; all tokens issued from one login share
a family_id so reuse of a rotated token can revoke the whole family.

Revision ID: 0006
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS identity.refresh_tokens (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id     UUID NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
            family_id   UUID NOT NULL,
            token_hash  TEXT UNIQUE NOT NULL,
            expires_at  TIMESTAMPTZ NOT NULL,
            used_at     TIMESTAMPTZ,
            revoked_at  TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON identity.refresh_tokens(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_family ON identity.refresh_tokens(family_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS identity.refresh_tokens")
