"""Settings API for GUI."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/settings", tags=["settings"])

_SETTINGS_PATH = Path(os.environ.get("AGENTARMOR_SETTINGS", "agentarmor-settings.json"))


class SettingsResponse(BaseModel):
    portable_mode: bool = False
    l5_enabled: bool = False
    model_dir: str = "~/.agentarmor/models"
    output_dir: str = "./reports"
    api_url: str = "http://127.0.0.1:8787"
    analysis_mode: str = "offline"
    analysis_provider: str = "openai"
    analysis_model: str = "gpt-4o-mini"
    analysis_api_key: str = ""
    l0_enabled: bool = True
    max_variants_per_goal: int = 100
    l0_suites: list[str] = Field(
        default_factory=lambda: ["prompt_leak", "model_theft", "memory_poison", "poisoning"]
    )
    cloud_mutations_enabled: bool = True
    self_play_enabled: bool = False
    self_play_max_rounds: int = 20
    self_play_stop_on_success: bool = True
    self_play_discovery_enabled: bool = True
    self_play_defender_enabled: bool = False


class SettingsUpdate(BaseModel):
    portable_mode: bool | None = None
    l5_enabled: bool | None = None
    model_dir: str | None = None
    output_dir: str | None = None
    analysis_mode: str | None = None
    analysis_provider: str | None = None
    analysis_model: str | None = None
    analysis_api_key: str | None = None
    l0_enabled: bool | None = None
    max_variants_per_goal: int | None = None
    l0_suites: list[str] | None = None
    cloud_mutations_enabled: bool | None = None
    self_play_enabled: bool | None = None
    self_play_max_rounds: int | None = None
    self_play_stop_on_success: bool | None = None
    self_play_discovery_enabled: bool | None = None
    self_play_defender_enabled: bool | None = None


def _load_settings() -> SettingsResponse:
    if _SETTINGS_PATH.exists():
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        return SettingsResponse(**data)
    from agentarmor.core.config import load_config

    cfg = load_config()
    return SettingsResponse(
        l5_enabled=cfg.detection.l5_enabled,
        model_dir=cfg.detection.model_dir,
        output_dir=cfg.reporting.output_dir,
        analysis_mode=cfg.detection.analysis_mode,
        analysis_provider=cfg.detection.agentic.provider,
        analysis_model=cfg.detection.agentic.model,
        l0_enabled=cfg.detection.l0.enabled,
        max_variants_per_goal=cfg.detection.l0.max_variants_per_goal,
        l0_suites=list(cfg.detection.l0.suites),
        cloud_mutations_enabled=cfg.detection.l0.cloud_mutations_enabled,
        self_play_enabled=cfg.detection.self_play.enabled,
        self_play_max_rounds=cfg.detection.self_play.max_rounds,
        self_play_stop_on_success=cfg.detection.self_play.stop_on_success,
        self_play_discovery_enabled=cfg.detection.self_play.discovery_enabled,
        self_play_defender_enabled=cfg.detection.self_play.defender_enabled,
    )


def _save_settings(settings: SettingsResponse) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(settings.model_dump_json(indent=2), encoding="utf-8")


def _sync_app_config(settings: SettingsResponse) -> None:
    import agentarmor.api.app as app_module

    if not hasattr(app_module, "_app_config"):
        return
    cfg = app_module._app_config
    cfg.detection.l5_enabled = settings.l5_enabled
    cfg.detection.model_dir = settings.model_dir
    cfg.reporting.output_dir = settings.output_dir
    cfg.detection.analysis_mode = settings.analysis_mode
    cfg.detection.agentic.enabled = settings.analysis_mode == "cloud"
    cfg.detection.agentic.provider = settings.analysis_provider
    cfg.detection.agentic.model = settings.analysis_model
    cfg.detection.agentic.api_key = settings.analysis_api_key
    cfg.detection.l0.enabled = settings.l0_enabled
    cfg.detection.l0.max_variants_per_goal = settings.max_variants_per_goal
    cfg.detection.l0.suites = list(settings.l0_suites)
    cfg.detection.l0.cloud_mutations_enabled = settings.cloud_mutations_enabled
    cfg.detection.self_play.enabled = settings.self_play_enabled
    cfg.detection.self_play.max_rounds = settings.self_play_max_rounds
    cfg.detection.self_play.stop_on_success = settings.self_play_stop_on_success
    cfg.detection.self_play.discovery_enabled = settings.self_play_discovery_enabled
    cfg.detection.self_play.defender_enabled = settings.self_play_defender_enabled


@router.get("")
def get_settings() -> SettingsResponse:
    return _load_settings()


@router.put("")
def update_settings(body: SettingsUpdate) -> SettingsResponse:
    current = _load_settings()
    updates = body.model_dump(exclude_none=True)
    merged = current.model_copy(update=updates)
    _save_settings(merged)
    _sync_app_config(merged)
    return merged
