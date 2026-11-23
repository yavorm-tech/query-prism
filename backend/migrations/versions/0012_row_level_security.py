"""Row-level security: a request can only see its own company's rows.

Every authenticated API request sets the session setting app.company_id on the
connections it uses (app/shared/db.py). With it set, these policies hide other
companies' rows from every query, so a query that forgets its company filter
returns nothing foreign instead of leaking.

Without it (sign-up, login, token links, the Celery worker, the outbox relay,
which have no tenant or work across tenants) the policies allow all rows; those
paths keep their own WHERE clauses as before.

Only tables with a company_id are covered. Rows reached through them are
covered by the join: chunks only through documents, team_members through teams,
tokens by their unguessable value. Superusers and table owners (migrations,
backups) bypass RLS; the app's role (0011) does not.

Revision ID: 0012
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# table -> its company column
TENANT_TABLES = {
    "identity.companies": "id",
    "identity.users": "company_id",
    "identity.teams": "company_id",
    "identity.invites": "company_id",
    "workspace.topics": "company_id",
    "knowledge.documents": "company_id",
    "retrieval.query_history": "company_id",
    "metering.subscriptions": "company_id",
    "audit.audit_log": "company_id",
}


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION shared.current_company() RETURNS uuid
        LANGUAGE sql STABLE PARALLEL SAFE AS
        $$ SELECT NULLIF(current_setting('app.company_id', true), '')::uuid $$
        """
    )
    for table, column in TENANT_TABLES.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING      (shared.current_company() IS NULL OR {column} = shared.current_company())
                WITH CHECK (shared.current_company() IS NULL OR {column} = shared.current_company())
            """
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS shared.current_company()")
