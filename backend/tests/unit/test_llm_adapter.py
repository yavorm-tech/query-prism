import httpx
import anthropic
import pytest

from app.shared.ai import llm
from app.shared.ai.llm import AllRoutesFailed, Route, parse_routes


def _provider_down() -> Exception:
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.example.test"))


@pytest.fixture
def two_routes(monkeypatch):
    monkeypatch.setattr(llm, "routes_for", lambda tier: [Route("anthropic", "primary"), Route("openai", "backup")])


def test_parse_routes():
    assert parse_routes("anthropic:claude-x, openai:gpt-y") == [Route("anthropic", "claude-x"), Route("openai", "gpt-y")]
    for bad in ("", "nope:model", "anthropic:", "gpt-4o"):
        with pytest.raises(ValueError):
            parse_routes(bad)


def test_default_tiers_are_valid():
    for tier in llm.AnswerTier:
        assert llm.routes_for(tier)


async def test_complete_fails_over_to_next_route(monkeypatch, two_routes):
    calls = []

    async def anthropic_down(model, system, user):
        calls.append(model)
        raise _provider_down()

    async def openai_ok(model, system, user):
        calls.append(model)
        return "from backup"

    monkeypatch.setattr(llm, "COMPLETE", {"anthropic": anthropic_down, "openai": openai_ok})
    assert await llm.complete("premium", "sys", "q") == "from backup"
    assert calls == ["primary", "backup"]


async def test_complete_raises_when_every_route_fails(monkeypatch, two_routes):
    async def down(model, system, user):
        raise _provider_down()

    monkeypatch.setattr(llm, "COMPLETE", {"anthropic": down, "openai": down})
    with pytest.raises(AllRoutesFailed):
        await llm.complete("premium", "sys", "q")


async def test_non_provider_errors_are_not_swallowed(monkeypatch, two_routes):
    async def bug(model, system, user):
        raise KeyError("our bug")

    monkeypatch.setattr(llm, "COMPLETE", {"anthropic": bug, "openai": bug})
    with pytest.raises(KeyError):
        await llm.complete("premium", "sys", "q")


async def test_stream_fails_over_before_the_first_token(monkeypatch, two_routes):
    async def anthropic_down(model, system, user):
        raise _provider_down()
        yield  # pragma: no cover

    async def openai_ok(model, system, user):
        for t in ("a", "b"):
            yield t

    monkeypatch.setattr(llm, "STREAM", {"anthropic": anthropic_down, "openai": openai_ok})
    assert [t async for t in llm.stream("premium", "sys", "q")] == ["a", "b"]


async def test_stream_does_not_switch_models_mid_answer(monkeypatch, two_routes):
    async def anthropic_breaks(model, system, user):
        yield "partial"
        raise _provider_down()

    async def openai_ok(model, system, user):
        yield "should not be used"

    monkeypatch.setattr(llm, "STREAM", {"anthropic": anthropic_breaks, "openai": openai_ok})
    got = []
    with pytest.raises(anthropic.APIConnectionError):
        async for t in llm.stream("premium", "sys", "q"):
            got.append(t)
    assert got == ["partial"]
