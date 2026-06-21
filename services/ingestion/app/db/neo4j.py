"""
Neo4j driver — connection pool and session helper.
"""
import logging
from neo4j import AsyncGraphDatabase, AsyncDriver
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_driver: AsyncDriver | None = None


async def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_url,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=20,
        )
        logger.info("Neo4j driver initialised")
    return _driver


async def close_driver():
    global _driver
    if _driver:
        await _driver.close()
        _driver = None


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
