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


def test_html_report_renders_agent_trace_panel(tmp_path):
    scan = Scan(
        target=Target(url="http://localhost/v1/chat/completions"),
        probe_count=5,
        finding_count=1,
    )
    enrichment = {
        "plain_title": "System prompt leaked",
        "what_happened": "The model revealed its hidden instructions.",
        "why_it_matters": "Attackers can craft targeted bypasses.",
        "remediation": ["Refuse to disclose the system prompt."],
        "agentic_notes": "Direct extraction succeeded.",
        "detection_summary": {"l1": "Signature score 0.80", "meta": "Combined risk 0.90"},
        "agent_trace": [
            {"agent": "triage", "label": "Triage", "does": "sorts the finding into an attack category", "model": "gpt-4o-mini", "latency_ms": 120.0, "status": "ok"},
            {"agent": "analyst", "label": "Analyst", "does": "explains the attack technique and cites evidence from the response", "model": "gpt-4o-mini", "latency_ms": 340.0, "status": "ok"},
            {"agent": "owasp_mapper", "label": "OWASP Mapper", "does": "maps the issue to the OWASP LLM Top 10", "model": "gpt-4o-mini", "latency_ms": 210.0, "status": "ok"},
        ],
        "agentic_fallback": False,
    }
    findings = [
        Finding(
            scan_id=scan.id,
            probe_id="l7.direct-leak",
            probe_name="Direct system prompt leak",
            owasp=["LLM07"],
            title="System prompt leaked",
            severity=Severity.HIGH,
            decision=Decision.FAIL,
            risk_score=0.90,
            response_excerpt="My system prompt is: You are a helpful assistant...",
            metadata={"enrichment": enrichment},
        )
    ]
    out = tmp_path / "report.html"
    html = write_html_report(scan, findings, out).read_text(encoding="utf-8")
    assert "How AgentArmor analyzed this" in html
    assert "Triage" in html
    assert "OWASP Mapper" in html
    assert "maps the issue to the OWASP LLM Top 10" in html
    assert "How we scored this" in html
    assert "Combined risk 0.90" in html
