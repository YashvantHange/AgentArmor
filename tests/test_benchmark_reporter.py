"""Benchmark reporter tests."""

from agentarmor.benchmark.config import target_from_provider
from agentarmor.benchmark.models import BenchmarkRun, BenchmarkStatus, ModelScore
from agentarmor.benchmark.models import BenchmarkTarget
from agentarmor.benchmark.reporter import print_terminal_table, write_html_leaderboard, write_json_report


def test_json_and_html_reports(tmp_path):
    run = BenchmarkRun(
        suite_id="owasp-llm-v1",
        suite_name="OWASP LLM Security Suite",
        status=BenchmarkStatus.COMPLETED,
        model_scores=[
            ModelScore(
                target=BenchmarkTarget(label="openai/gpt-4", type="provider", provider="openai"),
                pass_rate=0.94,
                risk_score=0.12,
                rank=1,
            ),
            ModelScore(
                target=BenchmarkTarget(label="anthropic/claude", type="provider", provider="anthropic"),
                pass_rate=0.89,
                risk_score=0.21,
                rank=2,
            ),
        ],
    )
    json_path = write_json_report(run, tmp_path / "bench.json")
    assert "openai" in json_path.read_text(encoding="utf-8")
    html_path = write_html_leaderboard(run, tmp_path / "bench.html")
    html = html_path.read_text(encoding="utf-8")
    assert "Leaderboard" in html
    assert "94%" in html


def test_terminal_table(capsys):
    run = BenchmarkRun(
        suite_id="owasp-llm-v1",
        suite_name="OWASP",
        status=BenchmarkStatus.COMPLETED,
        model_scores=[
            ModelScore(
                target=target_from_provider("openai"),
                pass_rate=0.5,
                risk_score=0.4,
                rank=1,
            )
        ],
    )
    print_terminal_table(run)
    captured = capsys.readouterr()
    assert "Benchmark" in captured.out
