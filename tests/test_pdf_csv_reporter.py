"""PDF and CSV reporter tests."""

from pathlib import Path

from agentarmor.core.models import Decision, Finding, Scan, Severity, Target, TargetType
from agentarmor.reporting.csv_reporter import write_csv_report
from agentarmor.reporting.pdf_reporter import write_pdf_report


def test_csv_report(tmp_path):
    scan = Scan(target=Target(type=TargetType.AGENT, agent_framework="crewai"), probe_count=5)
    findings = [
        Finding(
            scan_id=scan.id,
            probe_id="agent.tool-abuse",
            probe_name="Tool Abuse",
            owasp=["LLM06"],
            title="Tool Abuse — HIGH",
            severity=Severity.HIGH,
            decision=Decision.FAIL,
            risk_score=0.9,
        )
    ]
    path = write_csv_report(scan, findings, tmp_path / "out.csv")
    text = path.read_text(encoding="utf-8")
    assert "LLM06" in text
    assert "agent.tool-abuse" in text


def test_pdf_report(tmp_path):
    scan = Scan(target=Target(type=TargetType.MCP, mcp_target="./mcp"), probe_count=5)
    findings = [
        Finding(
            scan_id=scan.id,
            probe_id="mcp.data-leakage",
            probe_name="Data Leakage",
            owasp=["LLM02", "LLM06"],
            title="Data Leakage — HIGH",
            severity=Severity.HIGH,
            decision=Decision.FAIL,
            risk_score=0.85,
            response_excerpt="sk-test-SECRET123",
        )
    ]
    path = write_pdf_report(scan, findings, tmp_path / "out.pdf")
    assert path.exists()
    assert path.stat().st_size > 100
