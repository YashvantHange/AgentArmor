"""Endpoint client pooling and rate-limit enforcement.

Before the client pool existed, ``send_probe`` constructed a new
``EndpointClient`` per probe. Every one carried a fresh ``RateLimiter`` with
``_last_call = 0.0``, so the computed wait was always negative and
``rate_limit_rps`` had no effect across probes. ``test_rate_limiter_throttles``
is the regression guard for that.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from agentarmor.core.config import AppConfig, Target, TargetType
from agentarmor.core.models import ProbeRequest
from agentarmor.engines.endpoint import pool
from agentarmor.engines.endpoint.adapter import send_probe
from agentarmor.engines.endpoint.pool import (
    aclose_all,
    canonical_target_url,
    get_endpoint_client,
)

URL = "http://endpoint.test/v1/chat/completions"


@pytest.fixture(autouse=True)
def _clear_pool():
    asyncio.run(aclose_all())
    yield
    asyncio.run(aclose_all())


def _config(url: str = URL, *, rps: float = 10.0) -> AppConfig:
    cfg = AppConfig(target=Target(type=TargetType.ENDPOINT, url=url))
    cfg.engine_endpoint.profile = "openai"  # skip auto-detect
    cfg.engine_endpoint.rate_limit_rps = rps
    return cfg


def _request() -> ProbeRequest:
    return ProbeRequest(messages=[{"role": "user", "content": "hello"}])


class _Recorder:
    """Stub transport that records when each request is actually sent."""

    def __init__(self) -> None:
        self.sent: list[float] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(time.monotonic())
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
            headers={"content-type": "application/json"},
        )


def _patch_transport(monkeypatch, recorder: _Recorder) -> None:
    real_init = httpx.AsyncClient.__init__

    def init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(recorder.handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", init)


def test_rate_limiter_throttles_across_probes(monkeypatch):
    """Three probes at 10 rps must be spaced by at least ~0.1 s.

    Pre-fix each probe built its own limiter starting from ``_last_call = 0.0``,
    so the gaps were effectively zero.
    """
    recorder = _Recorder()
    _patch_transport(monkeypatch, recorder)
    cfg = _config(rps=10.0)

    async def run() -> None:
        for i in range(3):
            result = await send_probe(cfg, f"p{i}", "probe", ["LLM01"], _request())
            assert result.response.status_code == 200

    asyncio.run(run())

    assert len(recorder.sent) == 3
    gaps = [b - a for a, b in zip(recorder.sent, recorder.sent[1:])]
    assert min(gaps) >= 0.09, f"rate limiter not enforced across probes: {gaps}"


def test_pool_reuses_one_client_per_target(monkeypatch):
    recorder = _Recorder()
    _patch_transport(monkeypatch, recorder)
    cfg = _config()

    async def run():
        first = get_endpoint_client(cfg)
        second = get_endpoint_client(cfg)
        assert first is second

    asyncio.run(run())


def test_pool_separates_distinct_targets():
    async def run():
        a = get_endpoint_client(_config("http://a.test/v1/chat"))
        b = get_endpoint_client(_config("http://b.test/v1/chat"))
        assert a is not b

    asyncio.run(run())


@pytest.mark.parametrize(
    "variant",
    [
        "http://endpoint.test/v1/chat/completions",
        "http://ENDPOINT.test/v1/chat/completions",
        "HTTP://endpoint.test/v1/chat/completions",
        "http://endpoint.test:80/v1/chat/completions",
        "http://endpoint.test/v1/chat/completions/",
    ],
)
def test_equivalent_urls_share_one_client(variant):
    """Spelling variants must not each get their own limiter."""

    async def run():
        base = get_endpoint_client(_config(URL))
        other = get_endpoint_client(_config(variant))
        assert base is other, f"{variant} created a second client"

    asyncio.run(run())


def test_canonical_target_url_normalises():
    assert canonical_target_url("HTTP://Host.TEST:80/v1/chat/") == "http://host.test/v1/chat"
    assert canonical_target_url("https://host.test:443/") == "https://host.test"
    assert canonical_target_url("https://host.test:8443/x") == "https://host.test:8443/x"
    assert canonical_target_url(None) == ""


def test_pool_separates_event_loops(monkeypatch):
    """A client bound to a finished loop must never be handed out again."""
    recorder = _Recorder()
    _patch_transport(monkeypatch, recorder)
    cfg = _config()
    seen: list[object] = []

    async def run():
        # Keep a strong reference: comparing id() alone can collide after GC.
        seen.append(get_endpoint_client(cfg))

    asyncio.run(run())
    asyncio.run(run())
    assert seen[0] is not seen[1]


def test_autodetect_runs_once_across_probes(monkeypatch):
    """Auto-detect is per target, not per probe."""
    recorder = _Recorder()
    _patch_transport(monkeypatch, recorder)
    calls: list[str] = []

    async def fake_autodetect(app_config):
        calls.append(app_config.target.url or "")
        app_config.engine_endpoint.detected_profile = "openai"
        return {"ok": True, "profile": "openai", "auto_detected": True}

    monkeypatch.setattr(
        "agentarmor.engines.endpoint.client.autodetect_profile", fake_autodetect
    )

    cfg = _config(rps=0.0)  # disable throttling so the test stays fast
    cfg.engine_endpoint.profile = "auto"

    async def run():
        for i in range(3):
            await send_probe(cfg, f"p{i}", "probe", ["LLM01"], _request())

    asyncio.run(run())
    assert len(calls) == 1, f"auto-detect ran {len(calls)} times"


def test_failed_autodetect_keeps_failing(monkeypatch):
    """A cached failure must not let later probes through unresolved.

    The flag this replaced was set before the ``ok`` check, so once pooled the
    first probe reported the error and every later probe skipped detection and
    sent a real request with an unresolved profile.
    """
    recorder = _Recorder()
    _patch_transport(monkeypatch, recorder)
    calls: list[str] = []

    async def failing_autodetect(app_config):
        calls.append(app_config.target.url or "")
        return {"ok": False, "error": "Could not auto-detect API format."}

    monkeypatch.setattr(
        "agentarmor.engines.endpoint.client.autodetect_profile", failing_autodetect
    )

    cfg = _config(rps=0.0)
    cfg.engine_endpoint.profile = "auto"

    async def run():
        return [
            await send_probe(cfg, f"p{i}", "probe", ["LLM01"], _request())
            for i in range(3)
        ]

    results = asyncio.run(run())

    assert len(calls) == 1, "auto-detect should be attempted once per target"
    assert recorder.sent == [], "no probe may reach the target after detection failed"
    for result in results:
        assert result.error
        assert "auto-detect" in result.error.lower()


def test_cached_autodetect_reapplied_to_a_new_config(monkeypatch):
    """A later scan gets a fresh config copy; the cached profile must be replayed."""
    recorder = _Recorder()
    _patch_transport(monkeypatch, recorder)

    async def fake_autodetect(app_config):
        app_config.engine_endpoint.detected_profile = "openai"
        app_config.engine_endpoint.response_path = "choices.0.message.content"
        return {
            "ok": True,
            "profile": "openai",
            "response_path": "choices.0.message.content",
            "auto_detected": True,
        }

    monkeypatch.setattr(
        "agentarmor.engines.endpoint.client.autodetect_profile", fake_autodetect
    )

    async def run():
        first = _config(rps=0.0)
        first.engine_endpoint.profile = "auto"
        await send_probe(first, "p0", "probe", ["LLM01"], _request())

        second = _config(rps=0.0)
        second.engine_endpoint.profile = "auto"
        await send_probe(second, "p1", "probe", ["LLM01"], _request())
        return second

    second = asyncio.run(run())
    assert second.engine_endpoint.detected_profile == "openai"
    assert second.engine_endpoint.response_path == "choices.0.message.content"


def test_aclose_all_empties_the_pool():
    async def run():
        get_endpoint_client(_config())
        assert pool._all_clients()
        await aclose_all()
        assert not pool._all_clients()

    asyncio.run(run())


def test_the_pooled_client_does_not_carry_cookies_between_probes(monkeypatch):
    """Pooling the client also pooled its cookie jar.

    Before pooling, each probe built a fresh client and carried no session state.
    A shared jar would replay one probe's Set-Cookie on the next, including probes
    from a later scan against the same target - which for a tool that tests
    authentication boundaries can make a probe look authenticated because an
    earlier one was.
    """
    seen_cookies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_cookies.append(request.headers.get("cookie", ""))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
            headers={
                "content-type": "application/json",
                "set-cookie": "session=leaked-value; Path=/",
            },
        )

    real_init = httpx.AsyncClient.__init__

    def init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", init)
    cfg = _config(rps=0.0)

    async def run():
        for i in range(3):
            await send_probe(cfg, f"p{i}", "probe", ["LLM01"], _request())

    asyncio.run(run())

    assert len(seen_cookies) == 3
    for index, cookie in enumerate(seen_cookies):
        assert "leaked-value" not in cookie, f"probe {index} replayed a prior session"
