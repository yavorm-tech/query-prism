"""Move plan and usage counters out of identity.companies into metering.

Metering wrote counters straight into identity's companies rows. They now live
in metering.subscriptions, one row per company, backfilled from companies.
The old companies columns stay for one release as a rollback path and are no
longer read or written by the application; a later revision drops them.

Revision ID: 0004
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS metering.subscriptions (
            company_id               UUID PRIMARY KEY REFERENCES identity.companies(id) ON DELETE CASCADE,
            plan                     TEXT NOT NULL DEFAULT 'starter' REFERENCES metering.plan_limits(plan),
            queries_used_this_month  INT  NOT NULL DEFAULT 0,
            queries_reset_at         TIMESTAMPTZ NOT NULL DEFAULT date_trunc('month', now()),
            storage_used_bytes       BIGINT NOT NULL DEFAULT 0,
            created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        INSERT INTO metering.subscriptions
            (company_id, plan, queries_used_this_month, queries_reset_at, storage_used_bytes)
        SELECT id,
               plan,
               COALESCE(queries_used_this_month, 0),
               COALESCE(queries_reset_at, date_trunc('month', now())),
               COALESCE(storage_used_bytes, 0)
        FROM identity.companies
        ON CONFLICT (company_id) DO NOTHING
        """
    )
    for column in ("plan", "queries_used_this_month", "queries_reset_at", "storage_used_bytes"):
        op.execute(
            f"COMMENT ON COLUMN identity.companies.{column} IS "
            f"'DEPRECATED: moved to metering.subscriptions (revision 0004); not maintained'"
        )


def downgrade() -> None:
    # Copy current values back so the previous release sees up-to-date counters.
    op.execute(
        """
        UPDATE identity.companies c SET
            plan = s.plan,
            queries_used_this_month = s.queries_used_this_month,
            queries_reset_at = s.queries_reset_at,
            storage_used_bytes = s.storage_used_bytes
        FROM metering.subscriptions s
        WHERE s.company_id = c.id
        """
    )
    op.execute("DROP TABLE IF EXISTS metering.subscriptions")
