"""Baseline: the original schema (former postgres/init.sql + legacy SQL migrations 001-004).

Creates the schema from migrations/sql/0001_baseline.sql when the database is
empty, so `alembic upgrade head` alone builds a fresh database. Databases that
already have the schema (created by the old init.sql) skip it; they are past
this revision anyway.

Revision ID: 0001
"""
import pathlib

from alembic import op
from sqlalchemy import text

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

BASELINE_SQL = pathlib.Path(__file__).resolve().parents[1] / "sql" / "0001_baseline.sql"


def split_statements(sql: str) -> list[str]:
    """Split on ';' at the end of a line, keeping $$-quoted function bodies whole."""
    statements, current, in_dollar = [], [], False
    for line in sql.splitlines():
        if line.strip().startswith("--") and not in_dollar:
            continue
        current.append(line)
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        if not in_dollar and line.rstrip().endswith(";"):
            statement = "\n".join(current).strip()
            if statement.rstrip(";").strip():
                statements.append(statement)
            current = []
    if "\n".join(current).strip():
        raise ValueError("Baseline SQL does not end with ';'")
    return statements


def upgrade() -> None:
    exists = op.get_bind().execute(
        text("SELECT 1 FROM pg_tables WHERE tablename = 'companies'")
    ).scalar()
    if exists:
        return
    for statement in split_statements(BASELINE_SQL.read_text()):
        op.execute(statement)


def downgrade() -> None:
    # Dropping the whole schema is never what a downgrade should do.
    pass
