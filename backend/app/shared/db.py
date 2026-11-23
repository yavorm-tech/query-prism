import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncIterator

import asyncpg
from app.shared.config import get_settings
from app.shared.loop_local import LoopLocal

# Each bounded context owns one schema (see migrations/versions/0003). Every
# connection can still resolve all of them so cross-context read joins keep
# working; write ownership is enforced by tests/architecture.
SEARCH_PATH = "identity, workspace, knowledge, retrieval, metering, audit, public"

logger = logging.getLogger(__name__)

# The company the current request acts for. Set by get_current_user; every
# connection acquired while it is set carries it as app.company_id, which the
# row-level security policies (migrations/versions/0012) filter on. Unset
# (sign-up, login, worker, relay) means unscoped.
_tenant: ContextVar[str | None] = ContextVar("tenant", default=None)


def set_tenant(company_id: str | None) -> None:
    _tenant.set(company_id)


def current_tenant() -> str | None:
    return _tenant.get()


@asynccontextmanager
async def request_scope() -> AsyncIterator[None]:
    """Each request starts unscoped and leaves no tenant behind."""
    token = _tenant.set(None)
    try:
        yield
    finally:
        _tenant.reset(token)


async def _apply_tenant(conn: asyncpg.Connection) -> None:
    """Pool setup hook, run on every acquire. A released connection is reset
    (asyncpg runs RESET ALL), so an unscoped acquire needs no round trip."""
    company_id = _tenant.get()
    if company_id:
        await conn.execute("SELECT set_config('app.company_id', $1, false)", company_id)


async def _create_pool() -> asyncpg.Pool:
    # Strip SQLAlchemy prefix — asyncpg uses plain DSN
    dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=2,
        max_size=10,
        command_timeout=60,
        server_settings={"search_path": SEARCH_PATH},
        setup=_apply_tenant,
    )


_pool: LoopLocal[asyncpg.Pool] = LoopLocal(_create_pool, closer=lambda pool: pool.close())


async def get_pool() -> asyncpg.Pool:
    return await _pool.get()


async def close_pool():
    await _pool.close()


@asynccontextmanager
async def connection(conn: asyncpg.Connection | None = None) -> AsyncIterator[asyncpg.Connection]:
    """Use the caller's connection (and so its transaction) if given, else a pooled one.

    Lets a service function take part in a unit of work:
        async def open_subscription(company_id, *, conn=None):
            async with db.connection(conn) as c: ...
    """
    if conn is not None:
        yield conn
        return
    pool = await get_pool()
    async with pool.acquire() as c:
        yield c


async def warn_if_rls_bypassed() -> None:
    """Row-level security does nothing for superusers, table owners and BYPASSRLS roles."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT r.rolname, r.rolsuper OR r.rolbypassrls AS bypass,
                   pg_has_role(r.rolname, (SELECT relowner FROM pg_class WHERE oid = 'knowledge.documents'::regclass), 'USAGE') AS owner
            FROM pg_roles r WHERE r.rolname = current_user
            """
        )
    if row and (row["bypass"] or row["owner"]):
        logger.warning(
            f"Connected to Postgres as {row['rolname']}, which bypasses row-level security: tenant "
            "isolation relies on application filters only. Set APP_DB_PASSWORD and connect api/worker as the app role."
        )
