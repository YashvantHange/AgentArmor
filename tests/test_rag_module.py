"""RAG module tests."""

from pathlib import Path
from unittest.mock import patch

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Target, TargetType
from agentarmor.modules.rag.corpus import Document
from agentarmor.modules.rag.poisoning import SYNTHETIC_POISON_DOCUMENTS
from agentarmor.modules.rag.probes import get_rag_probes
from agentarmor.modules.rag.retriever import HashEmbedder, Retriever
from agentarmor.modules.rag.runner import run_rag_probe

CORPUS = Path(__file__).resolve().parent / "fixtures" / "rag_corpus"

SYNTHETIC_PROBE_IDS = (
    "rag.synthetic-label-poisoning",
    "rag.synthetic-backdoor-activation",
    "rag.synthetic-trigger-phrase",
)


def _probe(probe_id: str):
    return next(p for p in get_rag_probes() if p.id == probe_id)


def test_rag_probe_count():
    assert len(get_rag_probes()) == 8


@pytest.mark.asyncio
async def test_rag_poisoning_probe():
    cfg = AppConfig(
        target=Target(type=TargetType.RAG, rag_corpus=str(CORPUS)),
    )
    probe = _probe("rag.document-poisoning")
    result = await run_rag_probe(cfg, probe)
    assert result.error is None
    assert result.metadata.get("triggered") is True


@pytest.mark.asyncio
async def test_rag_retrieval_manipulation():
    cfg = AppConfig(
        target=Target(type=TargetType.RAG, rag_corpus=str(CORPUS)),
    )
    probe = _probe("rag.retrieval-manipulation")
    result = await run_rag_probe(cfg, probe)
    assert result.error is None
    assert result.metadata.get("triggered") is True


@pytest.mark.parametrize(
    ("probe_id", "synthetic_source"),
    [
        ("rag.synthetic-label-poisoning", "synthetic:label-poison"),
        ("rag.synthetic-backdoor-activation", "synthetic:backdoor"),
        ("rag.synthetic-trigger-phrase", "synthetic:trigger-phrase"),
    ],
)
def test_synthetic_rag_probe_triggers_when_poison_ranked(probe_id: str, synthetic_source: str):
    cfg = AppConfig(target=Target(type=TargetType.RAG, rag_corpus=str(CORPUS)))
    probe = _probe(probe_id)
    poison_doc = next(d for d in SYNTHETIC_POISON_DOCUMENTS if d.source == synthetic_source)
    base = [Document(id="base", text="benign handbook content", source="base.txt")]
    dummy = Retriever(base, HashEmbedder())

    with patch.object(
        Retriever,
        "retrieve",
        return_value=[(poison_doc, 0.91)],
    ):
        triggered, summary, raw = probe.run(base, dummy, cfg)

    assert triggered is True
    assert raw.get("suite") == "poisoning"
    assert raw.get("doc") == poison_doc.id
    assert "Synthetic" in summary or "synthetic" in summary.lower()


@pytest.mark.parametrize("probe_id", SYNTHETIC_PROBE_IDS)
def test_synthetic_rag_probe_no_trigger_without_poison_match(probe_id: str):
    cfg = AppConfig(target=Target(type=TargetType.RAG, rag_corpus=str(CORPUS)))
    probe = _probe(probe_id)
    base = [Document(id="base", text="unrelated content", source="base.txt")]
    dummy = Retriever(base, HashEmbedder())

    with patch.object(
        Retriever,
        "retrieve",
        return_value=[(base[0], 0.99)],
    ):
        triggered, _summary, raw = probe.run(base, dummy, cfg)

    assert triggered is False


@pytest.mark.asyncio
@pytest.mark.parametrize("probe_id", SYNTHETIC_PROBE_IDS)
async def test_synthetic_rag_probe_via_runner(probe_id: str):
    cfg = AppConfig(target=Target(type=TargetType.RAG, rag_corpus=str(CORPUS)))
    probe = _probe(probe_id)
    result = await run_rag_probe(cfg, probe)
    assert result.error is None
    assert result.probe_id == probe_id
    assert "triggered" in result.metadata
