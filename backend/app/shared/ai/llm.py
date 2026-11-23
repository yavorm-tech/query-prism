"""
LLM adapter (ADR-008): the only place that knows provider SDKs and model IDs.

Callers ask for an AnswerTier ("basic", "standard", "premium"). Each tier maps
to an ordered list of provider:model routes from settings (LLM_TIER_<TIER>).
A route that fails with a provider error is skipped and the next one is tried,
so replacing a deprecated model or adding a fallback provider is a config change.

Streaming can only fail over before the first token is sent: once text has
reached the client, a later failure is raised to the caller.
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import AsyncGenerator, Awaitable, Callable

import anthropic
import openai

from app.shared.config import get_settings
from app.shared.loop_local import per_loop
from app.shared.observability import LLM_FAILOVERS

logger = logging.getLogger(__name__)

MAX_TOKENS = 1024


class AnswerTier(str, Enum):
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"


@dataclass(frozen=True)
class Route:
    provider: str   # "anthropic" | "openai"
    model: str

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


# Errors that mean "this route is unavailable right now": try the next one.
# (Bad requests and auth failures are included: a retired model ID returns 404,
# a revoked key 401 — both are exactly what failover is for.)
PROVIDER_ERRORS: tuple[type[BaseException], ...] = (anthropic.APIError, openai.APIError)


class AllRoutesFailed(RuntimeError):
    pass


def parse_routes(spec: str) -> list[Route]:
    routes = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        provider, _, model = part.partition(":")
        if provider not in ("anthropic", "openai") or not model:
            raise ValueError(f"Invalid LLM route {part!r}; expected anthropic:<model> or openai:<model>")
        routes.append(Route(provider, model))
    if not routes:
        raise ValueError("An answer tier needs at least one route")
    return routes


def routes_for(tier: AnswerTier | str) -> list[Route]:
    s = get_settings()
    spec = {
        AnswerTier.BASIC: s.llm_tier_basic,
        AnswerTier.STANDARD: s.llm_tier_standard,
        AnswerTier.PREMIUM: s.llm_tier_premium,
    }[AnswerTier(tier)]
    return parse_routes(spec)


def _client_kwargs() -> dict:
    s = get_settings()
    # Few SDK retries: a failing route should hand over to the next one quickly.
    return {"timeout": s.llm_timeout_seconds, "max_retries": s.llm_max_retries}


_anthropic = per_loop(
    lambda: anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key, **_client_kwargs()),
    closer=lambda c: c.close(),
)
_openai = per_loop(
    lambda: openai.AsyncOpenAI(api_key=get_settings().openai_api_key, **_client_kwargs()),
    closer=lambda c: c.close(),
)


# ── Provider calls ───────────────────────────────────────────────────────────

async def _anthropic_complete(model: str, system: str, user: str) -> str:
    message = await _anthropic().messages.create(
        model=model, max_tokens=MAX_TOKENS, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


async def _anthropic_stream(model: str, system: str, user: str) -> AsyncGenerator[str, None]:
    async with _anthropic().messages.stream(
        model=model, max_tokens=MAX_TOKENS, system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


def _openai_messages(system: str, user: str) -> list[dict]:
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


async def _openai_complete(model: str, system: str, user: str) -> str:
    response = await _openai().chat.completions.create(
        model=model, max_tokens=MAX_TOKENS, messages=_openai_messages(system, user),
    )
    return response.choices[0].message.content or ""


async def _openai_stream(model: str, system: str, user: str) -> AsyncGenerator[str, None]:
    stream = await _openai().chat.completions.create(
        model=model, max_tokens=MAX_TOKENS, stream=True, messages=_openai_messages(system, user),
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


COMPLETE: dict[str, Callable[[str, str, str], Awaitable[str]]] = {
    "anthropic": _anthropic_complete, "openai": _openai_complete,
}
STREAM: dict[str, Callable[[str, str, str], AsyncGenerator[str, None]]] = {
    "anthropic": _anthropic_stream, "openai": _openai_stream,
}


def _failed(tier: AnswerTier, route: Route, exc: BaseException) -> None:
    LLM_FAILOVERS.labels(AnswerTier(tier).value, str(route)).inc()
    logger.warning(f"LLM route {route} failed for tier {AnswerTier(tier).value}: {type(exc).__name__}: {exc}")


# ── Public API ───────────────────────────────────────────────────────────────

async def complete(tier: AnswerTier | str, system: str, user: str) -> str:
    last: BaseException | None = None
    for route in routes_for(tier):
        try:
            return await COMPLETE[route.provider](route.model, system, user)
        except PROVIDER_ERRORS as exc:
            _failed(tier, route, exc)
            last = exc
    raise AllRoutesFailed(f"Every route for tier {AnswerTier(tier).value} failed") from last


async def stream(tier: AnswerTier | str, system: str, user: str) -> AsyncGenerator[str, None]:
    last: BaseException | None = None
    for route in routes_for(tier):
        started = False
        try:
            async for text in STREAM[route.provider](route.model, system, user):
                started = True
                yield text
            return
        except PROVIDER_ERRORS as exc:
            if started:
                raise   # text already reached the client; can't switch models mid-answer
            _failed(tier, route, exc)
            last = exc
    raise AllRoutesFailed(f"Every route for tier {AnswerTier(tier).value} failed") from last
