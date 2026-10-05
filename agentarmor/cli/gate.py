"""SARIF gate — fail CI on configured severities.

Exit codes are distinct on purpose:

- ``0`` gate passed, no findings at or above the threshold
- ``1`` gate failed, findings at or above the threshold
- ``2`` gate could not run (SARIF missing, unreadable, or not SARIF)

A pipeline needs to tell "the scan found problems" apart from "the gate never
evaluated anything", because the second usually means an earlier step failed and
produced no SARIF at all.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_UNAVAILABLE = 2


def run_gate(sarif_path: Path, fail_on: list[str]) -> int:
    if not sarif_path.exists():
        print(f"AgentArmor gate ERROR: SARIF file not found: {sarif_path}")
        print("The scan step probably failed before writing a report.")
        return EXIT_UNAVAILABLE

    try:
        raw = sarif_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"AgentArmor gate ERROR: cannot read {sarif_path}: {exc}")
        return EXIT_UNAVAILABLE

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"AgentArmor gate ERROR: {sarif_path} is not valid JSON: {exc}")
        return EXIT_UNAVAILABLE

    if not isinstance(data, dict):
        print(f"AgentArmor gate ERROR: {sarif_path} is not a SARIF object")
        return EXIT_UNAVAILABLE

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
        return EXIT_FAILED

    print("AgentArmor gate PASSED")
    return EXIT_PASSED


def gate_main(sarif_path: str, fail_on: str) -> None:
    levels = [s.strip() for s in fail_on.split(",") if s.strip()]
    code = run_gate(Path(sarif_path), levels)
    sys.exit(code)
