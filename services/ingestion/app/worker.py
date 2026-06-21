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

celery_app = Celery(
    "rag_worker",
    broker=setting.redis_url,
    backend=setting.redis_url,
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
    logger.info(f"[{document_id}] Starting ingestion: {file_path}")
    try:
        run_async(_ingest_async(document_id, file_path, source_type))
    except Exception as exc:
        logger.error(f"[{document_id}] Ingestion failed: {exc}", exc_info=True)
        run_async(_mark_failed(document_id, str(exc)))
        raise self.retry(exc=exc)
    finally:
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

        # 5. Insert chunks
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

        await conn.executemany(
            """
            INSERT INTO chunks
                (id, document_id, chunk_index, content, token_count, embedding, embedding_hv,  metadata)
            VALUES
                ($1, $2, $3, $4, $5, $6::vector, $6::halfvec, $7)
            """,
            records,
        )

        logger.info(f"[{document_id}] Inserted {len(chunks)} chunks")

        # 6. Mark complete
        await conn.execute(
            "UPDATE documents SET status='completed', updated_at=now() WHERE id=$1",
            document_id
        )
        logger.info(f"[{document_id}] Ingestion complete")

        # 7. Increment company storage counter
        doc_row = await conn.fetchrow(
            "SELECT company_id, file_size FROM documents WHERE id = $1", document_id
        )
        if doc_row and doc_row["file_size"]:
            await conn.execute(
                "UPDATE companies SET storage_used_bytes = storage_used_bytes + $2 WHERE id = $1",
                str(doc_row["company_id"]), doc_row["file_size"],
            )

        # 8. Chain KG extraction
        from app.graph_worker import build_knowledge_graph
        build_knowledge_graph.apply_async(args=[document_id], queue="ingestion")
        logger.info(f"[{document_id}] KG extraction queued")

    finally:
        await conn.close()


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
