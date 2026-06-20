"""SARIF 2.1 report writer for GitHub Security integration."""

from __future__ import annotations

import json
from pathlib import Path

from agentarmor.core.models import Finding, Scan
from agentarmor.reporting.owasp import rule_id, rule_name


def write_sarif_report(scan: Scan, findings: list[Finding], output_path: Path) -> Path:
    rules: dict[str, dict] = {}
    results = []

    for finding in findings:
        primary_owasp = finding.owasp[0] if finding.owasp else "LLM01"
        rid = rule_id(primary_owasp)
        if rid not in rules:
            rules[rid] = {
                "id": rid,
                "name": rule_name(primary_owasp),
                "shortDescription": {"text": rule_name(primary_owasp)},
                "properties": {"owasp": finding.owasp},
            }
        results.append(
            {
                "ruleId": rid,
                "level": _sarif_level(finding.severity.value),
                "message": {"text": finding.title},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": scan.target.url or "target"},
                        }
                    }
                ],
                "properties": {
                    "probe_id": finding.probe_id,
                    "decision": finding.decision.value,
                    "severity": finding.severity.value,
                    "risk_score": finding.risk_score,
                    "owasp": finding.owasp,
                    "evidence": finding.evidence,
                    "detection_layers": finding.metadata.get("detection_layers", {}),
                },
            }
        )

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AgentArmor",
                        "informationUri": "https://github.com/agentarmor/agentarmor",
                        "version": "0.1.0",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(sarif, indent=2), encoding="utf-8")
    return output_path


def _sarif_level(severity: str) -> str:
    if severity in ("CRITICAL", "HIGH"):
        return "error"
    if severity == "MEDIUM":
        return "warning"
    return "note"
