"""RAG security module runner."""

from __future__ import annotations

import time

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, ProbeResponse, ProbeResult
from agentarmor.modules.rag.probes import RagProbe, build_retriever, get_rag_probes


async def run_rag_probe(config: AppConfig, probe: RagProbe) -> ProbeResult:
    start = time.perf_counter()
    try:
        docs, retriever = build_retriever(config)
        triggered, summary, raw = probe.run(docs, retriever, config)
        content = f"[FINDING] {summary}" if triggered else summary
        latency_ms = (time.perf_counter() - start) * 1000
        return ProbeResult(
            probe_id=probe.id,
            probe_name=probe.name,
            owasp=probe.owasp,
            request=ProbeRequest(
                messages=[{"role": "user", "content": f"RAG probe on {len(docs)} docs"}]
            ),
            response=ProbeResponse(content=content, raw={**raw, "triggered": triggered}),
            latency_ms=latency_ms,
            metadata={"module": "rag", "corpus_size": len(docs), "triggered": triggered},
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return ProbeResult(
            probe_id=probe.id,
            probe_name=probe.name,
            owasp=probe.owasp,
            request=ProbeRequest(messages=[]),
            response=ProbeResponse(content="", raw={}),
            latency_ms=latency_ms,
            error=str(exc),
            metadata={"module": "rag"},
        )


def list_rag_probes() -> list[RagProbe]:
    return get_rag_probes()
