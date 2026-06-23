"""Web scan daily rate limit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from agentarmor.core.models import Scan, ScanStatus, Target, TargetType
from agentarmor.db.session import ScanRepository


def test_count_web_scans_since_filters_kind(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'rate.db'}"
    repo = ScanRepository(db_url)
    repo.ensure_schema()

    for i in range(3):
        scan = Scan(
            target=Target(type=TargetType.ENDPOINT, url=f"https://example.com/{i}"),
            status=ScanStatus.COMPLETED,
            metadata={"scan_kind": "web", "page_url": f"https://example.com/{i}"},
        )
        repo.save_scan(scan)

    api_scan = Scan(
        target=Target(type=TargetType.ENDPOINT, url="https://api.example.com"),
        status=ScanStatus.COMPLETED,
        metadata={"scan_kind": "endpoint"},
    )
    repo.save_scan(api_scan)

    since = datetime.now(timezone.utc) - timedelta(days=1)
    assert repo.count_web_scans_since(since) == 3


def test_enforce_rate_limit_raises():
    from agentarmor.api.routes import web_scans

    cfg = MagicMock()
    cfg.webscan.max_scans_per_day = 2
    original = web_scans._repo.count_web_scans_since
    try:
        web_scans._repo.count_web_scans_since = lambda since: 2
        with pytest.raises(HTTPException) as exc:
            web_scans._enforce_rate_limit(cfg)
        assert exc.value.status_code == 429
        assert "limit" in exc.value.detail.lower()
    finally:
        web_scans._repo.count_web_scans_since = original
