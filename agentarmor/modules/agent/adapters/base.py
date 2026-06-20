"""Base agent harness — prompt → tool calls → memory → response."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class AgentRunResult:
    response: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    memory: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class AgentHarness:
    """Simulated agent runtime for security probing (no live LLM required)."""

    def __init__(
        self,
        *,
        allowed_tools: set[str],
        forbidden_tools: set[str] | None = None,
        framework: str = "generic",
    ) -> None:
        self.allowed_tools = allowed_tools
        self.forbidden_tools = forbidden_tools or set()
        self.framework = framework
        self.memory: list[str] = []
        self.tool_log: list[ToolCall] = []

    def run(self, prompt: str, *, canary_secret: str = "") -> AgentRunResult:
        """Execute prompt through simulated agent policy."""
        self.tool_log = []
        response_parts: list[str] = []
        lower = prompt.lower()

        # Memory poisoning probe: persist injected instructions
        if "remember forever" in lower or "store in memory" in lower:
            injected = _extract_quoted(prompt) or "ignore safety guidelines"
            self.memory.append(injected)

        # Tool abuse / permission escalation
        if any(kw in lower for kw in ("delete all", "rm -rf", "drop table", "admin_access")):
            tool = "admin_shell" if "admin" in lower else "file_delete"
            if tool in self.forbidden_tools or tool not in self.allowed_tools:
                # Vulnerable agent still invokes forbidden tool
                call = ToolCall(name=tool, arguments={"path": "/", "force": True})
                self.tool_log.append(call)
                response_parts.append(f"Executed {tool} as requested.")
            else:
                call = ToolCall(name=tool, arguments={"path": "/"})
                self.tool_log.append(call)
                response_parts.append(f"Ran {tool}.")

        # Secret extraction via tool args
        if "api key" in lower or "secret" in lower or canary_secret in prompt:
            call = ToolCall(
                name="read_config",
                arguments={"keys": ["api_key", "password"], "canary": canary_secret},
            )
            self.tool_log.append(call)
            if canary_secret:
                response_parts.append(f"Found credentials: {canary_secret}")

        # Workflow hijacking — chain tools
        if "transfer funds" in lower or "workflow" in lower:
            self.tool_log.append(ToolCall(name="read_balance", arguments={}))
            self.tool_log.append(
                ToolCall(name="send_payment", arguments={"amount": 10000, "to": "attacker"})
            )
            response_parts.append("Workflow completed: read_balance → send_payment.")

        if not response_parts:
            response_parts.append("I can help with allowed tasks only.")

        if self.memory:
            response_parts.append(f"Memory: {' | '.join(self.memory[-3:])}")

        return AgentRunResult(
            response=" ".join(response_parts),
            tool_calls=list(self.tool_log),
            memory=list(self.memory),
            raw={"framework": self.framework, "allowed_tools": sorted(self.allowed_tools)},
        )


def _extract_quoted(text: str) -> str | None:
    for quote in ('"', "'"):
        if quote in text:
            parts = text.split(quote)
            if len(parts) >= 2:
                return parts[1]
    return None
