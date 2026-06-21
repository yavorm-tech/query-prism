"""
Neo4j schema — run once on startup to create constraints and indexes.
Idempotent: safe to call on every restart.
"""
import logging
from app.db.neo4j import run_write

logger = logging.getLogger(__name__)

SCHEMA_QUERIES = [
    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id  IF NOT EXISTS FOR (c:Chunk)  REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT doc_id    IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    """
    CREATE FULLTEXT INDEX entity_name_ft IF NOT EXISTS
    FOR (e:Entity) ON EACH [e.name, e.aliases]
    """,
    "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
]


async def init_schema():
    logger.info("Initialising Neo4j schema...")
    for query in SCHEMA_QUERIES:
        try:
            await run_write(query.strip())
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.warning(f"Schema query warning: {e}")
    logger.info("Neo4j schema ready")
