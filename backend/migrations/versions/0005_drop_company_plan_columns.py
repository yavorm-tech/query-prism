"""Drop the plan and usage columns from identity.companies.

Revision 0004 moved the plan and counters to metering.subscriptions and left
these columns for one release as a rollback path. Nothing reads or writes them
any more. Downgrade re-creates them and fills them from metering.subscriptions
and metering.plan_limits.

Revision ID: 0005
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

COLUMNS = (
    "plan", "max_storage_mb", "max_users", "max_teams",
    "queries_used_this_month", "queries_reset_at", "storage_used_bytes",
    "max_queries_per_month", "max_storage_bytes",
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE identity.companies "
        + ", ".join(f"DROP COLUMN IF EXISTS {c}" for c in COLUMNS)
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE identity.companies
            ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'starter'
                CHECK (plan IN ('starter', 'free', 'team', 'business', 'enterprise')),
            ADD COLUMN IF NOT EXISTS max_storage_mb INT NOT NULL DEFAULT 50,
            ADD COLUMN IF NOT EXISTS max_users INT NOT NULL DEFAULT 3,
            ADD COLUMN IF NOT EXISTS max_teams INT NOT NULL DEFAULT 1,
            ADD COLUMN IF NOT EXISTS queries_used_this_month INT DEFAULT 0,
            ADD COLUMN IF NOT EXISTS queries_reset_at TIMESTAMPTZ DEFAULT date_trunc('month', now()),
            ADD COLUMN IF NOT EXISTS storage_used_bytes BIGINT DEFAULT 0,
            ADD COLUMN IF NOT EXISTS max_queries_per_month INT DEFAULT 50,
            ADD COLUMN IF NOT EXISTS max_storage_bytes BIGINT DEFAULT 52428800
        """
    )
    op.execute(
        """
        UPDATE identity.companies c SET
            plan                    = s.plan,
            queries_used_this_month = s.queries_used_this_month,
            queries_reset_at        = s.queries_reset_at,
            storage_used_bytes      = s.storage_used_bytes,
            max_storage_mb          = COALESCE(pl.max_storage_mb, -1),
            max_users               = COALESCE(pl.max_users, -1),
            max_teams               = COALESCE(pl.max_teams, -1),
            max_queries_per_month   = COALESCE(pl.max_queries, -1),
            max_storage_bytes       = COALESCE(pl.max_storage_mb::bigint * 1024 * 1024, -1)
        FROM metering.subscriptions s
        JOIN metering.plan_limits pl ON pl.plan = s.plan
        WHERE s.company_id = c.id
        """
    )
