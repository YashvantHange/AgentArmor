"""SARIF gate — fail CI on configured severities."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def run_gate(sarif_path: Path, fail_on: list[str]) -> int:
    data = json.loads(sarif_path.read_text(encoding="utf-8"))
    fail_levels = {s.upper() for s in fail_on}
    severity_map = {
        "error": {"HIGH", "CRITICAL"},
        "warning": {"MEDIUM"},
        "note": {"LOW", "INFO"},
    }

    violations = []
    for run in data.get("runs", []):
        for result in run.get("results", []):
            level = result.get("level", "note")
            props = result.get("properties", {})
            severity = str(props.get("severity", level)).upper()
            if severity in fail_levels:
                violations.append(result)
            elif level == "error" and fail_levels & {"HIGH", "CRITICAL"}:
                violations.append(result)

    if violations:
        print(f"AgentArmor gate FAILED: {len(violations)} finding(s) at or above {sorted(fail_levels)}")
        for v in violations:
            print(f"  - {v.get('message', {}).get('text', 'unknown')}")
        return 1

    print("AgentArmor gate PASSED")
    return 0


def gate_main(sarif_path: str, fail_on: str) -> None:
    levels = [s.strip() for s in fail_on.split(",") if s.strip()]
    code = run_gate(Path(sarif_path), levels)
    sys.exit(code)
