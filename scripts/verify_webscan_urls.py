"""One-off verification of web scan discovery against live URLs."""
from __future__ import annotations

import asyncio
import json
import sys

from agentarmor.core.config import load_config
from agentarmor.db.session import ScanRepository
from agentarmor.webscan.browser.pool import BrowserPool, playwright_available
from agentarmor.webscan.browser.session import BrowserSession
from agentarmor.webscan.discovery.engine import discover_full, discover_widget
from agentarmor.webscan.orchestrator import WebScanOrchestrator
from agentarmor.webscan.probes.catalog import BASE_WEB_PROBES
from agentarmor.webscan.probes.executor import execute_probe


async def verify_url(url: str, *, run_probe: bool = False) -> dict:
    cfg = load_config()
    pool = BrowserPool(max_concurrent=1)
    result: dict = {"url": url, "ok": False}

    try:
        async with pool.context() as ctx:
            page = await ctx.new_page()
            session = BrowserSession(page, allowlist=cfg.webscan.allowlist, blocklist=cfg.webscan.blocklist)
            timeout_ms = int(cfg.webscan.timeout_s * 1000)
            try:
                await session.goto(url, timeout_ms=timeout_ms)
                result["navigation"] = "ok"
            except Exception as exc:
                result["navigation"] = f"failed: {exc}"
                return result

            widget_only = await discover_widget(page, url)
            full = await discover_full(page, url, session.network_log, cfg, use_llm_discovery=False)

            result["widget"] = (
                widget_only.widget.model_dump() if widget_only.widget else None
            )
            result["framework"] = widget_only.framework
            result["candidates"] = [c.model_dump() for c in widget_only.candidates[:5]]
            result["ok"] = full.widget is not None
            result["low_confidence"] = bool(
                full.widget and full.widget.score_breakdown.get("low_confidence")
            )

            if run_probe and full.widget:
                probe = BASE_WEB_PROBES[0]
                try:
                    stable = await execute_probe(
                        page,
                        full.widget,
                        probe,
                        stable_ms=cfg.webscan.stable_ms,
                        max_wait_ms=min(cfg.webscan.max_wait_ms, 30000),
                    )
                    result["probe"] = {
                        "id": probe.id,
                        "response_excerpt": stable.text[:300],
                        "complete": stable.complete,
                        "partial": stable.partial,
                        "wait_ms": stable.wait_ms,
                    }
                except Exception as exc:
                    result["probe"] = {"error": str(exc)}
    finally:
        await pool.close()

    return result


async def main() -> None:
    if not playwright_available():
        print("Playwright not installed", file=sys.stderr)
        sys.exit(1)

    urls = [
        ("https://gandalf.lakera.ai/baseline", True),
        ("https://www.promptairlines.com/", True),
        ("https://chatgpt.com/", False),
    ]
    for url, run_probe in urls:
        print(f"\n{'='*60}\nVerifying: {url}\n{'='*60}")
        out = await verify_url(url, run_probe=run_probe)
        print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
