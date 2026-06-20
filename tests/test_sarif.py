"""SARIF reporter tests."""

from agentarmor.core.models import Decision, Finding, Scan, Severity, Target
from agentarmor.reporting.sarif_reporter import write_sarif_report


def test_sarif_report_structure(tmp_path):
    scan = Scan(target=Target(url="http://localhost:8000/v1/chat/completions"))
    findings = [
        Finding(
            scan_id=scan.id,
            probe_id="l1.ignore-instructions",
            probe_name="Ignore Previous Instructions",
            owasp=["LLM01"],
            title="Test finding",
            severity=Severity.HIGH,
            decision=Decision.FAIL,
            risk_score=0.85,
            evidence=["test evidence"],
        )
    ]
    out = tmp_path / "findings.sarif"
    write_sarif_report(scan, findings, out)
    data = out.read_text(encoding="utf-8")
    assert "2.1.0" in data
    assert "LLM01" in data
    assert "agentarmor/owasp/llm01" in data
