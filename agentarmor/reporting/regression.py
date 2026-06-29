"""Regression scan comparison between baseline and current scan."""

from __future__ import annotations

from agentarmor.core.models import Finding
from agentarmor.db.session import ScanRepository
from agentarmor.reporting.finding_cluster import root_cause_for


def _issue_key(finding: Finding) -> str:
    rc = root_cause_for(finding)
    owasp = finding.owasp[0] if finding.owasp else "none"
    return f"{rc}:{owasp}"


def compare_scans(
    baseline_findings: list[Finding],
    current_findings: list[Finding],
) -> dict[str, list[dict]]:
    """Compare grouped primaries by root cause + primary OWASP."""
    base_primaries = [f for f in baseline_findings if f.metadata.get("is_cluster_primary", True)]
    curr_primaries = [f for f in current_findings if f.metadata.get("is_cluster_primary", True)]

    base_keys = {_issue_key(f): f for f in base_primaries}
    curr_keys = {_issue_key(f): f for f in curr_primaries}

    resolved = []
    for key, f in base_keys.items():
        if key not in curr_keys:
            resolved.append(_summary(f, "resolved"))

    still_vulnerable = []
    for key, f in curr_keys.items():
        if key in base_keys:
            still_vulnerable.append(_summary(f, "still_vulnerable"))

    new_issues = []
    for key, f in curr_keys.items():
        if key not in base_keys:
            new_issues.append(_summary(f, "new"))

    return {
        "resolved": resolved,
        "still_vulnerable": still_vulnerable,
        "new": new_issues,
    }


def _summary(finding: Finding, status: str) -> dict:
    return {
        "status": status,
        "probe_id": finding.probe_id,
        "title": finding.title,
        "severity": finding.severity.value,
        "root_cause": finding.metadata.get("root_cause"),
        "owasp": finding.owasp,
        "cluster_size": finding.metadata.get("cluster_size", 1),
    }


def compare_scan_ids(
    repo: ScanRepository,
    baseline_id: str,
    current_id: str,
) -> dict:
    baseline = repo.list_findings(scan_id=baseline_id)
    current = repo.list_findings(scan_id=current_id)
    if not baseline and not current:
        return {"error": "no findings in either scan"}
    result = compare_scans(baseline, current)
    result["baseline_scan_id"] = baseline_id
    result["current_scan_id"] = current_id
    result["summary"] = {
        "resolved_count": len(result["resolved"]),
        "still_vulnerable_count": len(result["still_vulnerable"]),
        "new_count": len(result["new"]),
    }
    return result
