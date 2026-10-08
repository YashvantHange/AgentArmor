"""SARIF gate tests — exit codes and malformed-input handling."""

import json

import pytest

from agentarmor.cli.gate import (
    EXIT_FAILED,
    EXIT_PASSED,
    EXIT_UNAVAILABLE,
    gate_main,
    run_gate,
)


def _sarif(results: list[dict]) -> dict:
    return {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "AgentArmor"}}, "results": results}],
    }


def test_missing_sarif_file_returns_unavailable(tmp_path, capsys):
    missing = tmp_path / "nope.sarif"
    assert run_gate(missing, ["HIGH"]) == EXIT_UNAVAILABLE
    out = capsys.readouterr().out
    assert "not found" in out
    assert str(missing) in out


def test_invalid_json_returns_unavailable(tmp_path, capsys):
    path = tmp_path / "broken.sarif"
    path.write_text("{not json", encoding="utf-8")
    assert run_gate(path, ["HIGH"]) == EXIT_UNAVAILABLE
    assert "not valid JSON" in capsys.readouterr().out


def test_non_object_sarif_returns_unavailable(tmp_path, capsys):
    path = tmp_path / "list.sarif"
    path.write_text("[]", encoding="utf-8")
    assert run_gate(path, ["HIGH"]) == EXIT_UNAVAILABLE
    assert "not a SARIF object" in capsys.readouterr().out


def test_empty_but_valid_sarif_passes(tmp_path, capsys):
    path = tmp_path / "empty.sarif"
    path.write_text(json.dumps({"runs": []}), encoding="utf-8")
    assert run_gate(path, ["HIGH", "CRITICAL"]) == EXIT_PASSED
    assert "PASSED" in capsys.readouterr().out


def test_high_severity_finding_fails(tmp_path, capsys):
    path = tmp_path / "findings.sarif"
    path.write_text(
        json.dumps(
            _sarif(
                [
                    {
                        "level": "error",
                        "message": {"text": "Prompt injection accepted"},
                        "properties": {"severity": "HIGH"},
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    assert run_gate(path, ["HIGH", "CRITICAL"]) == EXIT_FAILED
    out = capsys.readouterr().out
    assert "FAILED" in out
    assert "Prompt injection accepted" in out


def test_severity_below_threshold_passes(tmp_path):
    path = tmp_path / "low.sarif"
    path.write_text(
        json.dumps(
            _sarif(
                [
                    {
                        "level": "note",
                        "message": {"text": "Informational"},
                        "properties": {"severity": "LOW"},
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    assert run_gate(path, ["HIGH", "CRITICAL"]) == EXIT_PASSED


@pytest.mark.parametrize(
    "contents,expected",
    [
        (None, EXIT_UNAVAILABLE),
        ("{not json", EXIT_UNAVAILABLE),
        (json.dumps({"runs": []}), EXIT_PASSED),
    ],
)
def test_gate_main_exit_codes(tmp_path, contents, expected):
    path = tmp_path / "gate.sarif"
    if contents is not None:
        path.write_text(contents, encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        gate_main(str(path), "HIGH,CRITICAL")
    assert excinfo.value.code == expected
