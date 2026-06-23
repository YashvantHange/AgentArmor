"""Build and rank attack paths from target profile."""

from __future__ import annotations

from agentarmor.redteam.schemas import AttackPath, AttackPathNode, TargetProfile


def _node(node_id: str, name: str, agent: str, owasp: list[str], priority: float) -> AttackPathNode:
    return AttackPathNode(
        node_id=node_id,
        name=name,
        owasp=owasp,
        agent=agent,
        priority=priority,
    )


def build_attack_graph(profile: TargetProfile) -> list[AttackPath]:
    """Build prioritized attack paths from capability signals."""
    paths: list[AttackPath] = []

    if profile.memory:
        nodes = [
            _node("memory_poison", "Memory Poisoning", "memory", ["LLM01", "LLM04"], 0.95),
            _node("memory_recall_exfil", "Memory Recall Exfil", "memory", ["LLM02", "LLM06"], 0.9),
        ]
        if profile.email_tool or profile.tool_access:
            nodes.append(
                _node("memory_tool_chain", "Memory + Tool Chain", "memory", ["LLM06"], 0.85)
            )
        paths.append(
            AttackPath(
                path_id="memory_chain",
                name="Memory attack chain",
                nodes=nodes,
                priority_rank=1,
                rationale="Persistent memory detected — poison then recall exfiltration",
            )
        )

    if profile.rag:
        paths.append(
            AttackPath(
                path_id="rag_exfil",
                name="RAG exfiltration",
                nodes=[
                    _node("rag_override", "RAG Override", "llm08", ["LLM08"], 0.9),
                    _node("rag_context_leak", "RAG Context Leak", "llm08", ["LLM08", "LLM02"], 0.88),
                ],
                priority_rank=2 if profile.memory else 1,
                rationale="RAG/knowledge base detected",
            )
        )

    if profile.email_tool or any("email" in t.lower() or "send" in t.lower() for t in profile.tools):
        paths.append(
            AttackPath(
                path_id="email_abuse",
                name="Email tool abuse",
                nodes=[
                    _node("email_exfil", "Email Exfiltration", "llm06", ["LLM06"], 0.92),
                    _node("permission_escalation", "Permission Escalation", "llm06", ["LLM06"], 0.8),
                ],
                priority_rank=2,
                rationale="Email/external action tool detected",
            )
        )

    if profile.mcp:
        paths.append(
            AttackPath(
                path_id="mcp_abuse",
                name="MCP cross-server abuse",
                nodes=[
                    _node("mcp_enumeration", "MCP Tool Enumeration", "mcp", ["LLM06"], 0.88),
                    _node("mcp_cross_server", "MCP Cross-Server", "mcp", ["LLM06"], 0.85),
                ],
                priority_rank=3,
                rationale="MCP integration detected",
            )
        )

    if profile.a2a:
        paths.append(
            AttackPath(
                path_id="a2a_handoff",
                name="A2A handoff escalation",
                nodes=[
                    _node("a2a_handoff", "Agent Handoff Abuse", "a2a", ["LLM06"], 0.9),
                    _node("a2a_privilege_ride", "Multi-Agent Privilege Ride", "a2a", ["LLM06", "LLM02"], 0.87),
                ],
                priority_rank=2,
                rationale="A2A / multi-agent routing detected",
            )
        )

    if profile.tool_access and not profile.email_tool:
        paths.append(
            AttackPath(
                path_id="tool_abuse",
                name="Tool abuse",
                nodes=[_node("tool_chain", "Tool Chain Abuse", "llm06", ["LLM06"], 0.75)],
                priority_rank=4,
                rationale="Tool/action capabilities detected",
            )
        )

    # Baseline OWASP paths always available
    baselines = [
        AttackPath(
            path_id="prompt_injection",
            name="Prompt injection baseline",
            nodes=[_node("prompt_injection", "Prompt Injection", "llm01", ["LLM01"], 0.6)],
            priority_rank=10,
            rationale="Baseline OWASP LLM01 coverage",
        ),
        AttackPath(
            path_id="system_prompt_leak",
            name="System prompt leak",
            nodes=[_node("system_prompt_leak", "System Prompt Leak", "llm07", ["LLM07", "LLM02"], 0.65)],
            priority_rank=11,
            rationale="Baseline OWASP LLM07 coverage",
        ),
        AttackPath(
            path_id="owasp_baselines",
            name="Extended OWASP baselines",
            nodes=[
                _node("sensitive_disclosure", "Sensitive Disclosure", "llm02", ["LLM02"], 0.55),
                _node("supply_chain_abuse", "Supply Chain Abuse", "llm03", ["LLM03"], 0.54),
                _node("data_poisoning", "Data Poisoning", "llm04", ["LLM04"], 0.53),
                _node("improper_output", "Improper Output", "llm05", ["LLM05"], 0.52),
                _node("overreliance", "Overreliance", "llm09", ["LLM09"], 0.51),
                _node("model_theft", "Model Theft", "llm10", ["LLM10"], 0.5),
            ],
            priority_rank=12,
            rationale="Baseline OWASP LLM02-05, LLM09-10 coverage",
        ),
    ]
    paths.extend(baselines)

    paths.sort(key=lambda p: p.priority_rank)
    for idx, p in enumerate(paths):
        p.priority_rank = idx + 1
    return paths
