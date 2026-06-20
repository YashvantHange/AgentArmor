"""JSON scan report writer."""

from __future__ import annotations

import json
from pathlib import Path

from agentarmor.core.models import Finding, Scan


def write_json_report(scan: Scan, findings: list[Finding], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scan": scan.model_dump(mode="json"),
        "findings": [f.model_dump(mode="json") for f in findings],
        "summary": {
            "probe_count": scan.probe_count,
            "finding_count": scan.finding_count,
        },
    }
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return output_path
