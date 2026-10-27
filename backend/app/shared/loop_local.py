"""
Per-event-loop singletons.

asyncpg pools, redis.asyncio clients, the Neo4j async driver and AsyncOpenAI
are bound to the event loop that created them. The API runs one loop for its
lifetime, but every Celery task runs in a fresh loop, so a plain module-level
singleton breaks on the worker's second task. These helpers keep one instance
per loop, and close_loop_resources() closes the current loop's instances
before the loop itself is closed.
"""
import asyncio
import logging
import weakref
from typing import Any, Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)

Closer = Callable[[Any], Awaitable[None]]
_registry: list["_PerLoop"] = []


class _PerLoop:
    def __init__(self, closer: Closer | None):
        self._closer = closer
        self._items: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        _registry.append(self)

    def pop(self):
        """Detach this loop's instance (the caller closes it)."""
        return self._items.pop(asyncio.get_running_loop(), None)

    async def close(self) -> None:
        item = self.pop()
        if item is not None and self._closer is not None:
            try:
                await self._closer(item)
            except Exception as e:
                logger.warning(f"Closing loop resource failed: {e}")


class LoopLocal(_PerLoop, Generic[T]):
    """Async factory (pools, drivers)."""

    def __init__(self, factory: Callable[[], Awaitable[T]], closer: Closer | None = None):
        super().__init__(closer)
        self._factory = factory
        self._locks: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

    async def get(self) -> T:
        loop = asyncio.get_running_loop()
        item = self._items.get(loop)
        if item is not None:
            return item
        lock = self._locks.setdefault(loop, asyncio.Lock())
        async with lock:
            item = self._items.get(loop)
            if item is None:
                item = await self._factory()
                self._items[loop] = item
        return item


def per_loop(factory: Callable[[], T], closer: Closer | None = None) -> Callable[[], T]:
    """Sync factory variant for cheap clients (e.g. AsyncOpenAI)."""
    holder = _PerLoop(closer)

    def get() -> T:
        loop = asyncio.get_running_loop()
        item = holder._items.get(loop)
        if item is None:
            item = holder._items[loop] = factory()
        return item

    return get


async def close_loop_resources() -> None:
    for holder in _registry:
        await holder.close()


def run_in_fresh_loop(coro_factory: Callable[[], Awaitable[T]]) -> T:
    """Run a coroutine in a new loop (Celery tasks), closing loop-bound resources afterwards."""
    async def runner() -> T:
        try:
            return await coro_factory()
        finally:
            await close_loop_resources()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(runner())
    finally:
        loop.close()
