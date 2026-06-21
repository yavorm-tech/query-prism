"""
Graph writer — upserts entities, chunks, documents and relationships into Neo4j.

Node types:
  (:Document  {id, filename, source_type})
  (:Chunk     {id, document_id, chunk_index, content_preview})
  (:Entity    {id, name, type, normalized, aliases})

Relationship types:
  (:Document)-[:HAS_CHUNK]->(:Chunk)
  (:Chunk)-[:MENTIONS]->(:Entity)
  (:Entity)-[:RELATED_TO {predicate, weight, chunk_ids}]->(:Entity)
"""
import hashlib
import logging
from app.db.neo4j import run_write, get_driver
from app.services.graph.ner import ChunkEntities
from app.services.graph.relations import Relation

logger = logging.getLogger(__name__)


def _entity_id(normalized_name: str, entity_type: str) -> str:
    """Stable deterministic ID so the same entity merges across chunks."""
    key = f"{entity_type}::{normalized_name}"
    return hashlib.md5(key.encode()).hexdigest()


async def upsert_document_node(
    document_id: str,
    filename: str,
    source_type: str,
) -> None:
    await run_write(
        """
        MERGE (d:Document {id: $id})
        SET d.filename    = $filename,
            d.source_type = $source_type
        """,
        {"id": document_id, "filename": filename, "source_type": source_type},
    )


async def upsert_chunk_node(
    chunk_id: str,
    document_id: str,
    chunk_index: int,
    content: str,
) -> None:
    preview = content[:200].replace("\n", " ")
    await run_write(
        """
        MERGE (c:Chunk {id: $id})
        SET c.document_id     = $document_id,
            c.chunk_index     = $chunk_index,
            c.content_preview = $preview

        WITH c
        MATCH (d:Document {id: $document_id})
        MERGE (d)-[:HAS_CHUNK]->(c)
        """,
        {
            "id": chunk_id,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "preview": preview,
        },
    )


async def upsert_entities_and_mentions(chunk_entities: ChunkEntities) -> None:
    """Upsert all entities from a chunk and create MENTIONS edges."""
    if not chunk_entities.entities:
        return

    entity_params = [
        {
            "id":         _entity_id(e.normalized, e.type),
            "name":       e.text,
            "normalized": e.normalized,
            "type":       e.type,
        }
        for e in chunk_entities.entities
    ]

    driver = await get_driver()
    async with driver.session() as session:
        await session.run(
            """
            UNWIND $entities AS ent
            MERGE (e:Entity {id: ent.id})
            ON CREATE SET e.name       = ent.name,
                          e.normalized = ent.normalized,
                          e.type       = ent.type,
                          e.aliases    = [ent.normalized]
            ON MATCH  SET e.aliases    = CASE
                            WHEN NOT ent.normalized IN e.aliases
                            THEN e.aliases + ent.normalized
                            ELSE e.aliases
                          END

            WITH e, ent
            MATCH (c:Chunk {id: $chunk_id})
            MERGE (c)-[:MENTIONS]->(e)
            """,
            {"entities": entity_params, "chunk_id": chunk_entities.chunk_id},
        )


async def delete_document_graph(document_id: str) -> None:
    """
    Remove all Neo4j data for a document:
      1. Strip this document's chunk IDs from RELATED_TO edge arrays; delete edges with no remaining chunks.
      2. Delete all Chunk nodes (and their MENTIONS / HAS_CHUNK relationships).
      3. Delete the Document node.
      4. Delete Entity nodes that are now orphaned (no remaining MENTIONS pointing to them).
    """
    driver = await get_driver()
    async with driver.session() as session:
        # Step 1 — collect chunk IDs, then scrub them from RELATED_TO edges
        await session.run(
            """
            MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
            WITH collect(c.id) AS cids
            MATCH ()-[r:RELATED_TO]->()
            WHERE ANY(cid IN cids WHERE cid IN r.chunk_ids)
            SET r.chunk_ids = [x IN r.chunk_ids WHERE NOT x IN cids],
                r.weight    = size([x IN r.chunk_ids WHERE NOT x IN cids])
            """,
            {"doc_id": document_id},
        )

        # Step 2 — remove now-empty RELATED_TO edges
        await session.run(
            """
            MATCH ()-[r:RELATED_TO]->()
            WHERE size(r.chunk_ids) = 0
            DELETE r
            """
        )

        # Step 3 — delete Chunk nodes (DETACH removes HAS_CHUNK + MENTIONS)
        await session.run(
            """
            MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
            DETACH DELETE c
            """,
            {"doc_id": document_id},
        )

        # Step 4 — delete the Document node
        await session.run(
            "MATCH (d:Document {id: $doc_id}) DETACH DELETE d",
            {"doc_id": document_id},
        )

        # Step 5 — clean up orphaned Entity nodes
        await session.run(
            """
            MATCH (e:Entity)
            WHERE NOT ()-[:MENTIONS]->(e)
            DELETE e
            """
        )

    logger.info(f"[{document_id}] Neo4j graph nodes deleted")


async def upsert_relations(
    relations: list[Relation],
    chunk_id: str,
) -> None:
    """Upsert RELATED_TO edges between entities."""
    if not relations:
        return

    driver = await get_driver()
    async with driver.session() as session:
        for rel in relations:
            await session.run(
                """
                MATCH (s:Entity {normalized: $subject})
                MATCH (o:Entity {normalized: $object})
                MERGE (s)-[r:RELATED_TO {predicate: $predicate}]->(o)
                ON CREATE SET r.chunk_ids = [$chunk_id],
                              r.weight    = 1
                ON MATCH  SET r.chunk_ids = CASE
                                WHEN NOT $chunk_id IN r.chunk_ids
                                THEN r.chunk_ids + $chunk_id
                                ELSE r.chunk_ids
                              END,
                              r.weight = r.weight + 1
                """,
                {
                    "subject":   rel.subject,
                    "object":    rel.obj,
                    "predicate": rel.predicate,
                    "chunk_id":  chunk_id,
                },
            )
