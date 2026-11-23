"""Store password-reset tokens as SHA-256 hashes, like refresh tokens.

Outstanding tokens are hashed in place, so reset links already sent keep
working. Postgres' built-in sha256() matches hashlib.sha256().hexdigest().

Revision ID: 0009
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE identity.password_reset_tokens RENAME COLUMN token TO token_hash")
    op.execute(
        "UPDATE identity.password_reset_tokens "
        "SET token_hash = encode(sha256(convert_to(token_hash, 'UTF8')), 'hex')"
    )
    op.execute("ALTER INDEX IF EXISTS identity.idx_reset_tokens_token RENAME TO idx_reset_tokens_token_hash")


def downgrade() -> None:
    # Hashes can't be turned back into tokens: invalidate the outstanding ones.
    op.execute("UPDATE identity.password_reset_tokens SET used_at = now() WHERE used_at IS NULL")
    op.execute("ALTER INDEX IF EXISTS identity.idx_reset_tokens_token_hash RENAME TO idx_reset_tokens_token")
    op.execute("ALTER TABLE identity.password_reset_tokens RENAME COLUMN token_hash TO token")
