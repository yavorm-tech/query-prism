import asyncio
import os
import subprocess
import sys

import pytest
from jose import jwt
from starlette.requests import Request

from app.shared import rate_limit
from app.shared.loop_local import LoopLocal, close_loop_resources, run_in_fresh_loop


def _settings_error(**env) -> str:
    r = subprocess.run(
        [sys.executable, "-c", "from app.shared.config import Settings; Settings()"],
        env={**os.environ, **env}, capture_output=True, text=True,
    )
    return "ok" if r.returncode == 0 else r.stderr


@pytest.mark.parametrize("secret", ["changeme", "short", ""])
def test_weak_secret_key_refuses_to_start(secret):
    assert "at least 32 characters" in _settings_error(SECRET_KEY=secret)


def test_strong_secret_key_starts():
    assert _settings_error(SECRET_KEY="k" * 40) == "ok"


def _request(headers: dict, client_ip: str = "172.18.0.9") -> Request:
    return Request({
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_ip, 1),
    })


def test_rate_limit_keys_on_verified_user():
    token = jwt.encode({"sub": "user-42"}, os.environ["SECRET_KEY"], algorithm="HS256")
    key = rate_limit._rate_limit_key(_request({"Authorization": f"Bearer {token}", "X-Real-IP": "1.2.3.4"}))
    assert key == "user:user-42"


def test_rate_limit_ignores_forged_token_and_uses_forwarded_ip():
    forged = jwt.encode({"sub": "victim"}, "not-the-key" * 4, algorithm="HS256")
    key = rate_limit._rate_limit_key(_request({"Authorization": f"Bearer {forged}", "X-Real-IP": "1.2.3.4"}))
    assert key == "ip:1.2.3.4"


def test_rate_limit_anonymous_falls_back_to_peer():
    assert rate_limit._rate_limit_key(_request({})) == "ip:172.18.0.9"


def test_loop_local_gives_each_loop_its_own_instance_and_closes_it():
    created, closed = [], []

    async def factory():
        obj = object()
        created.append(obj)
        return obj

    async def closer(obj):
        closed.append(obj)

    holder = LoopLocal(factory, closer=closer)

    async def use():
        a = await holder.get()
        b = await holder.get()
        assert a is b
        return a

    first = run_in_fresh_loop(use)
    second = run_in_fresh_loop(use)
    assert first is not second
    assert closed == [first, second]  # run_in_fresh_loop closes before the loop ends
    asyncio.run(close_loop_resources())


def test_exception_logs_never_include_frame_locals(capsys):
    import logging
    from app.shared.observability import configure_logging

    configure_logging("info")
    secret_claims = {"sub": "user-1", "email": "person@example.test"}  # noqa: F841 (must not be logged)
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logging.getLogger("test").exception("failed")
    import json
    record = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    frames = record["exception"][0]["frames"]
    assert record["exception"][0]["exc_value"] == "boom"
    assert frames and all("locals" not in f for f in frames)
    assert "person@example.test" not in json.dumps(record)
