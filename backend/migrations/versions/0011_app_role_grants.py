"""Least-privilege database role for the API and worker.

Until now the app connected as the database owner (a superuser): any SQL bug
could drop tables, and row-level security (0012) would not apply, since
superusers and table owners bypass it. From here on:

  - migrations run as the owner (MIGRATION_DATABASE_URL, else DATABASE_URL)
  - api and worker connect as APP_DB_USER (default qp_app): read/write rows in
    the module schemas, no DDL, no TRUNCATE, and audit.audit_log is append-only

The role is created here with APP_DB_PASSWORD (from the migrate container's
environment). Without a password it is created NOLOGIN, so nothing can connect
as it until one is set; the app then keeps working as the owner and logs a
warning at startup that row-level security is not enforced.

shared.apply_app_grants(role) holds the grants, so they can be re-applied after
a restore with --no-privileges (procedures/staging.sh refresh) and by later
migrations that add schemas.

Revision ID: 0011
"""
import os
import re

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

SCHEMAS = ["identity", "workspace", "knowledge", "retrieval", "metering", "audit", "shared"]


def app_role() -> str:
    role = os.environ.get("APP_DB_USER", "qp_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise ValueError(f"APP_DB_USER must be a plain lower-case identifier, got {role!r}")
    return role


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    role = app_role()
    password = os.environ.get("APP_DB_PASSWORD", "")
    login = f"LOGIN PASSWORD {_literal(password)}" if password else "NOLOGIN"
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {_literal(role)}) THEN
                CREATE ROLE {role} {login};
            ELSE
                ALTER ROLE {role} {login};
            END IF;
        END
        $$
        """
    )
    op.execute(f"ALTER ROLE {role} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS")

    schemas = ", ".join(_literal(s) for s in SCHEMAS)
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION shared.apply_app_grants(app_role name) RETURNS void
        LANGUAGE plpgsql AS $$
        DECLARE s text;
        BEGIN
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), app_role);
            -- Extensions (uuid-ossp, vector) live in public; the app needs their types and functions only.
            EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', app_role);
            FOREACH s IN ARRAY ARRAY[{schemas}] LOOP
                EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', s, app_role);
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO %I', s, app_role);
                EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO %I', s, app_role);
                EXECUTE format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA %I TO %I', s, app_role);
                -- Tables later migrations create (as this same owner) get the same grants.
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', s, app_role);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO %I', s, app_role);
            END LOOP;
            -- The audit trail is append-only for the application.
            EXECUTE format('REVOKE UPDATE, DELETE ON audit.audit_log FROM %I', app_role);
            -- Granting the function to the app role would let it re-grant; it never needs it.
            EXECUTE format('REVOKE EXECUTE ON FUNCTION shared.apply_app_grants(name) FROM %I', app_role);
        END
        $$
        """
    )
    op.execute("REVOKE EXECUTE ON FUNCTION shared.apply_app_grants(name) FROM PUBLIC")
    op.execute(f"SELECT shared.apply_app_grants({_literal(role)})")


def downgrade() -> None:
    role = app_role()
    # The role is cluster-wide (and may be connected), so it is kept; only this
    # database's privileges are removed. DROP ROLE by hand if it is unused.
    for s in SCHEMAS:
        op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {s} REVOKE ALL ON TABLES FROM {role}")
        op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {s} REVOKE ALL ON SEQUENCES FROM {role}")
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {s} FROM {role}")
        op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {s} FROM {role}")
        op.execute(f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {s} FROM {role}")
        op.execute(f"REVOKE USAGE ON SCHEMA {s} FROM {role}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {role}")
    op.execute("DROP FUNCTION IF EXISTS shared.apply_app_grants(name)")
