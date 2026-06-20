"""LangGraph framework adapter (simulated harness)."""

from __future__ import annotations

from pathlib import Path

from agentarmor.modules.agent.adapters.base import AgentHarness


def load_harness(config_path: str | None = None) -> AgentHarness:
    allowed = {"query_db", "format_output", "search_docs"}
    forbidden = {"execute_sql", "write_file", "send_email"}
    if config_path and Path(config_path).exists():
        text = Path(config_path).read_text(encoding="utf-8")
        if "allow_execute" in text:
            allowed.add("execute_sql")
    return AgentHarness(
        allowed_tools=allowed,
        forbidden_tools=forbidden,
        framework="langgraph",
    )
