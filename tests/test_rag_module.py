"""RAG module tests."""

from pathlib import Path

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Target, TargetType
from agentarmor.modules.rag.probes import get_rag_probes
from agentarmor.modules.rag.runner import run_rag_probe

CORPUS = Path(__file__).resolve().parent / "fixtures" / "rag_corpus"


def test_rag_probe_count():
    assert len(get_rag_probes()) == 4


@pytest.mark.asyncio
async def test_rag_poisoning_probe():
    cfg = AppConfig(
        target=Target(type=TargetType.RAG, rag_corpus=str(CORPUS)),
    )
    probe = next(p for p in get_rag_probes() if p.id == "rag.document-poisoning")
    result = await run_rag_probe(cfg, probe)
    assert result.error is None
    assert result.metadata.get("triggered") is True


@pytest.mark.asyncio
async def test_rag_retrieval_manipulation():
    cfg = AppConfig(
        target=Target(type=TargetType.RAG, rag_corpus=str(CORPUS)),
    )
    probe = next(p for p in get_rag_probes() if p.id == "rag.retrieval-manipulation")
    result = await run_rag_probe(cfg, probe)
    assert result.error is None
    assert result.metadata.get("triggered") is True
