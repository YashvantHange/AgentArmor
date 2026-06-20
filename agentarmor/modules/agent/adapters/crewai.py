"""CrewAI framework adapter (simulated harness)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentarmor.modules.agent.adapters.base import AgentHarness


def load_harness(config_path: str | None = None) -> AgentHarness:
    allowed = {"search_web", "read_file", "summarize"}
    forbidden = {"admin_shell", "file_delete", "send_payment"}
    if config_path and Path(config_path).exists():
        _parse_config(config_path, allowed, forbidden)
    return AgentHarness(
        allowed_tools=allowed,
        forbidden_tools=forbidden,
        framework="crewai",
    )


def _parse_config(path: str, allowed: set[str], forbidden: set[str]) -> None:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]
    data: dict[str, Any] = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    tools = data.get("tools", {})
    if isinstance(tools, dict):
        for name in tools.get("allowed", []):
            allowed.add(str(name))
        for name in tools.get("forbidden", []):
            forbidden.add(str(name))
