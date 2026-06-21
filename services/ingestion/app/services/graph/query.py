"""
Graph query service — given a user query, find related chunk IDs via Neo4j traversal.
Used by the retrieval pipeline (Phase 4) to augment vector search results.
"""
import logging
from app.db.neo4j import run_query
from app.services.graph.ner import extract_entities

logger = logging.getLogger(__name__)


async def find_related_chunk_ids(
    query_text: str,
    max_hops: int = 2,
    max_chunks: int = 20,
) -> list[str]:
    """
    1. Extract entities from the query using GPT-4o-mini
    2. Find those entities in Neo4j
    3. Traverse up to max_hops to find related entities
    4. Collect chunk IDs that mention those entities
    """
    chunk_entities = await extract_entities("query", query_text)
    if not chunk_entities.entities:
        logger.debug("No entities found in query — skipping graph traversal")
        return []

    entity_names = [e.normalized for e in chunk_entities.entities]
    logger.debug(f"Query entities: {entity_names}")

    results = await run_query(
        """
        UNWIND $names AS name
        MATCH (e:Entity {normalized: name})

        OPTIONAL MATCH (c1:Chunk)-[:MENTIONS]->(e)
        OPTIONAL MATCH (e)-[:RELATED_TO*1..2]-(e2:Entity)
        OPTIONAL MATCH (c2:Chunk)-[:MENTIONS]->(e2)

        WITH collect(DISTINCT c1.id) + collect(DISTINCT c2.id) AS all_chunk_ids
        UNWIND all_chunk_ids AS chunk_id
        WITH chunk_id
        WHERE chunk_id IS NOT NULL
        RETURN DISTINCT chunk_id
        LIMIT $limit
        """,
        {"names": entity_names, "limit": max_chunks},
    )

    chunk_ids = [r["chunk_id"] for r in results if r.get("chunk_id")]
    logger.debug(f"Graph traversal found {len(chunk_ids)} related chunks")
    return chunk_ids


async def get_entity_neighbourhood(entity_name: str, hops: int = 2) -> dict:
    """Return the neighbourhood of an entity — useful for debugging."""
    results = await run_query(
        """
        MATCH (e:Entity)
        WHERE e.normalized = $name OR $name IN e.aliases
        OPTIONAL MATCH (e)-[:RELATED_TO*1..$hops]-(neighbour:Entity)
        RETURN e,
               collect(DISTINCT {
                 entity: neighbour.name,
                 type:   neighbour.type
               }) AS neighbours
        LIMIT 1
        """,
        {"name": entity_name.lower(), "hops": hops},
    )
    return results[0] if results else {}
