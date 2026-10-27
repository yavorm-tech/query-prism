"""
Celery worker entry point:  celery -A app.worker worker -Q ingestion

Registers the ingestion tasks, wires the same event handlers as the API and
serves Prometheus metrics. Celery forks child processes, so metrics use
prometheus_client's multiprocess mode: PROMETHEUS_MULTIPROC_DIR must be set
in the environment before this module is imported (see docker-compose.yml).
"""
import os
import shutil

# Must run before anything imports prometheus_client metrics (app.shared.observability):
# multiprocess mode needs the directory to exist, and stale files from a previous
# run would double-count. Celery children fork after this, so it runs once.
_MULTIPROC_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
if _MULTIPROC_DIR:
    shutil.rmtree(_MULTIPROC_DIR, ignore_errors=True)
    os.makedirs(_MULTIPROC_DIR, exist_ok=True)

from celery.signals import setup_logging, worker_init, worker_process_shutdown  # noqa: E402

from app.shared.celery import celery_app  # noqa: E402
from app.shared.config import get_settings  # noqa: E402
from app.shared.observability import configure_logging  # noqa: E402
from app.bootstrap import wire  # noqa: E402
import app.knowledge.tasks  # noqa: F401,E402  (registers app.worker.ingest_document)
import app.knowledge.graph_tasks  # noqa: F401,E402  (registers app.graph_worker.*)

METRICS_PORT = 9101

wire()


@setup_logging.connect
def _configure_logging(**_):
    # Connecting this signal stops Celery from installing its own handlers.
    configure_logging(get_settings().log_level)


@worker_init.connect
def _start_metrics_server(**_):
    if not _MULTIPROC_DIR:
        return
    from prometheus_client import CollectorRegistry, start_http_server
    from prometheus_client.multiprocess import MultiProcessCollector
    registry = CollectorRegistry()
    MultiProcessCollector(registry)
    start_http_server(METRICS_PORT, registry=registry)


@worker_process_shutdown.connect
def _mark_process_dead(pid=None, **_):
    if _MULTIPROC_DIR:
        from prometheus_client import multiprocess
        multiprocess.mark_process_dead(pid or os.getpid())


__all__ = ["celery_app"]
