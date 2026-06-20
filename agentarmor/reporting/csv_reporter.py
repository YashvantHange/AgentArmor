"""CSV flat findings export."""

from __future__ import annotations

import csv
from pathlib import Path

from agentarmor.core.models import Finding, Scan


def write_csv_report(scan: Scan, findings: list[Finding], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scan_id",
        "probe_id",
        "probe_name",
        "severity",
        "decision",
        "risk_score",
        "owasp",
        "title",
        "description",
        "request_summary",
        "response_excerpt",
        "created_at",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for f in findings:
            writer.writerow(
                {
                    "scan_id": scan.id,
                    "probe_id": f.probe_id,
                    "probe_name": f.probe_name,
                    "severity": f.severity.value,
                    "decision": f.decision.value,
                    "risk_score": f.risk_score,
                    "owasp": ",".join(f.owasp),
                    "title": f.title,
                    "description": f.description,
                    "request_summary": f.request_summary,
                    "response_excerpt": f.response_excerpt,
                    "created_at": f.created_at.isoformat(),
                }
            )
    return output_path
