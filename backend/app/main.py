"""
Query Prism API — one deployable, one module per bounded context.

    identity      /auth, /auth/oauth          companies, users, teams, invites
    audit         /audit                      audit trail
    metering      /usage                      plans, quotas, usage counters
    notification  /contact                    transactional email
    workspace     /topics                     topics
    knowledge     /ingest, /topics/*/documents documents, chunks, graph
    retrieval     /chat, /topics/*/questions  answering, question history

The Celery worker (app.worker) is deployed separately from the same code.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi.errors import RateLimitExceeded

from app.shared.config import get_settings
from app.shared.db import get_pool, close_pool
from app.shared.neo4j import close_driver
from app.shared.observability import DOCUMENTS_BY_STATUS, RequestContextMiddleware, configure_logging
from app.shared.rate_limit import limiter
from app.bootstrap import wire
from app.identity.router import router as identity_router
from app.identity.oauth import router as oauth_router
from app.audit.router import router as audit_router
from app.metering.router import router as usage_router
from app.notification.router import router as contact_router
from app.workspace.router import router as topics_router
from app.knowledge.router import router as ingest_router, topics_router as topic_documents_router
from app.knowledge.graph.schema import init_schema
from app.retrieval.router import router as chat_router
from app.retrieval.history import router as topic_questions_router
from app.retrieval.cache import close_redis

settings = get_settings()
configure_logging(settings.log_level)
wire()
logger = logging.getLogger(__name__)

DOCUMENT_STATUSES = ("pending", "processing", "completed", "failed")


async def _refresh_document_gauge() -> None:
    """Feeds the 'documents stuck in pending' alert."""
    while True:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT status, COUNT(*) AS n FROM documents GROUP BY status")
            counts = {r["status"]: r["n"] for r in rows}
            for status in DOCUMENT_STATUSES:
                DOCUMENTS_BY_STATUS.labels(status).set(counts.get(status, 0))
        except Exception as e:
            logger.warning(f"Document status gauge refresh failed: {e}")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Query Prism API starting...")
    await get_pool()
    logger.info("Postgres ready")
    try:
        await init_schema()
        logger.info("Neo4j ready")
    except Exception as e:
        # The graph is an enrichment; answer from vectors until Neo4j is back.
        logger.warning(f"Neo4j unavailable at startup: {e}")
    gauge_task = asyncio.create_task(_refresh_document_gauge())
    yield
    logger.info("Query Prism API shutting down...")
    gauge_task.cancel()
    await close_pool()
    await close_driver()
    await close_redis()


app = FastAPI(title="Query Prism API", version="2.0.0", lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

app.include_router(identity_router)
app.include_router(oauth_router)
app.include_router(audit_router)
app.include_router(usage_router)
app.include_router(contact_router)
app.include_router(topics_router)
app.include_router(topic_documents_router)
app.include_router(topic_questions_router)
app.include_router(ingest_router)
app.include_router(chat_router)


@app.get("/health")
async def health():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "postgres": "down"})
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    # Not routed by the gateway; scrape from inside the Docker network.
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
