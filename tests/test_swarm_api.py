"""Swarm API, job registry, service seam and CLI surface."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agentarmor.api import app as app_module
from agentarmor.api.routes import swarms as swarms_route
from agentarmor.core.jobs import JobRegistry
from agentarmor.core.models import Scan, ScanStatus
from agentarmor.db.session import ScanRepository


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client with an isolated database and no real launching."""
    repo = ScanRepository(f"sqlite:///{tmp_path / 'api.db'}")
    repo.ensure_schema()
    monkeypatch.setattr(swarms_route, "_repo", repo)
    monkeypatch.setattr(swarms_route, "job_registry", JobRegistry())
    # /v1/scans/{id} keeps its own module-level repository, so it has to be
    # pointed at the same database for the cross-endpoint test to mean anything.
    from agentarmor.api.routes import scans as scans_route

    monkeypatch.setattr(scans_route, "_repo", repo)
    monkeypatch.setattr(app_module, "_repo", repo)

    cfg = swarms_route._app_config.model_copy(deep=True)
    cfg.database_url = f"sqlite:///{tmp_path / 'api.db'}"
    cfg.detection.agentic.api_key = "test-key"
    monkeypatch.setattr(swarms_route, "_app_config", cfg)

    def fake_build_config(body):
        from agentarmor.core.config import merge_cli_target

        built = cfg.model_copy(deep=True)
        built = merge_cli_target(built, url=body.url or "http://target.test/v1/chat")
        built.detection.analysis_mode = "cloud"
        built.detection.agentic.api_key = "test-key"
        return built

    monkeypatch.setattr(swarms_route, "_build_config", fake_build_config)

    async def fake_validate_key(config):
        return None

    monkeypatch.setattr(
        "agentarmor.detection.agentic.preflight.validate_analysis_key", fake_validate_key
    )

    launched: list[dict] = []

    async def fake_run(cfg_arg, scan_id, *, goal_id, agents, max_concurrent, formats):
        launched.append(
            {
                "scan_id": scan_id,
                "goal_id": goal_id,
                "agents": agents,
                "max_concurrent": max_concurrent,
            }
        )
        await asyncio.sleep(0)

    monkeypatch.setattr(swarms_route, "_run_swarm_background", fake_run)

    with TestClient(app_module.app) as test_client:
        yield test_client, repo, launched


def _body(**overrides) -> dict:
    payload = {"goal_id": "extract_system_prompt", "url": "http://target.test/v1/chat"}
    payload.update(overrides)
    return payload


# --- goals ------------------------------------------------------------------


def test_list_goals(client):
    test_client, _repo, _launched = client
    response = test_client.get("/v1/swarms/goals")
    assert response.status_code == 200
    goals = response.json()
    assert goals
    for goal in goals:
        assert goal["id"] and goal["name"] and goal["description"]
        assert goal["owasp"]
        assert goal["max_agents"] == 100


def test_goals_route_is_not_shadowed_by_the_id_route(client):
    """Literal paths must be declared before /{scan_id}."""
    test_client, _repo, _launched = client
    assert test_client.get("/v1/swarms/goals").status_code == 200


# --- the product decision, enforced in CI -----------------------------------


def test_there_is_no_free_text_goal_field():
    """A free-text objective is unrepresentable, not merely rejected."""
    fields = set(swarms_route.SwarmCreateRequest.model_fields)
    for forbidden in ("goal_text", "prompt", "custom_goal", "objective", "instruction"):
        assert forbidden not in fields


def test_goal_id_is_required():
    with pytest.raises(Exception):
        swarms_route.SwarmCreateRequest(url="http://x")


# --- create -----------------------------------------------------------------


def test_create_launches_a_swarm(client):
    test_client, repo, launched = client
    response = test_client.post("/v1/swarms", json=_body(agents=12, max_concurrent=4))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["scan_kind"] == "swarm"
    assert data["agents"] == 12
    assert data["max_concurrent"] == 4

    stored = repo.get_scan(data["scan_id"])
    assert stored is not None
    assert stored.metadata["scan_kind"] == "swarm"
    assert stored.metadata["goal_id"] == "extract_system_prompt"
    assert launched and launched[0]["agents"] == 12


def test_create_rejects_an_unknown_goal(client):
    test_client, _repo, _launched = client
    response = test_client.post("/v1/swarms", json=_body(goal_id="do-whatever"))
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Unknown goal" in detail
    assert "extract_system_prompt" in detail, "the error should list valid goals"


def test_create_clamps_the_agent_count(client):
    """An over-large request is answered with what will actually run."""
    test_client, _repo, _launched = client
    data = test_client.post("/v1/swarms", json=_body(agents=500)).json()
    assert data["agents"] == 100
    assert data["agents_requested"] == 500


def test_create_clamps_concurrency(client):
    test_client, _repo, _launched = client
    data = test_client.post("/v1/swarms", json=_body(agents=100, max_concurrent=99)).json()
    assert data["max_concurrent"] == 16


