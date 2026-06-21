import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.db.connection import get_pool, close_pool
from app.routers.internal import router as internal_router
from app.routers.usage import router as usage_router

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.DEBUG),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Billing service starting...")
    await get_pool()
    logger.info("Postgres ready")
    yield
    logger.info("Billing service shutting down...")
    await close_pool()


app = FastAPI(title="Billing Service", version="1.0.0", lifespan=lifespan)

# Internal service — only gateway and peer services talk to it directly.
# CORS permissive since it's on the internal Docker network.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(internal_router)
app.include_router(usage_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "billing"}
