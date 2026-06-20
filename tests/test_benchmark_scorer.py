"""Benchmark scorer tests."""

from agentarmor.benchmark.models import ProbeBenchmarkResult
from agentarmor.benchmark.scorer import rank_models, score_model
from agentarmor.benchmark.suite_loader import load_suite


def test_score_model_pass_rate():
    suite = load_suite("owasp")
    results = [
        ProbeBenchmarkResult(
            probe_id="l1.ignore-instructions",
            category_id="LLM01",
            decision="PASS",
            risk_score=0.1,
            severity="INFO",
        ),
        ProbeBenchmarkResult(
            probe_id="l1.reveal-system-prompt",
            category_id="LLM01",
            decision="FAIL",
            risk_score=0.9,
            severity="HIGH",
        ),
        ProbeBenchmarkResult(
            probe_id="l1.act-as-root",
            category_id="LLM01",
            decision="PASS",
            risk_score=0.2,
            severity="LOW",
        ),
        ProbeBenchmarkResult(
            probe_id="l2.roleplay",
            category_id="LLM01",
            decision="PASS",
            risk_score=0.15,
            severity="LOW",
        ),
    ]
    score = score_model(suite, "gpt-test", "provider", "openai", "gpt-3.5-turbo", results)
    assert 0.0 < score.pass_rate < 1.0
    assert score.risk_score > 0.0
    assert len(score.category_scores) >= 1


def test_rank_models():
    suite = load_suite("owasp")
    a = score_model(suite, "a", "provider", "openai", None, [])
    b = score_model(suite, "b", "provider", "anthropic", None, [])
    a.pass_rate = 0.9
    b.pass_rate = 0.7
    ranked = rank_models([b, a])
    assert ranked[0].target.label == "a"
    assert ranked[0].rank == 1
