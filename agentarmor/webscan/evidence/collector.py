"""Collect screenshots, DOM snapshots, and probe evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentarmor.webscan.models import StableResponse, WebProbeDef


class EvidenceCollector:
    def __init__(self, scan_id: str, base_dir: Path | None = None) -> None:
        root = base_dir or Path.home() / ".agentarmor" / "scans" / scan_id / "evidence"
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    async def capture_probe(
        self,
        page: Any,
        probe: WebProbeDef,
        response: StableResponse,
        network_log: list[dict[str, Any]],
    ) -> dict[str, Any]:
        probe_dir = self.root / probe.id.replace(".", "_")
        probe_dir.mkdir(parents=True, exist_ok=True)

        screenshot = probe_dir / "screenshot.png"
        try:
            await page.screenshot(path=str(screenshot), full_page=False)
        except Exception:
            screenshot = None

        dom_path = probe_dir / "dom.html"
        try:
            html = await page.content()
            dom_path.write_text(html[:500_000], encoding="utf-8")
        except Exception:
            dom_path = None

        meta = {
            "probe_id": probe.id,
            "response_text": response.text[:5000],
            "complete": response.complete,
            "partial": response.partial,
            "stream_detected": response.stream_detected,
            "wait_ms": response.wait_ms,
            "screenshot": str(screenshot) if screenshot else None,
            "dom_snapshot": str(dom_path) if dom_path else None,
            "network_sample": network_log[-20:],
        }
        (probe_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return meta
