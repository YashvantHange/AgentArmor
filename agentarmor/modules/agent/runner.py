"""Agent security module runner."""

from __future__ import annotations

import time

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, ProbeResponse, ProbeResult
from agentarmor.modules.agent.adapters import crewai, langgraph
from agentarmor.modules.agent.adapters.base import AgentHarness
from agentarmor.modules.agent.probes import AgentProbe, get_agent_probes

_ADAPTERS = {
    "crewai": crewai.load_harness,
    "langgraph": langgraph.load_harness,
}


def load_harness(config: AppConfig) -> AgentHarness:
    framework = (config.target.agent_framework or "crewai").lower()
    loader = _ADAPTERS.get(framework)
    if loader is None:
        raise ValueError(
            f"Unsupported agent framework '{framework}'. "
            f"Supported: {', '.join(sorted(_ADAPTERS))}"
        )
    return loader(config.target.agent_config)


async def run_agent_probe(
    config: AppConfig,
    probe: AgentProbe,
) -> ProbeResult:
    start = time.perf_counter()
    harness = load_harness(config)
    prompt = probe.build_prompt(config)
    try:
        run_result = harness.run(prompt, canary_secret=config.module_agent.canary_secret)
        triggered, evidence = probe.evaluate(run_result, config)
        content = run_result.response
        if triggered:
            content = f"[FINDING] {'; '.join(evidence)}\n{content}"
        latency_ms = (time.perf_counter() - start) * 1000
        return ProbeResult(
            probe_id=probe.id,
            probe_name=probe.name,
            owasp=probe.owasp,
            request=ProbeRequest(messages=[{"role": "user", "content": prompt}]),
            response=ProbeResponse(
                content=content,
                raw={
                    "tool_calls": [
                        {"name": tc.name, "arguments": tc.arguments}
                        for tc in run_result.tool_calls
                    ],
                    "memory": run_result.memory,
                    "triggered": triggered,
                    "evidence": evidence,
                },
            ),
            latency_ms=latency_ms,
            metadata={
                "framework": harness.framework,
                "module": "agent",
                "triggered": triggered,
            },
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return ProbeResult(
            probe_id=probe.id,
            probe_name=probe.name,
            owasp=probe.owasp,
            request=ProbeRequest(messages=[{"role": "user", "content": prompt}]),
            response=ProbeResponse(content="", raw={}),
            latency_ms=latency_ms,
            error=str(exc),
            metadata={"module": "agent"},
        )


def list_agent_probes() -> list[AgentProbe]:
    return get_agent_probes()
