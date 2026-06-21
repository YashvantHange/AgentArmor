"""Research dataset export with optional anonymization."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentarmor.export.anonymizer import anonymize_text
from agentarmor.db.session import ScanRepository


def export_dataset_jsonl(
    repo: ScanRepository,
    *,
    scan_ids: list[str] | None = None,
    anonymize: bool = True,
    output_path: Path | None = None,
) -> Path:
    """Export findings as JSONL suitable for research / fine-tuning datasets."""
    findings = repo.list_findings()
    if scan_ids:
        scan_set = set(scan_ids)
        findings = [f for f in findings if f.scan_id in scan_set]

    rows: list[dict[str, Any]] = []
    for f in findings:
        prompt = f.request_summary or ""
        response = f.response_excerpt or ""
        if anonymize:
            prompt = anonymize_text(prompt)
            response = anonymize_text(response)
        rows.append(
            {
                "scan_id": f.scan_id if not anonymize else _hash_id(f.scan_id),
                "probe_id": f.probe_id,
                "probe_name": f.probe_name,
                "prompt": prompt,
                "response": response,
                "label": f.decision.value,
                "severity": f.severity.value,
                "risk_score": f.risk_score,
                "owasp": f.owasp,
                "evidence": [anonymize_text(e) for e in f.evidence] if anonymize else f.evidence,
                "metadata": {k: v for k, v in f.metadata.items() if k != "raw_api_key"},
            }
        )

    out = output_path or Path(f"agentarmor-dataset-{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
    return out


def _hash_id(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode()).hexdigest()[:16]
