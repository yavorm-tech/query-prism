"""
Domain events through a transactional outbox (ADR-010).

A lower-layer context announces something without importing the contexts that
react to it (knowledge announces DocumentIngested; retrieval clears its answer
cache). Event classes are dataclasses in the publishing context's api module.

Publishing writes the event to shared.outbox, ideally in the same transaction
as the change it describes:

    async with events.unit_of_work() as uow:
        await uow.conn.execute("DELETE FROM topics WHERE id = $1", topic_id)
        await uow.publish(TopicDeleted(...))
    # committed: the event is delivered to its handlers now

So an event exists if and only if its change was committed. Delivery happens
right after commit in the publishing process; if that fails (a handler raises,
the process dies), the relay (run_relay, started by the API) redelivers it.
Delivery is at-least-once, so every handler must be idempotent.
"""
import asyncio
import dataclasses
import json
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable

import asyncpg

from app.shared.db import get_pool
from app.shared.observability import EVENT_HANDLER_FAILURES, OUTBOX_DEAD, OUTBOX_PENDING

logger = logging.getLogger(__name__)

Handler = Callable[[object], Awaitable[None]]
_handlers: dict[type, list[Handler]] = defaultdict(list)
_types: dict[str, type] = {}

MAX_ATTEMPTS = 10
CLAIM_TIMEOUT = "2 minutes"        # a claimed event not finished by then is redelivered
RELAY_GRACE = "10 seconds"         # leave fresh events to the publisher's own delivery
RETENTION = "7 days"               # delivered events are deleted after this
MAX_BACKOFF_SECONDS = 3600         # retries back off 2^attempts seconds, up to this


def subscribe(event_type: type, handler: Handler) -> None:
    _types[event_type.__name__] = event_type
    if handler not in _handlers[event_type]:
        _handlers[event_type].append(handler)


def clear() -> None:
    """For tests."""
    _handlers.clear()
    _types.clear()


def _payload(event: object) -> str:
    if not dataclasses.is_dataclass(event):
        raise TypeError(f"Events must be dataclasses, got {type(event).__name__}")
    return json.dumps(dataclasses.asdict(event), default=str)


async def _record(conn: asyncpg.Connection, event: object) -> int:
    return await conn.fetchval(
        "INSERT INTO shared.outbox (event_type, payload) VALUES ($1, $2::jsonb) RETURNING id",
        type(event).__name__, _payload(event),
    )


class UnitOfWork:
    """A connection in a transaction, plus the events to deliver once it commits."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn
        self._ids: list[int] = []

    async def publish(self, event: object) -> None:
        self._ids.append(await _record(self.conn, event))


@asynccontextmanager
async def unit_of_work() -> AsyncIterator[UnitOfWork]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        uow = UnitOfWork(conn)
        async with conn.transaction():
            yield uow
    for event_id in uow._ids:
        await deliver(event_id)


async def publish(event: object) -> None:
    """Record and deliver an event that is not tied to a transaction of the caller's."""
    async with unit_of_work() as uow:
        await uow.publish(event)


async def deliver(event_id: int) -> bool:
    """Run the handlers for one outbox event. Returns True when it is done (delivered or dead)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE shared.outbox SET claimed_at = now(), attempts = attempts + 1
            WHERE id = $1 AND processed_at IS NULL AND attempts < {MAX_ATTEMPTS}
              AND (claimed_at IS NULL OR claimed_at < now() - interval '{CLAIM_TIMEOUT}')
            RETURNING event_type, payload, attempts
            """,
            event_id,
        )
    if row is None:
        return True     # already delivered, given up on, or being delivered elsewhere

    event_cls = _types.get(row["event_type"])
    error = None
    if event_cls is not None:
        payload = row["payload"]
        event = event_cls(**(json.loads(payload) if isinstance(payload, str) else payload))
        for handler in _handlers.get(event_cls, []):
            try:
                await handler(event)
            except Exception as e:
                EVENT_HANDLER_FAILURES.labels(row["event_type"]).inc()
                logger.exception(f"Handler {handler.__qualname__} failed for {row['event_type']} #{event_id}")
                error = f"{handler.__qualname__}: {type(e).__name__}: {e}"

    async with pool.acquire() as conn:
        if error is None:
            await conn.execute("UPDATE shared.outbox SET processed_at = now(), last_error = NULL WHERE id = $1", event_id)
            return True
        backoff = min(2 ** row["attempts"], MAX_BACKOFF_SECONDS)
        await conn.execute(
            """
            UPDATE shared.outbox
               SET claimed_at = NULL, last_error = $2, available_at = now() + make_interval(secs => $3)
             WHERE id = $1
            """,
            event_id, error[:2000], float(backoff),
        )
    if row["attempts"] >= MAX_ATTEMPTS:
        OUTBOX_DEAD.labels(row["event_type"]).inc()
        logger.error(f"Outbox event {row['event_type']} #{event_id} gave up after {MAX_ATTEMPTS} attempts: {error}")
        return True
    return False


async def relay_once(limit: int = 100) -> int:
    """Redeliver events whose immediate delivery did not finish. Returns how many were attempted."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        ids = await conn.fetch(
            f"""
            SELECT id FROM shared.outbox
            WHERE processed_at IS NULL AND attempts < {MAX_ATTEMPTS}
              AND created_at < now() - interval '{RELAY_GRACE}'
              AND available_at <= now()
              AND (claimed_at IS NULL OR claimed_at < now() - interval '{CLAIM_TIMEOUT}')
            ORDER BY id LIMIT $1
            """,
            limit,
        )
        OUTBOX_PENDING.set(await conn.fetchval(
            f"SELECT COUNT(*) FROM shared.outbox WHERE processed_at IS NULL AND attempts < {MAX_ATTEMPTS}"
        ))
        await conn.execute(
            f"DELETE FROM shared.outbox WHERE processed_at < now() - interval '{RETENTION}'"
        )
    for r in ids:
        await deliver(r["id"])
    return len(ids)


async def run_relay(interval: float = 5.0) -> None:
    """Background loop in the API process."""
    while True:
        try:
            await relay_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Outbox relay pass failed: {e}")
        await asyncio.sleep(interval)
