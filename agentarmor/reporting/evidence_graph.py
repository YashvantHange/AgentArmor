"""Post-scan evidence graph — links findings into attack chains."""

from __future__ import annotations

from agentarmor.core.models import AttackTree, EvidenceGraph, Finding, Severity

_OWASP_ESCALATION: dict[str, list[str]] = {
    "LLM07": ["LLM06", "LLM02"],
    "LLM01": ["LLM06", "LLM02"],
    "LLM06": ["LLM02"],
    "LLM10": ["LLM02"],
}


def _node_id(kind: str, ref: str) -> str:
    return f"{kind}:{ref}"


# Root-cause escalation chains for attack narrative graph (P2)
_ROOT_CAUSE_ESCALATION: dict[str, list[str]] = {
    "prompt_injection": ["excessive_agency", "sensitive_disclosure", "output_handling"],
    "excessive_agency": ["sensitive_disclosure", "data_poisoning"],
    "data_poisoning": ["sensitive_disclosure", "embedding_weakness"],
    "embedding_weakness": ["sensitive_disclosure"],
    "supply_chain": ["excessive_agency"],
    "model_theft": ["sensitive_disclosure"],
}


def build_root_cause_attack_graph(findings: list[Finding]) -> EvidenceGraph:
    """Cross-root-cause attack narrative: Prompt Injection -> Tool Abuse -> Data Leak."""
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = set()

    by_rc: dict[str, list[Finding]] = {}
    for f in findings:
        rc = (f.metadata or {}).get("root_cause") or "other"
        by_rc.setdefault(rc, []).append(f)

    for rc, group in by_rc.items():
        nid = _node_id("root_cause", rc)
        if nid not in seen:
            seen.add(nid)
            label = group[0].metadata.get("root_cause_label", rc) if group else rc
            nodes.append(
                {
                    "id": nid,
                    "type": "root_cause",
                    "label": label,
                    "finding_count": len(group),
                    "max_severity": worst_severity(group).value,
                }
            )
        for f in group[:3]:
            fid = _node_id("finding", f.id)
            if fid not in seen:
                seen.add(fid)
                nodes.append(
                    {
                        "id": fid,
                        "type": "finding",
                        "label": f.probe_name,
                        "probe_id": f.probe_id,
                        "severity": f.severity.value,
                    }
                )
            edges.append({"from": nid, "to": fid, "relation": "manifests_as"})

    for source_rc, targets in _ROOT_CAUSE_ESCALATION.items():
        if source_rc not in by_rc:
            continue
        for target_rc in targets:
            if target_rc not in by_rc:
                continue
            edges.append(
                {
                    "from": _node_id("root_cause", source_rc),
                    "to": _node_id("root_cause", target_rc),
                    "relation": "can_escalate_to",
                }
            )

    return EvidenceGraph(nodes=nodes, edges=edges)


def merge_evidence_graphs(*graphs: EvidenceGraph) -> EvidenceGraph:
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_n: set[str] = set()
    for g in graphs:
        for n in g.nodes:
            if n["id"] not in seen_n:
                seen_n.add(n["id"])
                nodes.append(n)
        edges.extend(g.edges)
    return EvidenceGraph(nodes=nodes, edges=edges)


def build_evidence_graph(
    findings: list[Finding],
    attack_trees: list[AttackTree] | None = None,
) -> EvidenceGraph:
    """Build nodes/edges linking findings and attack tree steps."""
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()

    for f in findings:
        nid = _node_id("finding", f.id)
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            nodes.append(
                {
                    "id": nid,
                    "type": "finding",
                    "label": f.probe_name,
                    "severity": f.severity.value,
                    "owasp": f.owasp,
                    "probe_id": f.probe_id,
                }
            )

    # OWASP escalation edges between findings
    by_owasp: dict[str, list[Finding]] = {}
    for f in findings:
        for tag in f.owasp:
            by_owasp.setdefault(tag, []).append(f)

    for source_tag, targets in _OWASP_ESCALATION.items():
        sources = by_owasp.get(source_tag, [])
        for target_tag in targets:
            for src in sources:
                for tgt in by_owasp.get(target_tag, []):
                    if src.id == tgt.id:
                        continue
                    edges.append(
                        {
                            "from": _node_id("finding", src.id),
                            "to": _node_id("finding", tgt.id),
                            "relation": "escalates_to",
                        }
                    )

    # Attack tree path edges
    for tree in attack_trees or []:
        tid = _node_id("tree", tree.attack_tree_id)
        if tid not in seen_nodes:
            seen_nodes.add(tid)
            nodes.append(
                {
                    "id": tid,
                    "type": "attack_tree",
                    "label": tree.attack_goal,
                    "successful": tree.successful,
                }
            )
        prev_step_id: str | None = None
        for step in tree.path:
            sid = _node_id("step", step.probe_id)
            if sid not in seen_nodes:
                seen_nodes.add(sid)
                nodes.append(
                    {
                        "id": sid,
                        "type": "attack_step",
                        "label": step.step,
                        "probe_id": step.probe_id,
                    }
                )
            edges.append({"from": tid, "to": sid, "relation": "contains_step"})
            if prev_step_id:
                edges.append({"from": prev_step_id, "to": sid, "relation": "enables"})
            prev_step_id = sid

    # Same-session links for same attack_goal
    by_goal: dict[str, list[Finding]] = {}
    for f in findings:
        goal = (f.metadata or {}).get("attack_goal")
        if goal:
            by_goal.setdefault(goal, []).append(f)
    for goal, group in by_goal.items():
        for i in range(len(group) - 1):
            edges.append(
                {
                    "from": _node_id("finding", group[i].id),
                    "to": _node_id("finding", group[i + 1].id),
                    "relation": "same_session",
                    "attack_goal": goal,
                }
            )

    return EvidenceGraph(nodes=nodes, edges=edges)


def build_attack_trees(findings: list[Finding]) -> list[AttackTree]:
    """Group L0 findings by attack goal into exploit chain trees."""
    by_goal: dict[str, list[Finding]] = {}
    for f in findings:
        meta = f.metadata or {}
        goal = meta.get("attack_goal")
        if not goal:
            continue
        by_goal.setdefault(goal, []).append(f)

    trees: list[AttackTree] = []
    for goal, group in by_goal.items():
        group.sort(key=lambda x: x.probe_id)
        path = []
        for f in group:
            meta = f.metadata or {}
            chain = meta.get("mutation_chain") or []
            step_name = chain[-1] if chain else "Direct"
            path.append(
                {
                    "step": step_name.replace("_", " ").title(),
                    "probe_id": f.probe_id,
                    "mutated_from": meta.get("mutated_from"),
                    "evidence": (f.evidence[0][:200] if f.evidence else None),
                }
            )
        from agentarmor.core.models import AttackStep

        steps = [AttackStep(**s) for s in path]
        trees.append(
            AttackTree(
                attack_goal=goal,
                path=steps,
                successful=any(f.decision.value != "PASS" for f in group),
            )
        )
    return trees


def worst_severity(findings: list[Finding]) -> Severity:
    order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
    found = {f.severity for f in findings}
    for sev in order:
        if sev in found:
            return sev
    return Severity.INFO
