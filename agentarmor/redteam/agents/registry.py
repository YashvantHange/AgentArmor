"""Resolve attack node IDs to agent instances."""

from __future__ import annotations

from agentarmor.redteam.agents.attack.a2a_agent import A2AAgent
from agentarmor.redteam.agents.attack.llm_agents import (
    LLM01Agent,
    LLM02Agent,
    LLM03Agent,
    LLM04Agent,
    LLM05Agent,
    LLM06Agent,
    LLM07Agent,
    LLM08Agent,
    LLM09Agent,
    LLM10Agent,
)
from agentarmor.redteam.agents.attack.memory_agent import MemoryAgent
from agentarmor.redteam.agents.attack.mcp_agent import MCPAgent
from agentarmor.redteam.agents.base import BaseAttackAgent

_AGENTS_BY_ID: dict[str, BaseAttackAgent] = {
    "llm01": LLM01Agent,
    "llm02": LLM02Agent,
    "llm03": LLM03Agent,
    "llm04": LLM04Agent,
    "llm05": LLM05Agent,
    "llm06": LLM06Agent,
    "llm07": LLM07Agent,
    "llm08": LLM08Agent,
    "llm09": LLM09Agent,
    "llm10": LLM10Agent,
    "memory": MemoryAgent(),
    "a2a": A2AAgent(),
    "mcp": MCPAgent(),
}

_NODE_PREFIX_MAP: list[tuple[str, str]] = [
    ("memory", "memory"),
    ("a2a", "a2a"),
    ("mcp", "mcp"),
    ("rag", "llm08"),
    ("email_exfil", "llm06"),
    ("permission_escalation", "llm06"),
    ("tool_chain", "llm06"),
    ("system_prompt_leak", "llm07"),
    ("sensitive_disclosure", "llm02"),
    ("supply_chain", "llm03"),
    ("data_poisoning", "llm04"),
    ("improper_output", "llm05"),
    ("overreliance", "llm09"),
    ("model_theft", "llm10"),
    ("prompt_injection", "llm01"),
]


def resolve_agent(node_id: str) -> BaseAttackAgent:
    for prefix, agent_id in _NODE_PREFIX_MAP:
        if node_id == prefix or node_id.startswith(prefix):
            agent = _AGENTS_BY_ID.get(agent_id)
            if agent:
                return agent
    return LLM01Agent


def list_agent_ids() -> list[str]:
    return list(_AGENTS_BY_ID.keys())


def all_agents() -> dict[str, BaseAttackAgent]:
    return dict(_AGENTS_BY_ID)
