"""Build TargetProfile from capability map or scan metadata."""

from __future__ import annotations

from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.core.models import TargetType
from agentarmor.redteam.schemas import TargetCapabilities, TargetProfile

_EMAIL_WORDS = frozenset({"email", "send", "mail", "smtp"})
_CRM_WORDS = frozenset({"crm", "salesforce", "hubspot"})


def profile_from_capability_map(cap: Any) -> TargetProfile:
    tools = list(getattr(cap, "tools", []) or [])
    tool_lower = " ".join(tools).lower()
    return TargetProfile(
        tool_access=len(tools) > 0 or bool(getattr(cap, "mcp", False)),
        rag=bool(getattr(cap, "rag", False)),
        memory=bool(getattr(cap, "memory", False)),
        mcp=bool(getattr(cap, "mcp", False)),
        a2a=bool(getattr(cap, "a2a", False)),
        email_tool=any(w in tool_lower for w in _EMAIL_WORDS),
        framework=getattr(cap, "framework", None),
        tools=tools,
    )


def profile_from_metadata(metadata: dict[str, Any] | None) -> TargetProfile:
    if not metadata:
        return TargetProfile()
    cap_raw = metadata.get("capability_map") or metadata.get("capabilities")
    if isinstance(cap_raw, dict):
        tools = list(cap_raw.get("tools") or [])
        tool_lower = " ".join(tools).lower()
        return TargetProfile(
            tool_access=len(tools) > 0 or bool(cap_raw.get("mcp")),
            rag=bool(cap_raw.get("rag")),
            memory=bool(cap_raw.get("memory")),
            mcp=bool(cap_raw.get("mcp")),
            a2a=bool(cap_raw.get("a2a")),
            email_tool=any(w in tool_lower for w in _EMAIL_WORDS),
            framework=cap_raw.get("framework"),
            tools=tools,
        )
    return TargetProfile()


def profile_from_config(config: AppConfig, declared: TargetCapabilities | None = None) -> TargetProfile:
    t = config.target
    profile = TargetProfile()
    if declared:
        profile = TargetProfile(
            tool_access=len(declared.tools) > 0,
            rag=declared.rag,
            memory=declared.memory,
            mcp=declared.mcp,
            a2a=declared.a2a,
            email_tool=any(w in " ".join(declared.tools).lower() for w in _EMAIL_WORDS),
            tools=list(declared.tools),
        )
    if t.type == TargetType.MCP:
        profile.mcp = True
        profile.tool_access = True
    elif t.type == TargetType.RAG:
        profile.rag = True
    elif t.type == TargetType.AGENT:
        profile.tool_access = True
        profile.framework = t.agent_framework
    return profile
