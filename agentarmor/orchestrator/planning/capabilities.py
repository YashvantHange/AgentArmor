"""Target capability detection for probe planning."""

from __future__ import annotations

from dataclasses import dataclass, field

from agentarmor.core.config import AppConfig
from agentarmor.core.models import TargetType


@dataclass
class TargetCapabilities:
    rag: bool = False
    memory: bool = False
    tools: bool = False
    mcp: bool = False
    browser: bool = False
    vision: bool = False
    audio: bool = False

    def satisfied(self, requires: list[str]) -> bool:
        if not requires:
            return True
        mapping = {
            "rag": self.rag,
            "memory": self.memory,
            "tools": self.tools,
            "mcp": self.mcp,
            "browser": self.browser,
            "vision": self.vision,
            "audio": self.audio,
        }
        return all(mapping.get(req, False) for req in requires)

    def to_dict(self) -> dict[str, bool]:
        return {
            "rag": self.rag,
            "memory": self.memory,
            "tools": self.tools,
            "mcp": self.mcp,
            "browser": self.browser,
            "vision": self.vision,
            "audio": self.audio,
        }


def detect_capabilities(config: AppConfig) -> TargetCapabilities:
    """Heuristic capability map from target type (sync; no network)."""
    t = config.target.type
    if t == TargetType.RAG:
        return TargetCapabilities(rag=True, memory=True)
    if t == TargetType.MCP:
        return TargetCapabilities(mcp=True, tools=True)
    if t == TargetType.AGENT:
        return TargetCapabilities(tools=True, memory=True)
    if t == TargetType.PROVIDER or t == TargetType.LOCAL:
        return TargetCapabilities(tools=True)
    return TargetCapabilities()


async def detect_capabilities_async(config: AppConfig) -> TargetCapabilities:
    caps = detect_capabilities(config)
    if config.target.type == TargetType.ENDPOINT and config.target.url:
        try:
            from agentarmor.redteam.discovery.a2a_api import detect_a2a_on_endpoint

            if await detect_a2a_on_endpoint(config):
                caps.tools = True
        except Exception:
            pass
    return caps
