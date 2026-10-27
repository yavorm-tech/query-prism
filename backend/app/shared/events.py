"""
In-process domain events.

Lets a lower-layer context announce something without importing the contexts
that react to it (e.g. knowledge announces DocumentIngested; retrieval clears
its answer cache). Handlers run in-process, in subscription order, after the
publisher's own writes. A failing handler is logged and does not fail the
publisher — handlers must be safe to miss (caches, defaults that can be
re-created). Event classes live in the publishing context's api module.
"""
import logging
from collections import defaultdict
from typing import Awaitable, Callable
from app.shared.observability import EVENT_HANDLER_FAILURES

logger = logging.getLogger(__name__)

Handler = Callable[[object], Awaitable[None]]
_handlers: dict[type, list[Handler]] = defaultdict(list)


def subscribe(event_type: type, handler: Handler) -> None:
    if handler not in _handlers[event_type]:
        _handlers[event_type].append(handler)


async def publish(event: object) -> None:
    for handler in _handlers.get(type(event), []):
        try:
            await handler(event)
        except Exception:
            EVENT_HANDLER_FAILURES.labels(type(event).__name__).inc()
            logger.exception(f"Handler {handler.__qualname__} failed for {type(event).__name__}")


def clear() -> None:
    """For tests."""
    _handlers.clear()
