import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.db.connection import get_pool, close_pool
from app.routers import auth, audit
from app.routers import oauth

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.DEBUG),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Auth service starting...")
    await get_pool()
    logger.info("Postgres ready")
    yield
    logger.info("Auth service shutting down...")
    await close_pool()


app = FastAPI(title="Auth Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(oauth.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth"}
