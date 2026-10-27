"""
Structured logging, request correlation and Prometheus metrics.

Logs: every stdlib `logging` call (including the existing f-string calls and
library loggers) is rendered as one JSON object per line, enriched with the
contextvars bound for the current request or task (request_id, user_id,
company_id, document_id). Query text and chunk content must never be logged
at INFO or above — they are customer data.

Metrics: the API serves /metrics (not routed by the gateway). The Celery
worker records into PROMETHEUS_MULTIPROC_DIR and serves them from its parent
process (see app/worker.py).
"""
import logging
import time
import uuid

import structlog
from structlog.tracebacks import ExceptionDictTransformer
from prometheus_client import Counter, Gauge, Histogram

# ── Logging ──────────────────────────────────────────────────────────────────

_SHARED_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
]


def configure_logging(level: str = "info") -> None:
    structlog.configure(
        processors=_SHARED_PROCESSORS + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[*_SHARED_PROCESSORS, structlog.stdlib.ExtraAdder()],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            # Tracebacks as data, but never frame locals: they hold JWT claims and question text.
            structlog.processors.ExceptionRenderer(ExceptionDictTransformer(show_locals=False)),
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Route uvicorn/celery through the same handler; request logs come from RequestContextMiddleware.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "celery", "celery.task"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("httpx", "httpcore", "neo4j", "openai", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


bind = structlog.contextvars.bind_contextvars
clear_context = structlog.contextvars.clear_contextvars

# ── Metrics ──────────────────────────────────────────────────────────────────

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "route"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
ANSWER_TTFT = Histogram(
    "qp_answer_ttft_seconds", "Time from request to first answer token", ["model", "cached"],
    buckets=(0.1, 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 4, 6, 10, 20),
)
ANSWER_CACHE = Counter("qp_answer_cache_total", "Answer cache lookups", ["result"])
NO_CONTEXT_ANSWERS = Counter("qp_no_context_answers_total", "Questions answered with 'no documents found'")
RETRIEVAL_CANDIDATES = Histogram(
    "qp_retrieval_candidates", "Candidates per retrieval channel", ["source"],
    buckets=(0, 1, 2, 5, 10, 15, 20),
)
RETRIEVAL_FALLBACKS = Counter("qp_retrieval_fallback_total", "Degraded retrieval steps", ["step"])
LLM_ERRORS = Counter("qp_llm_errors_total", "Answer generation failures", ["model"])
INGEST_DURATION = Histogram(
    "qp_ingest_duration_seconds", "Document ingestion time", ["source_type", "outcome"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1800, 3600),
)
INGEST_CHUNKS = Counter("qp_ingest_chunks_total", "Chunks written by ingestion")
DOCUMENTS_BY_STATUS = Gauge("qp_documents_by_status", "Documents per ingestion status", ["status"])
EVENT_HANDLER_FAILURES = Counter("qp_event_handler_failures_total", "Failed domain event handlers", ["event"])


# ── Request middleware ───────────────────────────────────────────────────────

class RequestContextMiddleware:
    """
    Pure ASGI (not BaseHTTPMiddleware) so SSE responses stream untouched.
    Assigns X-Request-ID, binds it to the log context, records HTTP metrics and
    logs one line per request.
    """

    def __init__(self, app):
        self.app = app
        self.log = logging.getLogger("app.request")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers") or [])
        request_id = headers.get(b"x-request-id", b"").decode()[:64] or uuid.uuid4().hex
        clear_context()
        bind(request_id=request_id)
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            method = scope["method"]
            HTTP_REQUESTS.labels(method, route, str(status)).inc()
            HTTP_LATENCY.labels(method, route).observe(elapsed)
            if route not in ("/health", "/metrics"):
                self.log.info(
                    "request",
                    extra={"method": method, "route": route, "status": status,
                           "duration_ms": round(elapsed * 1000, 1)},
                )
            clear_context()
