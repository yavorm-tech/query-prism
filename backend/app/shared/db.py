import asyncpg
from app.shared.config import get_settings
from app.shared.loop_local import LoopLocal

# Each bounded context owns one schema (see migrations/versions/0003). Every
# connection can still resolve all of them so cross-context read joins keep
# working; write ownership is enforced by tests/architecture.
SEARCH_PATH = "identity, workspace, knowledge, retrieval, metering, audit, public"


async def _create_pool() -> asyncpg.Pool:
    # Strip SQLAlchemy prefix — asyncpg uses plain DSN
    dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=2,
        max_size=10,
        command_timeout=60,
        server_settings={"search_path": SEARCH_PATH},
    )


_pool: LoopLocal[asyncpg.Pool] = LoopLocal(_create_pool, closer=lambda pool: pool.close())


async def get_pool() -> asyncpg.Pool:
    return await _pool.get()


async def close_pool():
    await _pool.close()
