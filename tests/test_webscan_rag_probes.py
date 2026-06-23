"""RAG probe catalog coverage."""

from agentarmor.webscan.probes.catalog import get_web_probes


def test_full_rag_set():
    probes = get_web_probes(["LLM08"], max_probes=20)
    rag_ids = [p.id for p in probes if p.id.startswith("web.rag.")]
    assert len(rag_ids) >= 5
