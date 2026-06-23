"""A2A discovery for API endpoint targets."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx

_A2A_PATHS = (
    "/.well-known/agent-card.json",
    "/.well-known/agent.json",
    "/agent-card.json",
    "/api/agents",
    "/v1/agents",
)


async def detect_a2a_on_endpoint(url: str, *, timeout_s: float = 5.0) -> bool:
    """Probe common agent-card paths on the target API origin."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    origin = f"{parsed.scheme}://{parsed.netloc}"
    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        for path in _A2A_PATHS:
            try:
                resp = await client.get(urljoin(origin, path))
                if resp.status_code == 200 and len(resp.content) > 10:
                    text = resp.text.lower()
                    if any(k in text for k in ("agent", "handoff", "capabilities", "skills")):
                        return True
            except (httpx.HTTPError, OSError):
                continue
    return False
