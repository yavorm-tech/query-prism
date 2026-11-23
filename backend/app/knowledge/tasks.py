"""
Celery task — document ingestion pipeline.

load → chunk → embed → write chunks → mark complete + announce DocumentIngested
(one transaction) → count storage. Graph extraction is queued by the
DocumentIngested handler (knowledge.handlers).
"""
import json
import logging
import time
import uuid

from app.shared import events
from app.shared.celery import celery_app
from app.shared.db import get_pool
from app.shared.loop_local import run_in_fresh_loop
from app.shared.storage import get_storage
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
def ingest_document(self, document_id: str, storage_key: str, source_type: str):
    """storage_key: an app.shared.storage key (older queued jobs pass an absolute path, also accepted)."""
    clear_context()
    bind(document_id=document_id, task="ingest_document", attempt=self.request.retries + 1)
    logger.info(f"[{document_id}] Starting ingestion: {storage_key} (attempt {self.request.retries + 1})")
    started = time.perf_counter()
    try:
        run_in_fresh_loop(lambda: _ingest_async(document_id, storage_key, source_type))
    except Exception as exc:
        if self.request.retries < self.max_retries:
            # Keep the file: the retry needs it.
            logger.warning(f"[{document_id}] Ingestion attempt failed, retrying: {exc}")
            raise self.retry(exc=exc)
        logger.error(f"[{document_id}] Ingestion failed after {self.max_retries + 1} attempts: {exc}", exc_info=True)
        INGEST_DURATION.labels(source_type, "failed").observe(time.perf_counter() - started)
        error = str(exc)
        run_in_fresh_loop(lambda: _mark_failed(document_id, error))
        _remove_upload(document_id, storage_key)
        raise
    INGEST_DURATION.labels(source_type, "completed").observe(time.perf_counter() - started)
    _remove_upload(document_id, storage_key)


def _remove_upload(document_id: str, storage_key: str) -> None:
    try:
        get_storage().delete_sync(storage_key)
    except Exception as e:
        logger.warning(f"[{document_id}] Could not delete upload {storage_key}: {e}")


async def _ingest_async(document_id: str, storage_key: str, source_type: str):
    from app.knowledge.loaders import load_document
    from app.knowledge.chunker import chunk_text
    from app.shared.ai.embedder import embed_texts

    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Mark as processing. A document that is already completed (a duplicate
        #    delivery of the queue event, or a deleted one) is left alone.
        started = await conn.fetchval(
            "UPDATE documents SET status='processing', updated_at=now() WHERE id=$1 AND status <> 'completed' RETURNING id",
            document_id
        )
    if not started:
        logger.info(f"[{document_id}] Already completed or deleted; skipping")
        return

    # 2. Extract text
    logger.info(f"[{document_id}] Loading document...")
    with get_storage().local_copy(storage_key) as file_path:
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

    # 6. Mark complete and announce it in one transaction. Only the first
    #    transition to 'completed' counts: a duplicate or late run of this task
    #    must not count the file's storage twice.
    async with events.unit_of_work() as uow:
        doc_row = await uow.conn.fetchrow(
            """
            UPDATE documents SET status='completed', error_message=NULL, updated_at=now()
            WHERE id=$1 AND status <> 'completed'
            RETURNING company_id, team_id, visibility, file_size
            """,
            document_id,
        )
        if doc_row:
            # Retrieval drops answers cached without this document; knowledge queues graph extraction.
            await uow.publish(DocumentIngested(
                document_id=document_id, company_id=str(doc_row["company_id"]),
                team_id=str(doc_row["team_id"]), visibility=doc_row["visibility"],
            ))
    if doc_row and doc_row["file_size"]:
        await increment_storage(str(doc_row["company_id"]), doc_row["file_size"])
    logger.info(f"[{document_id}] Ingestion complete")


async def _mark_failed(document_id: str, error: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET status='failed', error_message=$1, updated_at=now() WHERE id=$2",
            error, document_id
        )
