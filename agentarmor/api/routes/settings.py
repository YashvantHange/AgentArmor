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


class SettingsUpdate(BaseModel):
    portable_mode: bool | None = None
    l5_enabled: bool | None = None
    model_dir: str | None = None
    output_dir: str | None = None


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
    )


def _save_settings(settings: SettingsResponse) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(settings.model_dump_json(indent=2), encoding="utf-8")


@router.get("")
def get_settings() -> SettingsResponse:
    return _load_settings()


@router.put("")
def update_settings(body: SettingsUpdate) -> SettingsResponse:
    current = _load_settings()
    updates = body.model_dump(exclude_none=True)
    merged = current.model_copy(update=updates)
    _save_settings(merged)

    # Apply to runtime detection config when server is running
    import agentarmor.api.app as app_module

    if hasattr(app_module, "_app_config"):
        if body.l5_enabled is not None:
            app_module._app_config.detection.l5_enabled = body.l5_enabled
        if body.model_dir is not None:
            app_module._app_config.detection.model_dir = body.model_dir
        if body.output_dir is not None:
            app_module._app_config.reporting.output_dir = body.output_dir
    return merged
