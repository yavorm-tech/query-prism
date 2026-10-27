"""Baseline: schema from postgres/init.sql plus legacy migrations 001-004.

Fresh databases get that schema from init.sql (docker-entrypoint-initdb.d);
existing databases already have it. Either way there is nothing to do here,
so Alembic can be introduced without stamping.

Revision ID: 0001
"""
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
