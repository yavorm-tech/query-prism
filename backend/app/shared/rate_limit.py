"""
Rate limiting — uses slowapi (Starlette wrapper around limits).

Requests arrive through the Nginx gateway, so the socket peer is always the
gateway. Limits are keyed on the authenticated user, falling back to the
client IP the gateway forwards in X-Real-IP. Counters live in Redis so every
worker process and replica shares them.
"""
from fastapi import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request
from app.shared.config import get_settings
from app.shared.security import decode_token

settings = get_settings()


def _rate_limit_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            claims = decode_token(auth[7:])
            if claims.get("sub"):
                return f"user:{claims['sub']}"
        except HTTPException:
            pass
    return f"ip:{request.headers.get('x-real-ip') or get_remote_address(request)}"


limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=settings.redis_url,
    in_memory_fallback_enabled=True,
)
