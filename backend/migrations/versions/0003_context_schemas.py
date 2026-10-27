"""One schema per bounded context.

ALTER TABLE ... SET SCHEMA is a catalog-only change: no rows are rewritten,
and indexes, constraints, foreign keys and triggers move with their tables.
The database default search_path lists every context schema, so unqualified
SQL (the application, psql, pg_dump restores) keeps resolving. Which context
may *write* which schema is enforced by tests/architecture, not by grants.

Stop the old services before upgrading: their open connections were created
with the old search_path and would no longer find the tables.

Revision ID: 0003
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

OWNERSHIP = {
    "identity": ["companies", "teams", "users", "team_members", "invites", "password_reset_tokens"],
    "workspace": ["topics"],
    "knowledge": ["documents", "chunks"],
    "retrieval": ["query_history"],
    "metering": ["plan_limits"],
    "audit": ["audit_log"],
}
SEARCH_PATH = "identity, workspace, knowledge, retrieval, metering, audit, public"


def _set_database_search_path(path: str) -> None:
    op.execute(
        f"DO $$ BEGIN EXECUTE format('ALTER DATABASE %I SET search_path = {path}', current_database()); END $$"
    )


def upgrade() -> None:
    for schema, tables in OWNERSHIP.items():
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for table in tables:
            op.execute(f"ALTER TABLE IF EXISTS public.{table} SET SCHEMA {schema}")
    _set_database_search_path(SEARCH_PATH)
    op.execute(f"SET search_path = {SEARCH_PATH}")


def downgrade() -> None:
    for schema, tables in OWNERSHIP.items():
        for table in tables:
            op.execute(f"ALTER TABLE IF EXISTS {schema}.{table} SET SCHEMA public")
        op.execute(f"DROP SCHEMA IF EXISTS {schema}")
    _set_database_search_path('"$user", public')
    op.execute('SET search_path = "$user", public')
