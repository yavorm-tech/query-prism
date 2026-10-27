"""
Celery task — document ingestion pipeline.

load → chunk → embed → write chunks → count storage → mark complete →
announce DocumentIngested → queue knowledge-graph extraction.
"""
import json
import logging
import os
import time
import uuid

from app.shared import events
from app.shared.celery import celery_app
from app.shared.db import get_pool
from app.shared.loop_local import run_in_fresh_loop
from app.shared.observability import INGEST_CHUNKS, INGEST_DURATION, bind, clear_context
from app.metering.api import increment_storage
from app.knowledge.api import DocumentIngested

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.worker.ingest_document",
    max_retries=3,
    default_retry_delay=30,
)
def ingest_document(self, document_id: str, file_path: str, source_type: str):
    clear_context()
    bind(document_id=document_id, task="ingest_document", attempt=self.request.retries + 1)
    logger.info(f"[{document_id}] Starting ingestion: {file_path} (attempt {self.request.retries + 1})")
    started = time.perf_counter()
    try:
        run_in_fresh_loop(lambda: _ingest_async(document_id, file_path, source_type))
    except Exception as exc:
        if self.request.retries < self.max_retries:
            # Keep the file: the retry needs it.
            logger.warning(f"[{document_id}] Ingestion attempt failed, retrying: {exc}")
            raise self.retry(exc=exc)
        logger.error(f"[{document_id}] Ingestion failed after {self.max_retries + 1} attempts: {exc}", exc_info=True)
        INGEST_DURATION.labels(source_type, "failed").observe(time.perf_counter() - started)
        error = str(exc)
        run_in_fresh_loop(lambda: _mark_failed(document_id, error))
        _remove_file(file_path)
        raise
    INGEST_DURATION.labels(source_type, "completed").observe(time.perf_counter() - started)
    _remove_file(file_path)


def _remove_file(file_path: str) -> None:
    if os.path.exists(file_path):
        os.remove(file_path)


async def _ingest_async(document_id: str, file_path: str, source_type: str):
    from app.knowledge.loaders import load_document
    from app.knowledge.chunker import chunk_text
    from app.shared.ai.embedder import embed_texts

    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Mark as processing
        await conn.execute(
            "UPDATE documents SET status='processing', updated_at=now() WHERE id=$1",
            document_id
        )

    # 2. Extract text
    logger.info(f"[{document_id}] Loading document...")
    text, doc_metadata = load_document(file_path)

    # Strip null bytes — PostgreSQL rejects \x00 in text columns
    text = text.replace("\x00", "")

    if not text.strip():
        raise ValueError("Document produced no extractable text")

    logger.info(f"[{document_id}] Extracted {len(text):,} characters")

    # 3. Chunk
    chunks = chunk_text(text, doc_metadata)
    logger.info(f"[{document_id}] Created {len(chunks)} chunks")

    if not chunks:
        raise ValueError("Chunking produced no chunks")

    # 4. Embed
    texts = [c.content for c in chunks]
    logger.info(f"[{document_id}] Embedding {len(texts)} chunks...")
    embeddings = await embed_texts(texts)

    # 5. Insert chunks (replacing any left by a failed earlier attempt)
    logger.info(f"[{document_id}] Inserting {len(chunks)} chunks into pgvector...")
    records = [
        (
            str(uuid.uuid4()),
            document_id,
            chunk.chunk_index,
            chunk.content.replace("\x00", ""),
            chunk.token_count,
            str(embeddings[i]),
            json.dumps(chunk.metadata),
        )
        for i, chunk in enumerate(chunks)
    ]

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM chunks WHERE document_id = $1", document_id)
            await conn.executemany(
                """
                INSERT INTO chunks
                    (id, document_id, chunk_index, content, token_count, embedding_hv, metadata)
                VALUES
                    ($1, $2, $3, $4, $5, $6::halfvec, $7)
                """,
                records,
            )
        INGEST_CHUNKS.inc(len(records))
        logger.info(f"[{document_id}] Inserted {len(chunks)} chunks")

        # 6. Count storage (metering owns the counter), then mark complete.
        doc_row = await conn.fetchrow(
            "SELECT company_id, team_id, visibility, file_size FROM documents WHERE id = $1", document_id
        )
        if doc_row and doc_row["file_size"]:
            await increment_storage(str(doc_row["company_id"]), doc_row["file_size"])

        await conn.execute(
            "UPDATE documents SET status='completed', updated_at=now() WHERE id=$1",
            document_id
        )
    logger.info(f"[{document_id}] Ingestion complete")

    # 7. Let other contexts react (retrieval drops answers cached without this document)
    if doc_row:
        await events.publish(DocumentIngested(
            document_id=document_id, company_id=str(doc_row["company_id"]),
            team_id=str(doc_row["team_id"]), visibility=doc_row["visibility"],
        ))

    # 8. Chain KG extraction
    celery_app.send_task("app.graph_worker.build_knowledge_graph", args=[document_id], queue="ingestion")
    logger.info(f"[{document_id}] KG extraction queued")


async def _mark_failed(document_id: str, error: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET status='failed', error_message=$1, updated_at=now() WHERE id=$2",
            error, document_id
        )
