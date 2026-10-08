"""Swarm traffic against a target stays bounded.

The integration neither branch could prove on its own: the swarm engine and the
endpoint client pool were developed separately, and the swarm's HTTP path only goes
through the pool once both are present. Without the pool every probe built its own
``RateLimiter`` starting from ``_last_call = 0.0``, so a hundred-member run would
have sent a hundred unthrottled requests at whatever it was pointed at.

These are the two properties that make a swarm safe to point at a system you own:
concurrency never exceeds the configured cap, and requests are spaced by the
configured rate limit.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from agentarmor.core.config import AppConfig, Target, TargetType, apply_swarm_options
from agentarmor.core.models import ProbeRequest
from agentarmor.engines.endpoint.adapter import send_probe
from agentarmor.engines.endpoint.pool import aclose_all, get_endpoint_client

URL_A = "http://target-a.test/v1/chat/completions"
URL_B = "http://target-b.test/v1/chat/completions"


@pytest.fixture(autouse=True)
def _clear_pool():
    asyncio.run(aclose_all())
    yield
    asyncio.run(aclose_all())


def _config(url: str, *, rps: float) -> AppConfig:
    cfg = AppConfig(target=Target(type=TargetType.ENDPOINT, url=url))
    cfg.engine_endpoint.profile = "openai"
    cfg.engine_endpoint.rate_limit_rps = rps
    return cfg


class _Recorder:
    """Records when each request reaches the wire, and how many are in flight."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, float]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.sent.append((str(request.url), time.monotonic()))
        self.in_flight -= 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "I cannot help with that."}}]},
            headers={"content-type": "application/json"},
        )

    def gaps(self, url: str | None = None) -> list[float]:
        stamps = [t for (u, t) in self.sent if url is None or u == url]
        return [b - a for a, b in zip(stamps, stamps[1:])]


def _patch_transport(monkeypatch, recorder: _Recorder) -> None:
    real_init = httpx.AsyncClient.__init__

    def init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(recorder.handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", init)


def _request() -> ProbeRequest:
    return ProbeRequest(messages=[{"role": "user", "content": "probe"}])


def test_concurrent_probes_are_spaced_by_the_rate_limit(monkeypatch):
    """Many coroutines, one shared limiter.

    This is the shape a swarm produces: several members issuing probes at once
    against the same target. Pre-pool each got its own limiter and the spacing was
    zero.
    """
    recorder = _Recorder()
    _patch_transport(monkeypatch, recorder)
    cfg = _config(URL_A, rps=20.0)  # 0.05s apart

    async def run():
        await asyncio.gather(
            *[send_probe(cfg, f"p{i}", "probe", ["LLM01"], _request()) for i in range(6)]
        )

    asyncio.run(run())

    assert len(recorder.sent) == 6
    gaps = recorder.gaps()
    assert min(gaps) >= 0.045, f"requests were not spaced by the rate limit: {gaps}"


def test_one_limiter_is_shared_across_concurrent_callers(monkeypatch):
    recorder = _Recorder()
    _patch_transport(monkeypatch, recorder)
    cfg = _config(URL_A, rps=10.0)

    async def run():
        clients = await asyncio.gather(
            *[asyncio.sleep(0, result=get_endpoint_client(cfg)) for _ in range(5)]
        )
        return clients

    clients = asyncio.run(run())
    assert len({id(client) for client in clients}) == 1, "each caller got its own limiter"


def test_the_rate_limit_serialises_the_wire(monkeypatch):
    """The limiter holds a lock, so requests never overlap on the transport."""
    recorder = _Recorder()
    _patch_transport(monkeypatch, recorder)
    cfg = _config(URL_A, rps=50.0)

    async def run():
        await asyncio.gather(
            *[send_probe(cfg, f"p{i}", "probe", ["LLM01"], _request()) for i in range(10)]
        )

    asyncio.run(run())
    assert recorder.max_in_flight == 1, f"overlapping requests: {recorder.max_in_flight}"


def test_two_targets_do_not_throttle_each_other(monkeypatch):
    """A slow target must not stall probes aimed somewhere else."""
    recorder = _Recorder()
    _patch_transport(monkeypatch, recorder)
    cfg_a = _config(URL_A, rps=5.0)
    cfg_b = _config(URL_B, rps=5.0)

    async def run():
        started = time.monotonic()
        await asyncio.gather(
            send_probe(cfg_a, "a0", "probe", ["LLM01"], _request()),
            send_probe(cfg_b, "b0", "probe", ["LLM01"], _request()),
        )
        return time.monotonic() - started

    elapsed = asyncio.run(run())

    urls = {url for (url, _) in recorder.sent}
    assert urls == {URL_A, URL_B}
    # Separate limiters, so the second request does not wait out the first's interval.
    assert elapsed < 0.15, f"independent targets serialised each other: {elapsed:.3f}s"


def test_swarm_sizing_cannot_exceed_the_configured_caps():
    """Whatever a caller asks for, the engine runs within its ceilings."""
    cfg, agents, concurrency = apply_swarm_options(
        AppConfig(), agents=100, max_concurrent=99
    )
    assert agents == cfg.swarm.max_agents == 100
    assert concurrency == cfg.swarm.max_concurrent == 16
    # Concurrency is what the target feels, and it is always well under the roster.
    assert concurrency < agents


def test_the_swarm_http_path_goes_through_the_pool():
    """Guards the integration itself.

    The swarm calls execute_attack, which calls send_probe. If send_probe ever goes
    back to constructing a client per probe, the rate limit silently stops applying
    to swarms and nothing else in the suite would notice.
    """
    import inspect

    from agentarmor.engines.endpoint import adapter

    source = inspect.getsource(adapter.send_probe)
    assert "get_endpoint_client" in source
    assert "EndpointClient(" not in source
