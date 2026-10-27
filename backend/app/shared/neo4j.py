"""
Neo4j driver — connection pool and session helper.
"""
import logging
from neo4j import AsyncGraphDatabase, AsyncDriver
from app.shared.config import get_settings
from app.shared.loop_local import LoopLocal

logger = logging.getLogger(__name__)


async def _create_driver() -> AsyncDriver:
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_url,
        auth=(settings.neo4j_user, settings.neo4j_password),
        max_connection_pool_size=20,
    )
    logger.info("Neo4j driver initialised")
    return driver


_driver: LoopLocal[AsyncDriver] = LoopLocal(_create_driver, closer=lambda driver: driver.close())


async def get_driver() -> AsyncDriver:
    return await _driver.get()


async def close_driver():
    await _driver.close()


async def run_query(cypher: str, parameters: dict | None = None) -> list[dict]:
    """Run a read Cypher query and return results as a list of dicts."""
    driver = await get_driver()
    async with driver.session() as session:
        result = await session.run(cypher, parameters or {})
        return [dict(record) for record in await result.data()]


async def run_write(cypher: str, parameters: dict | None = None) -> None:
    """Run a write Cypher query."""
    driver = await get_driver()
    async with driver.session() as session:
        await session.run(cypher, parameters or {})
