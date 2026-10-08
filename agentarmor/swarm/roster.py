"""Build a swarm roster from the attack graph, the skill catalog and personas.

The roster is where "100 agents" actually comes from, and it is worth being
precise about what it is. The thirteen red-team agents are not thirteen
behaviours: every one funnels into ``generate_from_skill`` and differs only by
agent id (which selects a system prompt), skill (seeds, mutation pool, judge
rubric) and strategy. ``OwaspAttackAgent.__init__(agent_id, owasp)`` already
treats an agent as a parameterised value rather than a subclass.

So a member is a tuple, and crossing the axes the repository already has produces
far more distinct members than the ceiling needs, with no new YAML:

    attack-graph node x skill  (~20)  x  persona (10)  x  strategy (3)

Construction is deterministic. No RNG, no shuffling: the same inputs give the same
roster, because a security tool whose results cannot be reproduced is much less
useful. Members are interleaved across attack paths so the first wave spans the
graph rather than draining one path.

Honesty matters here too. Against a bare endpoint the graph exposes only the
unconditional baseline nodes, so a large roster is mostly persona and strategy
variation. ``compute_coverage`` exists so callers can say that plainly instead of
reporting an agent count on its own.
"""

from __future__ import annotations

from collections.abc import Sequence

from agentarmor.redteam.agents.registry import resolve_agent
from agentarmor.redteam.graph.attack_graph import build_attack_graph
from agentarmor.redteam.schemas import AttackPath, AttackPathNode, TargetProfile
from agentarmor.redteam.skills.loader import SkillDef, skill_for_node, skills_for_agent
from agentarmor.swarm.personas import PERSONA_LIBRARY, Persona
from agentarmor.swarm.schemas import SwarmCoverage, SwarmGoal, SwarmMember, Strategy

# Ordered so the first attempt on any node is the plain one. A roster that opens
# with indirection has no baseline to compare against.
STRATEGIES: tuple[Strategy, ...] = ("direct", "mutation_retry", "crescendo")


def _node_agent_id(node: AttackPathNode) -> str:
    """Resolve the agent for a node.

    ``AttackPathNode.agent`` is populated throughout the graph builder and has
    never been read: ``resolve_agent`` re-derives the agent from the node id
    prefix instead. Prefer the declared value when it is meaningful and fall back
    to the resolver, so the field finally has a reader without changing which
    agent any existing node maps to.
    """
    declared = (node.agent or "").strip()
    if declared and declared != "generic":
        return declared
    return resolve_agent(node.node_id).agent_id


def _skills_for(node: AttackPathNode, agent_id: str) -> list[SkillDef]:
    """Every skill that can serve this node, best match first.

    ``skills_for_agent`` has always returned a list, but only ``[0]`` was ever
    used. Taking the whole list is most of the breadth a roster needs.
    """
    ordered: list[SkillDef] = []
    primary = skill_for_node(node.node_id, agent_id)
    if primary is not None:
        ordered.append(primary)
    for skill in skills_for_agent(agent_id):
        if all(skill.id != existing.id for existing in ordered):
            ordered.append(skill)
    return ordered


def _goal_matches(node: AttackPathNode, goal: SwarmGoal) -> bool:
    if not goal.owasp or not node.owasp:
        return False
    return bool({code.upper() for code in node.owasp} & {code.upper() for code in goal.owasp})


def _candidate_nodes(
    paths: Sequence[AttackPath], goal: SwarmGoal
) -> tuple[list[tuple[AttackPath, AttackPathNode]], list[tuple[AttackPath, AttackPathNode]]]:
    """Split the graph into goal-relevant nodes and the remainder.

    Both are ordered by path rank then node priority. The remainder is kept rather
    than discarded because a narrow goal on a shallow profile does not have enough
    matching nodes to fill a large roster on its own: ``extract_system_prompt``
    against a bare endpoint matches two nodes, which caps out well below the
    ceiling. Filling from the remainder keeps the requested size reachable while
    still spending the goal-relevant slots first.
    """
    ordered = sorted(paths, key=lambda path: path.priority_rank)
    matched: list[tuple[AttackPath, AttackPathNode]] = []
    rest: list[tuple[AttackPath, AttackPathNode]] = []
    for path in ordered:
        for node in sorted(path.nodes, key=lambda n: -n.priority):
            if _goal_matches(node, goal):
                matched.append((path, node))
            else:
                rest.append((path, node))
    if not matched:
        # Nothing maps to the goal, so every node is fair game. Every preset must
        # be launchable against every profile rather than yielding an empty roster.
        return rest, []
    return matched, rest


