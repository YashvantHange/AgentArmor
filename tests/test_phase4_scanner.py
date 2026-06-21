"""Phase 4 tests — marketplace, monitoring, dataset export."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agentarmor.api.app import app
from agentarmor.db.monitor_session import MonitorRepository
from agentarmor.db.session import ScanRepository
from agentarmor.export.anonymizer import anonymize_text
from agentarmor.export.dataset import export_dataset_jsonl
from agentarmor.marketplace.catalog import get_rule, list_rules
from agentarmor.marketplace.installer import install_rule, list_installed, publish_local_probe, uninstall_rule
from agentarmor.marketplace.models import RuleManifest
from agentarmor.sdk.probe_sdk import validate_probe_module

client = TestClient(app)


def test_marketplace_catalog_lists_builtin_rules():
    rules = list_rules()
    assert len(rules) >= 3
    assert get_rule("roleplay-injection") is not None


def test_marketplace_install_and_uninstall(tmp_path):
    install_dir = tmp_path / "installed"
    installed = install_rule("roleplay-injection", install_dir=install_dir)
    assert Path(installed.install_path).exists()
    assert list_installed(install_dir=install_dir)
    assert uninstall_rule("roleplay-injection", install_dir=install_dir)
    assert not list_installed(install_dir=install_dir)


def test_probe_sdk_validate_custom_probe():
    probe = Path("probes/custom_probe.py")
    errors = validate_probe_module(probe)
    assert errors == []


def test_publish_local_probe(tmp_path):
    manifest = RuleManifest(
        id="user.test-probe",
        name="User Test",
        version="0.1.0",
        author="tester",
        category="probe",
        probe_file="custom_probe.py",
        builtin=False,
    )
    installed = publish_local_probe(
        Path("probes/custom_probe.py"),
        manifest=manifest,
        install_dir=tmp_path / "pub",
    )
    assert (Path(installed.install_path) / "custom_probe.py").exists()


def test_anonymizer_redacts_secrets():
    text = "Contact admin@test.com with key sk-abcdefghijklmnopqrstuvwxyz123456"
    out = anonymize_text(text)
    assert "admin@test.com" not in out
    assert "sk-" not in out


def test_dataset_export_jsonl(tmp_path):
    from agentarmor.core.models import Decision, Finding, Severity, Target, TargetType, Scan, ScanStatus
    import uuid

    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    scan_repo = ScanRepository(db_url)
    scan_repo.ensure_schema()
    scan_id = str(uuid.uuid4())
    scan_repo.save_scan(
        Scan(
            id=scan_id,
            target=Target(type=TargetType.ENDPOINT, url="http://localhost"),
            status=ScanStatus.COMPLETED,
            probe_count=1,
            finding_count=1,
        )
    )
    scan_repo.save_finding(
        Finding(
            id=str(uuid.uuid4()),
            scan_id=scan_id,
            probe_id="test.probe",
            probe_name="Test",
            owasp=["LLM01"],
            title="Test finding",
            description="desc",
            severity=Severity.HIGH,
            decision=Decision.WARN,
            risk_score=0.8,
            evidence=["leaked secret sk-abc123456789012345678901234"],
            request_summary="ignore instructions",
            response_excerpt="here is the secret",
        )
    )
    out = export_dataset_jsonl(scan_repo, anonymize=True, output_path=tmp_path / "out.jsonl")
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["probe_id"] == "test.probe"
    assert "sk-" not in json.dumps(row)


def test_monitor_schedule_crud(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'mon.db'}"
    repo = MonitorRepository(db_url)
    repo.ensure_schema()
    schedule = repo.create_schedule(
        name="Daily API",
        target_type="endpoint",
        target_config={"url": "http://127.0.0.1:8000/v1/chat/completions"},
        cron="daily",
    )
    listed = repo.list_schedules()
    assert any(s.id == schedule.id for s in listed)
    assert repo.delete_schedule(schedule.id)


def test_marketplace_api_list():
    r = client.get("/v1/marketplace/rules")
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_monitoring_api_create_list(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTARMOR_DATA_DIR", str(tmp_path))
    r = client.post(
        "/v1/monitoring/schedules",
        json={
            "name": "Test schedule",
            "target_type": "endpoint",
            "target_config": {"url": "http://localhost/v1/chat/completions"},
            "cron": "manual",
        },
    )
    assert r.status_code == 200
    r2 = client.get("/v1/monitoring/schedules")
    assert r2.status_code == 200
    assert len(r2.json()) >= 1
