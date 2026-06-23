"""Ensure red team is opt-in and standard scans unchanged."""

import pytest

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Scan, Target, TargetType
from agentarmor.db.session import ScanRepository
from agentarmor.orchestrator.runner import ScanRunner, _collect_probes


@pytest.mark.asyncio
async def test_standard_scan_does_not_use_redteam_metadata(tmp_path):
    cfg = AppConfig(
        target=Target(type=TargetType.ENDPOINT, url="http://127.0.0.1:9999/v1/chat"),
        database_url=f"sqlite:///{tmp_path / 'reg.db'}",
    )
    scan = Scan(target=cfg.target, metadata={})
    assert scan.metadata.get("scan_mode") != "multi_agent_redteam"


@pytest.mark.asyncio
async def test_collect_probes_without_redteam_mode(tmp_path, detection_config):
    cfg = AppConfig(
        target=Target(type=TargetType.ENDPOINT, url="http://127.0.0.1:9999/v1/chat"),
        database_url=f"sqlite:///{tmp_path / 'reg2.db'}",
    )
    cfg.detection = detection_config
    probes = await _collect_probes(cfg)
    assert len(probes) > 0
    assert all(p.layer in ("L1", "L2", "L3", "L0", "plugin") for p in probes)


@pytest.mark.asyncio
async def test_scan_runner_delegates_redteam_only_when_requested(tmp_path, monkeypatch):
    cfg = AppConfig(
        target=Target(type=TargetType.ENDPOINT, url="http://127.0.0.1:9999/v1/chat"),
        database_url=f"sqlite:///{tmp_path / 'reg3.db'}",
    )
    cfg.detection.analysis_mode = "cloud"
    cfg.detection.agentic.api_key = "test-key"
    repo = ScanRepository(cfg.database_url)
    repo.ensure_schema()
    scan = Scan(target=cfg.target, metadata={"scan_mode": "multi_agent_redteam"})

    called = {"redteam": False}

    async def fake_redteam_run(self, s, **kwargs):
        called["redteam"] = True
        from agentarmor.core.models import ScanStatus
        s.status = ScanStatus.COMPLETED
        return s

    monkeypatch.setattr(
        "agentarmor.redteam.orchestrator.RedTeamOrchestrator.run",
        fake_redteam_run,
    )

    runner = ScanRunner(cfg, repo)
    await runner.run(scan)
    assert called["redteam"]
