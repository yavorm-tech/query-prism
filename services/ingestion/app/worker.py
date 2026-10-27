"""
Celery worker — ingestion task pipeline.
"""
import asyncio
import json
import logging
import os
from celery import Celery
from app.config import get_settings

setting = get_settings()
logger = logging.getLogger(__name__)

# Broker and results live on a dedicated Redis with noeviction; the answer
# cache Redis evicts under memory pressure and would silently drop queued tasks.
celery_app = Celery(
    "rag_worker",
    broker=setting.celery_broker_url,
    backend=setting.celery_broker_url,
    include=["app.worker", "app.graph_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=24 * 3600,
    task_routes={
        "app.worker.ingest_document":              {"queue": "ingestion"},
        "app.graph_worker.build_knowledge_graph":  {"queue": "ingestion"},
    },
)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="app.worker.ingest_document",
    max_retries=3,
    default_retry_delay=30,
)
def ingest_document(self, document_id: str, file_path: str, source_type: str):
    logger.info(f"[{document_id}] Starting ingestion: {file_path} (attempt {self.request.retries + 1})")
    try:
        run_async(_ingest_async(document_id, file_path, source_type))
    except Exception as exc:
        if self.request.retries < self.max_retries:
            # Keep the file: the retry needs it.
            logger.warning(f"[{document_id}] Ingestion attempt failed, retrying: {exc}")
            raise self.retry(exc=exc)
        logger.error(f"[{document_id}] Ingestion failed after {self.max_retries + 1} attempts: {exc}", exc_info=True)
        run_async(_mark_failed(document_id, str(exc)))
        _remove_file(file_path)
        raise
    _remove_file(file_path)


def _remove_file(file_path: str) -> None:
    if os.path.exists(file_path):
        os.remove(file_path)


async def _ingest_async(document_id: str, file_path: str, source_type: str):
    import asyncpg
    import uuid
    from app.config import get_settings
    from app.services.loaders import load_document
    from app.services.chunker import chunk_text
    from app.services.embedder import embed_texts

    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn=dsn)

    try:
        # Register pgvector codec
        await conn.set_type_codec(
            "vector",
            encoder=lambda v: str(v),
            decoder=lambda v: v,
            schema="public",
            format="text",
        )

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

        logger.info(f"[{document_id}] Inserted {len(chunks)} chunks")

        # 6. Count storage (billing owns the counter), then mark complete.
        doc_row = await conn.fetchrow(
            "SELECT company_id, team_id, visibility, file_size FROM documents WHERE id = $1", document_id
        )
        if doc_row and doc_row["file_size"]:
            from app.services.billing_client import increment_storage
            await increment_storage(str(doc_row["company_id"]), doc_row["file_size"])

        await conn.execute(
            "UPDATE documents SET status='completed', updated_at=now() WHERE id=$1",
            document_id
        )
        logger.info(f"[{document_id}] Ingestion complete")

        # 7. Drop cached answers that were computed without this document
        if doc_row:
            _invalidate_answer_cache(doc_row)

        # 8. Chain KG extraction
        from app.graph_worker import build_knowledge_graph
        build_knowledge_graph.apply_async(args=[document_id], queue="ingestion")
        logger.info(f"[{document_id}] KG extraction queued")

    finally:
        await conn.close()


def _invalidate_answer_cache(doc_row) -> None:
    """
    Sync counterpart of services.cache.invalidate_*_cache: the async client there is
    bound to one event loop, and each Celery task runs in a fresh loop.
    """
    import redis
    from app.services.cache import _team_index_key, _company_index_key

    index_key = (
        _company_index_key(str(doc_row["company_id"])) if doc_row["visibility"] == "company"
        else _team_index_key(str(doc_row["team_id"]))
    )
    try:
        r = redis.Redis.from_url(setting.redis_url, decode_responses=True)
        keys = r.smembers(index_key)
        if keys:
            r.delete(*keys, index_key)
        logger.info(f"Cache invalidated {len(keys)} entries ({index_key})")
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")


async def _mark_failed(document_id: str, error: str):
    import asyncpg
    from app.config import get_settings
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "UPDATE documents SET status='failed', error_message=$1, updated_at=now() WHERE id=$2",
            error, document_id
        )
    finally:
        await conn.close()
