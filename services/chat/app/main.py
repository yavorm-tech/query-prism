import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.config import get_settings
from app.db.connection import get_pool, close_pool
from app.db.neo4j import close_driver
from app.services.rate_limit import limiter
from app.services.cache import close_redis
from app.routers import chat
from app.routers.topics import router as topics_router

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.DEBUG),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Chat service starting...")
    await get_pool()
    logger.info("Postgres ready")
    yield
    logger.info("Chat service shutting down...")
    await close_pool()
    await close_driver()
    await close_redis()


app = FastAPI(title="Chat Service", version="1.0.0", lifespan=lifespan)
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

app.include_router(chat.router)
app.include_router(topics_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "chat"}
