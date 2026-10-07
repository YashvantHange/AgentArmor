"""Process-level cache of :class:`EndpointClient` instances.

``send_probe`` used to build a new ``EndpointClient`` for every probe. Each one
got a fresh :class:`~agentarmor.engines.endpoint.client.RateLimiter` whose
``_last_call`` started at ``0.0``, so the computed wait was always negative and
``engine.endpoint.rate_limit_rps`` never throttled anything across probes. It
also meant a new TCP/TLS connection and a repeated auto-detect per probe.

Clients are cached per *(event loop, canonical target identity)*:

- **Event loop** comes first because ``asyncio.Lock`` and ``httpx.AsyncClient``
  bind to the loop that created them, and reusing one across loops raises. The
  CLI calls ``asyncio.run`` per command and pytest-asyncio builds a loop per
  test. The loop is held in a :class:`weakref.WeakKeyDictionary` rather than
  keyed by ``id()``: CPython reuses addresses, so an ``id()`` key can collide
  with a *destroyed* loop and hand back a client bound to it.
- **Target identity** is normalised (lower-cased scheme and host, default port
  dropped, trailing slash on an empty path ignored) so that ``http://host``,
  ``http://host/`` and ``HTTP://HOST`` share one limiter instead of getting
  three and silently tripling the effective rate.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from weakref import WeakKeyDictionary
from urllib.parse import urlsplit, urlunsplit

from agentarmor.core.config import AppConfig
from agentarmor.engines.endpoint.client import EndpointClient

# One fingerprint -> client map per live event loop. Entries vanish with the loop.
_POOLS: "WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, EndpointClient]]" = (
    WeakKeyDictionary()
)
# Used only when there is no running loop (direct sync calls, mostly in tests).
_NO_LOOP_POOL: dict[str, EndpointClient] = {}

_DEFAULT_PORTS = {"http": 80, "https": 443}


def canonical_target_url(url: str | None) -> str:
    """Normalise a target URL so equivalent spellings produce one cache key."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if not host:
        # Not an absolute URL; fall back to the raw string so distinct values
        # still get distinct clients.
        return url.strip().lower()

    netloc = host
    if parts.port is not None and parts.port != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{parts.port}"
    if parts.username:
        credentials = parts.username
        if parts.password:
            credentials = f"{credentials}:{parts.password}"
        netloc = f"{credentials}@{netloc}"

    path = parts.path
    if path == "/":
        path = ""
    path = path.rstrip("/") if path else path

    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _fingerprint(config: AppConfig) -> str:
    ep = config.engine_endpoint
    headers = json.dumps(config.target.headers or {}, sort_keys=True)
    # ``detected_profile`` is deliberately absent: auto-detect *sets* it on the
    # config, so including it would change the key the moment detection succeeds
    # and hand the next probe a fresh client with no cached result.
    parts = [
        canonical_target_url(config.target.url),
        ep.profile,
        f"{ep.rate_limit_rps}",
        f"{ep.timeout_s}",
        ep.http_method,
        hashlib.sha256(headers.encode("utf-8")).hexdigest()[:12],
    ]
    return "|".join(parts)


def _pool_for_loop() -> dict[str, EndpointClient]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return _NO_LOOP_POOL
    pool = _POOLS.get(loop)
    if pool is None:
        pool = {}
        _POOLS[loop] = pool
    return pool


def get_endpoint_client(config: AppConfig) -> EndpointClient:
    """Return the shared client for this target on the running event loop."""
    pool = _pool_for_loop()
    key = _fingerprint(config)
    client = pool.get(key)
    if client is None:
        client = EndpointClient(config.engine_endpoint)
        pool[key] = client
    return client


def _all_clients() -> list[EndpointClient]:
    """Every pooled client across all live loops. For shutdown and tests."""
    clients: list[EndpointClient] = list(_NO_LOOP_POOL.values())
    for pool in list(_POOLS.values()):
        clients.extend(pool.values())
    return clients


async def aclose_all() -> None:
    """Close every pooled client. Call on API shutdown and after CLI runs."""
    clients = _all_clients()
    _NO_LOOP_POOL.clear()
    for pool in list(_POOLS.values()):
        pool.clear()
    for client in clients:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001 - shutdown must not raise
            pass