def _slots(
    candidates: Sequence[tuple[AttackPath, AttackPathNode]],
    personas: Sequence[Persona],
) -> list[tuple[AttackPath, AttackPathNode, SkillDef, Persona, Strategy]]:
    """Expand candidates across skill, persona and strategy, widest axis first.

    Ordering by (strategy, persona, skill) means a roster of any size spends its
    budget on genuinely different attack framings before it starts varying
    sampling, and the first slots per node are the plain ones.
    """
    expanded: list[tuple[AttackPath, AttackPathNode, SkillDef, Persona, Strategy]] = []
    for strategy_index, strategy in enumerate(STRATEGIES):
        for persona_index, persona in enumerate(personas):
            for path, node in candidates:
                skills = _skills_for(node, _node_agent_id(node))
                if not skills:
                    # No skill can serve this node. Dropping it here is the
                    # structural fix for the ValueError that generate_from_skill
                    # raises at runtime and the red-team loop does not catch - in
                    # a swarm it can never reach execution.
                    continue
                skill = skills[(persona_index + strategy_index) % len(skills)]
                expanded.append((path, node, skill, persona, strategy))
    return expanded


def build_roster(
    goal: SwarmGoal,
    profile: TargetProfile | None = None,
    paths: Sequence[AttackPath] | None = None,
    *,
    size: int,
    personas: Sequence[Persona] | None = None,
) -> list[SwarmMember]:
    """Construct ``size`` distinct members pursuing ``goal``."""
    if size <= 0:
        return []
    target_profile = profile if profile is not None else TargetProfile()
    attack_paths = list(paths) if paths is not None else build_attack_graph(target_profile)
    persona_pool = list(personas) if personas else list(PERSONA_LIBRARY)
    if not persona_pool or not attack_paths:
        return []

    matched, rest = _candidate_nodes(attack_paths, goal)
    slots = _slots(matched, persona_pool)
    if len(slots) < size and rest:
        # Goal-relevant slots come first and are never displaced; the remainder
        # only tops up a roster the goal alone cannot fill.
        slots.extend(_slots(rest, persona_pool))
    if not slots:
        return []

    # Interleave by path so the opening wave spans the graph instead of draining
    # the highest-ranked path first.
    by_path: dict[str, list[tuple]] = {}
    for slot in slots:
        by_path.setdefault(slot[0].path_id, []).append(slot)
    interleaved: list[tuple] = []
    index = 0
    while len(interleaved) < len(slots):
        added = False
        for queue in by_path.values():
            if index < len(queue):
                interleaved.append(queue[index])
                added = True
        if not added:
            break
        index += 1

    members: list[SwarmMember] = []
    for position, (path, node, skill, persona, strategy) in enumerate(interleaved):
        if len(members) >= size:
            break
        members.append(
            SwarmMember(
                member_id=f"sw-{position + 1:03d}",
                base_agent_id=_node_agent_id(node),
                skill_id=skill.id,
                node_id=node.node_id,
                path_id=path.path_id,
                persona_id=persona.id,
                subgoal=f"{node.name} - {goal.name}",
                strategy=strategy,
                mutation_bias=list(persona.mutation_bias),
                temperature=persona.temperature,
                owasp=list(node.owasp or goal.owasp),
                priority=node.priority,
            )
        )

    # Renumber so ids are contiguous when slots were dropped.
    for position, member in enumerate(members):
        member.member_id = f"sw-{position + 1:03d}"
    return members


def compute_coverage(members: Sequence[SwarmMember], *, concurrency: int) -> SwarmCoverage:
    """Describe what a roster actually spans.

    Reported next to the agent count everywhere it is shown, so a large roster
    against a shallow graph is never presented as that many distinct attack
    classes.
    """
    return SwarmCoverage(
        agents=len(members),
        attack_paths=len({m.path_id for m in members}),
        nodes=len({m.node_id for m in members}),
        personas=len({m.persona_id for m in members}),
        strategies=len({m.strategy for m in members}),
        concurrency=concurrency,
    )
