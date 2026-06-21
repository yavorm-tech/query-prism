"""
Rate limiting — uses slowapi (Starlette wrapper around limits).
Limits are per IP address in dev; swap to per-user in production.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Key function — rate limit by IP
# Swap to a user-based key in production:
#   lambda request: request.state.user_id or get_remote_address(request)
limiter = Limiter(key_func=get_remote_address)