def test_create_uses_defaults_when_unspecified(client):
    test_client, _repo, _launched = client
    data = test_client.post("/v1/swarms", json=_body()).json()
    assert data["agents"] == 24
    assert data["max_concurrent"] == 8


def test_create_requires_an_analysis_key(client, monkeypatch):
    test_client, _repo, _launched = client

    def keyless(body):
        from agentarmor.core.config import merge_cli_target

        built = swarms_route._app_config.model_copy(deep=True)
        built = merge_cli_target(built, url="http://target.test/v1/chat")
        built.detection.agentic.api_key = ""
        built.detection.agentic.api_key_env = "AGENTARMOR_DEFINITELY_UNSET_KEY"
        return built

    monkeypatch.setattr(swarms_route, "_build_config", keyless)
    response = test_client.post("/v1/swarms", json=_body())
    assert response.status_code == 400
    assert "analysis API key" in response.json()["detail"]


def test_create_rejects_when_swarm_is_disabled(client, monkeypatch):
    test_client, _repo, _launched = client

    def disabled(body):
        from agentarmor.core.config import merge_cli_target

        cfg = swarms_route._app_config.model_copy(deep=True)
        cfg = merge_cli_target(cfg, url="http://target.test/v1/chat")
        cfg.detection.analysis_mode = "cloud"
        cfg.detection.agentic.api_key = "test-key"
        cfg.swarm.enabled = False
        return cfg

    monkeypatch.setattr(swarms_route, "_build_config", disabled)
    response = test_client.post("/v1/swarms", json=_body())
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]


# --- limits -----------------------------------------------------------------


def test_the_daily_limit_returns_429_and_names_the_key(client):
    test_client, repo, _launched = client
    for _ in range(5):
        scan = Scan(target=swarms_route._app_config.target)
        scan.metadata["scan_kind"] = "swarm"
        repo.save_scan(scan)

    response = test_client.post("/v1/swarms", json=_body())
    assert response.status_code == 429
    assert "swarm.max_swarms_per_day" in response.json()["detail"]


def test_the_concurrent_limit_returns_429(client, monkeypatch):
    test_client, _repo, _launched = client
    # A task created inside asyncio.run() dies with that loop, so simulate an
    # occupied registry rather than relying on a task surviving across loops.
    monkeypatch.setattr(
        swarms_route.job_registry, "count_active", lambda *, kind=None: 1
    )
    response = test_client.post("/v1/swarms", json=_body())
    assert response.status_code == 429
    assert "already running" in response.json()["detail"]
    assert "swarm.max_concurrent_swarms" in response.json()["detail"]


def test_only_swarm_scans_count_toward_the_daily_limit(client):
    test_client, repo, _launched = client
    for _ in range(9):
        scan = Scan(target=swarms_route._app_config.target)
        scan.metadata["scan_kind"] = "web"
        repo.save_scan(scan)
    assert test_client.post("/v1/swarms", json=_body()).status_code == 200


# --- read and cancel --------------------------------------------------------


def test_get_returns_the_scan(client):
    test_client, _repo, _launched = client
    scan_id = test_client.post("/v1/swarms", json=_body()).json()["scan_id"]
    data = test_client.get(f"/v1/swarms/{scan_id}").json()
    assert data["id"] == scan_id
    assert data["metadata"]["scan_kind"] == "swarm"
    assert "running" in data


def test_get_404s_for_an_unknown_id(client):
    test_client, _repo, _launched = client
    assert test_client.get("/v1/swarms/nope").status_code == 404


def test_get_404s_for_a_non_swarm_scan(client):
    test_client, repo, _launched = client
    scan = Scan(target=swarms_route._app_config.target)
    repo.save_scan(scan)
    assert test_client.get(f"/v1/swarms/{scan.id}").status_code == 404


def test_cancel_reports_when_nothing_is_running(client):
    test_client, _repo, _launched = client
    scan_id = test_client.post("/v1/swarms", json=_body()).json()["scan_id"]
    data = test_client.post(f"/v1/swarms/{scan_id}/cancel").json()
    assert data["cancelled"] is False


def test_cancel_404s_for_an_unknown_id(client):
    test_client, _repo, _launched = client
    assert test_client.post("/v1/swarms/nope/cancel").status_code == 404


def test_a_swarm_scan_is_reachable_through_the_scans_endpoints(client):
    """The payoff of reusing the scans table: no duplicated endpoints."""
    test_client, _repo, _launched = client
    scan_id = test_client.post("/v1/swarms", json=_body()).json()["scan_id"]
    assert test_client.get(f"/v1/scans/{scan_id}").status_code == 200
    assert test_client.get(f"/v1/scans/{scan_id}/findings").status_code == 200


def test_swarm_routes_do_not_duplicate_sse_findings_or_reports():
    """Web scans duplicated those three; this must not compound it."""
    paths = {route.path for route in swarms_route.router.routes}
    assert paths == {
        "/v1/swarms/goals",
        "/v1/swarms",
        "/v1/swarms/{scan_id}",
        "/v1/swarms/{scan_id}/cancel",
    }


# --- job registry -----------------------------------------------------------


