"""Single-probe execution outcome for orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agentarmor.core.models import Decision, Finding, ProbeRequest, ProbeResponse, ProbeResult, Severity

if TYPE_CHECKING:
    from agentarmor.orchestrator.runner import RunnableProbe


@dataclass
class ProbeOutcome:
    probe_id: str
    probe_layer: str
    result: ProbeResult
    prompt_text: str
    conversation: list[dict[str, str]]
    detection_decision: Decision
    detection_severity: Severity
    detection_risk: float
    is_finding: bool
    finding: Finding | None = None
    latency_ms: float = 0.0
    owasp: list[str] = field(default_factory=list)


def probe_error_outcome(probe: RunnableProbe, exc: BaseException) -> ProbeOutcome:
    """Convert an unhandled probe exception into a recorded connectivity-style outcome."""
    message = str(exc) or exc.__class__.__name__
    result = ProbeResult(
        probe_id=probe.id,
        probe_name=probe.name,
        owasp=list(probe.owasp),
        request=ProbeRequest(messages=[]),
        response=ProbeResponse(content=""),
        error=message,
    )
    return ProbeOutcome(
        probe_id=probe.id,
        probe_layer=probe.layer,
        result=result,
        prompt_text="",
        conversation=[],
        detection_decision=Decision.PASS,
        detection_severity=Severity.INFO,
        detection_risk=0.0,
        is_finding=False,
        owasp=list(probe.owasp),
    )
