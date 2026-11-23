"""Knowledge reactions to its own events (subscribed in app.bootstrap).

They run after the change committed and are redelivered by the outbox relay if
they fail, so the broker or Neo4j being briefly down no longer loses work.
All are idempotent: the worker skips completed documents, graph writes MERGE,
and deleting an already-deleted graph is a no-op.
"""
from app.shared.celery import celery_app
from app.knowledge.api import DocumentDeleted, DocumentIngested, DocumentUploaded


async def queue_ingestion(event: DocumentUploaded) -> None:
    # Enqueue by name so the API never imports the worker's heavy dependencies.
    celery_app.send_task(
        "app.worker.ingest_document",
        args=[event.document_id, event.storage_key, event.source_type],
        queue="ingestion",
        task_id=event.job_id,
    )


async def queue_graph_build(event: DocumentIngested) -> None:
    celery_app.send_task("app.graph_worker.build_knowledge_graph", args=[event.document_id], queue="ingestion")


async def delete_graph(event: DocumentDeleted) -> None:
    from app.knowledge.graph.writer import delete_document_graph
    await delete_document_graph(event.document_id)