def test_registry_tracks_cancels_and_counts():
    async def scenario():
        registry = JobRegistry()

        async def long_running():
            await asyncio.sleep(3600)

        registry.launch("a", kind="swarm", coro=long_running())
        registry.launch("b", kind="scan", coro=long_running())
        assert registry.count_active() == 2
        assert registry.count_active(kind="swarm") == 1
        assert registry.is_running("a") is True
        assert registry.active_ids(kind="swarm") == ["a"]

        assert registry.cancel("a") is True
        assert registry.cancel("missing") is False
        await asyncio.sleep(0)
        assert registry.is_running("a") is False

        await registry.drain(timeout=1.0)
        assert registry.count_active() == 0

    asyncio.run(scenario())


def test_registry_forgets_a_finished_job():
    async def scenario():
        registry = JobRegistry()

        async def quick():
            return None

        registry.launch("x", kind="swarm", coro=quick())
        await asyncio.sleep(0.01)
        assert registry.count_active() == 0
        assert registry.get("x") is None

    asyncio.run(scenario())


def test_registry_logs_rather_than_swallows_a_failure(caplog):
    async def scenario():
        registry = JobRegistry()

        async def boom():
            raise RuntimeError("member exploded")

        registry.launch("x", kind="swarm", coro=boom())
        await asyncio.sleep(0.01)

    with caplog.at_level("ERROR"):
        asyncio.run(scenario())
    assert any("member exploded" in record.getMessage() for record in caplog.records)


def test_relaunching_the_same_id_returns_the_live_job():
    async def scenario():
        registry = JobRegistry()

        async def long_running():
            await asyncio.sleep(3600)

        first = registry.launch("x", kind="swarm", coro=long_running())
        second_coro = long_running()
        second = registry.launch("x", kind="swarm", coro=second_coro)
        assert first is second
        second_coro.close()
        registry.cancel("x")
        await registry.drain(timeout=1.0)

    asyncio.run(scenario())


# --- the service seam -------------------------------------------------------


def test_the_service_rejects_an_unknown_goal(tmp_path):
    from agentarmor.core.config import AppConfig
    from agentarmor.services.swarm_service import execute_swarm

    cfg = AppConfig()
    cfg.database_url = f"sqlite:///{tmp_path / 's.db'}"
    with pytest.raises(ValueError, match="Unknown swarm goal"):
        asyncio.run(execute_swarm(cfg, goal_id="nope", agents=1, max_concurrent=1))


def test_build_swarm_scan_marks_the_kind():
    from agentarmor.core.config import AppConfig
    from agentarmor.services.swarm_service import build_swarm_scan

    scan = build_swarm_scan(
        AppConfig(), goal_id="extract_system_prompt", agents=7, max_concurrent=3
    )
    assert scan.metadata["scan_kind"] == "swarm"
    assert scan.metadata["agent_count"] == 7
    assert scan.metadata["max_concurrent"] == 3


def test_the_api_and_cli_share_one_service():
    """Same relationship scan and POST /v1/scans have via execute_scan."""
    import inspect

    from agentarmor.cli import swarm as cli_swarm
    from agentarmor.services.swarm_service import execute_swarm

    assert "execute_swarm" in inspect.getsource(cli_swarm.run)
    assert "execute_swarm" in inspect.getsource(swarms_route._run_swarm_background)
    params = inspect.signature(execute_swarm).parameters
    for expected in ("goal_id", "agents", "max_concurrent", "scan_id", "formats"):
        assert expected in params


# --- CLI surface ------------------------------------------------------------


def test_cli_exposes_goals_and_run():
    from typer.testing import CliRunner

    from agentarmor.cli.main import app

    runner = CliRunner()
    assert runner.invoke(app, ["swarm", "--help"]).exit_code == 0
    listing = runner.invoke(app, ["swarm", "goals"])
    assert listing.exit_code == 0
    assert "extract_system_prompt" in listing.stdout


def test_cli_rejects_an_unknown_goal_and_lists_valid_ones():
    from typer.testing import CliRunner

    from agentarmor.cli.main import app

    result = CliRunner().invoke(
        app, ["swarm", "run", "--goal", "nonsense", "--url", "http://x/v1/chat"]
    )
    assert result.exit_code == 1
    assert "unknown goal" in result.output.lower()
    assert "extract_system_prompt" in result.output


def test_count_scans_since_filters_by_kind(tmp_path):
    repo = ScanRepository(f"sqlite:///{tmp_path / 'k.db'}")
    repo.ensure_schema()
    from agentarmor.core.config import AppConfig

    target = AppConfig().target
    for kind in ("swarm", "swarm", "web"):
        scan = Scan(target=target)
        scan.metadata["scan_kind"] = kind
        repo.save_scan(scan)

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    assert repo.count_scans_since(since, scan_kind="swarm") == 2
    assert repo.count_scans_since(since, scan_kind="web") == 1
    # The original helper must keep working for the web-scan route.
    assert repo.count_web_scans_since(since) == 1


def test_cancelled_status_is_a_terminal_scan_status():
    assert ScanStatus.CANCELLED.value == "cancelled"
