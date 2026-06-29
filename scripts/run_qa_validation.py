"""Validate QA scan exports per exe QA plan."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

BASE = Path(__file__).resolve().parents[1]
REPORT_DIRS = [BASE / "reports", Path(r"C:\AgentArmorQA\reports")]


def find_reports() -> list[Path]:
    found: list[Path] = []
    for root in REPORT_DIRS:
        if root.exists():
            found.extend(root.rglob("scan-*.json"))
    return sorted(set(found))


def validate_scan(json_path: Path) -> dict:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    scan_id = data["scan"]["id"]
    api_count = None
    try:
        r = httpx.get(f"http://127.0.0.1:8787/v1/scans/{scan_id}", timeout=10)
        if r.status_code == 200:
            api_count = r.json().get("finding_count")
    except Exception:
        pass

    json_count = data["summary"]["finding_count"]
    json_len = len(data["findings"])
    sarif_path = json_path.with_suffix(".sarif")
    sarif_count = None
    sarif_ok = False
    if sarif_path.exists():
        sarif = json.loads(sarif_path.read_text(encoding="utf-8"))
        sarif_count = len(sarif.get("runs", [{}])[0].get("results", []))
        run = sarif.get("runs", [{}])[0]
        driver = run.get("tool", {}).get("driver", {})
        sarif_ok = (
            sarif.get("version") == "2.1.0"
            and bool(sarif.get("$schema"))
            and driver.get("name") == "AgentArmor"
            and sarif_count == json_count
        )

    html_path = json_path.with_suffix(".html")
    html_count_ok = False
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        import re
        html_count_ok = bool(re.search(rf">\s*{json_count}\s*<.*?finding\(s\)", html, re.S)) or f"{json_count} finding(s)" in html

    connectivity_failed = any(
        f.get("probe_id") == "connectivity.failed" for f in data["findings"]
    )
    conn_errors = sum(
        1 for f in data["findings"] if f.get("metadata", {}).get("connectivity_error")
    )

    counts_match = json_count == json_len == sarif_count
    if api_count is not None:
        counts_match = counts_match and api_count == json_count

    return {
        "scan_id": scan_id,
        "target_type": data["scan"].get("target", {}).get("type"),
        "probe_count": data["summary"]["probe_count"],
        "finding_count": json_count,
        "counts_match": counts_match,
        "sarif_ok": sarif_ok,
        "html_count_ok": html_count_ok,
        "connectivity_failed_finding": connectivity_failed,
        "connectivity_error_findings": conn_errors,
        "json_path": str(json_path),
    }


def main() -> int:
    reports = find_reports()
    if not reports:
        print("No scan-*.json reports found")
        return 1

    failures = 0
    for p in reports:
        result = validate_scan(p)
        status = "PASS" if (
            result["counts_match"] and result["sarif_ok"] and result["html_count_ok"]
        ) else "FAIL"
        if status == "FAIL":
            failures += 1
        print(f"\n[{status}] {result['target_type']} scan {result['scan_id'][:8]}...")
        for k, v in result.items():
            if k != "json_path":
                print(f"  {k}: {v}")

    print(f"\nValidated {len(reports)} scan(s), {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
