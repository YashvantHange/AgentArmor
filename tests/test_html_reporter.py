"""HTML reporter tests."""

from pathlib import Path

from agentarmor.core.models import Decision, Finding, Scan, Severity, Target
from agentarmor.reporting.html_reporter import write_html_report


def test_html_report_writes(tmp_path):
    scan = Scan(
        target=Target(url="http://localhost/v1/chat/completions"),
        probe_count=13,
        finding_count=1,
    )
    findings = [
        Finding(
            scan_id=scan.id,
            probe_id="l1.ignore-instructions",
            probe_name="Ignore Previous Instructions",
            owasp=["LLM01"],
            title="Ignore — HIGH",
            severity=Severity.HIGH,
            decision=Decision.FAIL,
            risk_score=0.85,
            evidence=["L1 signature match"],
            response_excerpt="Here is how to bypass filters...",
        )
    ]
    out = tmp_path / "report.html"
    path = write_html_report(scan, findings, out)
    html = path.read_text(encoding="utf-8")
    assert "AgentArmor" in html
    assert "LLM01" in html
    assert "Executive Summary" in html
    assert "HIGH" in html
