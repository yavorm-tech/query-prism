"""
Celery application: broker config and routing only, no task imports.

The API uses it to enqueue by task name; app.worker imports the task modules.
Task names are part of the queue contract (messages already in the broker
reference them), so they keep their original "app.worker.*" / "app.graph_worker.*"
names even though the code now lives in app.knowledge.
"""
from celery import Celery
from app.shared.config import get_settings

_settings = get_settings()

# Broker and results live on a dedicated Redis with noeviction; the answer
# cache Redis evicts under memory pressure and would silently drop queued tasks.
celery_app = Celery(
    "rag_worker",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_broker_url,
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
        "app.worker.ingest_document":                   {"queue": "ingestion"},
        "app.graph_worker.build_knowledge_graph":       {"queue": "ingestion"},
        "app.graph_worker.build_knowledge_graph_bulk":  {"queue": "ingestion"},
    },
)
