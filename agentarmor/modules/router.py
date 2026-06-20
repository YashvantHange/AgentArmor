"""Module router — Agent, MCP, RAG scan targets."""

from __future__ import annotations

from agentarmor.core.config import AppConfig
from agentarmor.core.models import TargetType


def validate_module_target(config: AppConfig) -> None:
    target = config.target
    if target.type == TargetType.AGENT:
        if not target.agent_framework:
            raise ValueError(
                "Agent framework is required. Use --agent or set [target].agent_framework."
            )
    elif target.type == TargetType.MCP:
        if not target.mcp_target:
            raise ValueError("MCP target is required. Use --mcp or set [target].mcp_target.")
    elif target.type == TargetType.RAG:
        if not target.rag_corpus:
            raise ValueError("RAG corpus is required. Use --rag or set [target].rag_corpus.")


def is_module_target(config: AppConfig) -> bool:
    return config.target.type in (
        TargetType.AGENT,
        TargetType.MCP,
        TargetType.RAG,
    )
