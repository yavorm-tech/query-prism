"""
Knowledge graph extraction Celery task.
Automatically chained after ingest_document completes.
Can also be triggered manually:
  - Single document: build_knowledge_graph.delay(document_id)
  - All documents:   build_knowledge_graph_bulk.delay()
"""
import logging
from app.shared.celery import celery_app
from app.shared.db import get_pool
from app.shared.loop_local import run_in_fresh_loop
from app.shared.observability import bind, clear_context

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.graph_worker.build_knowledge_graph",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="ingestion",
)
def build_knowledge_graph(self, document_id: str):
    clear_context()
    bind(document_id=document_id, task="build_knowledge_graph")
    logger.info(f"[{document_id}] Starting KG extraction")
    try:
        run_in_fresh_loop(lambda: _build_kg_async(document_id))
    except Exception as exc:
        logger.error(f"[{document_id}] KG extraction failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.graph_worker.build_knowledge_graph_bulk",
    queue="ingestion",
)
def build_knowledge_graph_bulk():
    """Reprocess KG for all completed documents."""
    run_in_fresh_loop(_bulk_async)


async def _build_kg_async(document_id: str):
    from app.knowledge.graph.schema import init_schema
    from app.shared.ai.ner import extract_entities_batch
    from app.knowledge.graph.relations import extract_relations_batch
    from app.knowledge.graph.writer import (
        upsert_document_node,
        upsert_chunk_node,
        upsert_entities_and_mentions,
        upsert_relations,
    )

    await init_schema()

    # Fetch document + chunks
    pool = await get_pool()
    async with pool.acquire() as conn:
        doc = await conn.fetchrow(
            "SELECT id, filename, source_type FROM documents WHERE id = $1",
            document_id,
        )
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        rows = await conn.fetch(
            "SELECT id, chunk_index, content FROM chunks WHERE document_id = $1 ORDER BY chunk_index",
            document_id,
        )

    if not rows:
        logger.warning(f"[{document_id}] No chunks found — skipping KG extraction")
        return

    chunks = [(str(r["id"]), r["chunk_index"], r["content"]) for r in rows]
    logger.info(f"[{document_id}] Processing {len(chunks)} chunks for KG")

    # Upsert document + chunk nodes
    await upsert_document_node(document_id, doc["filename"], doc["source_type"])
    for chunk_id, chunk_index, content in chunks:
        await upsert_chunk_node(chunk_id, document_id, chunk_index, content)

    # Batch NER with GPT-4o-mini
    chunk_text_pairs = [(cid, content) for cid, _, content in chunks]
    chunk_entities_list = await extract_entities_batch(chunk_text_pairs)
    entity_map = {ce.chunk_id: ce for ce in chunk_entities_list}

    # Upsert entities + MENTIONS edges
    for chunk_entities in chunk_entities_list:
        await upsert_entities_and_mentions(chunk_entities)

    logger.info(f"[{document_id}] Entities upserted into Neo4j")

    # LLM relation extraction — only chunks with 2+ entities
    relation_candidates = [
        (cid, content, [e.normalized for e in entity_map[cid].entities])
        for cid, _, content in chunks
        if cid in entity_map and len(entity_map[cid].entities) >= 2
    ]

    if relation_candidates:
        logger.info(f"[{document_id}] Extracting relations from {len(relation_candidates)} chunks")
        relations_map = await extract_relations_batch(relation_candidates, concurrency=5)
        for chunk_id, relations in relations_map.items():
            if relations:
                await upsert_relations(relations, chunk_id)

    logger.info(f"[{document_id}] KG extraction complete")


async def _bulk_async():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id FROM documents WHERE status = 'completed' ORDER BY created_at"
        )

    doc_ids = [str(r["id"]) for r in rows]
    logger.info(f"Bulk KG extraction queued for {len(doc_ids)} documents")
    for doc_id in doc_ids:
        celery_app.send_task("app.graph_worker.build_knowledge_graph", args=[doc_id], queue="ingestion")
