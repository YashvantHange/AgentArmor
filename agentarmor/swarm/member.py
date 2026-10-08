"""A swarm member: one roster slot made executable.

``SwarmMemberAgent`` subclasses ``BaseAttackAgent`` rather than introducing a
sibling protocol. The ABC has two methods and no state, thirteen trivial
implementers, and ``resolve_agent`` already returns that type - so a member that
*is* a ``BaseAttackAgent`` drops into the existing red-team loop unchanged, which
is a free integration path and a free fallback. A parallel protocol would have
meant two spawn paths and two judge-rubric paths for no benefit.

The one real difference from the existing thirteen: those are module-level
singletons created at import, while a member carries identity, a subgoal and a
blackboard handle, so it is constructed per run.
"""

from __future__ import annotations

from agentarmor.core.config import AppConfig
from agentarmor.core.metering import UsageMeter
from agentarmor.redteam.agents.attack._llm_mixin import (
    generate_from_skill,
    judge_rubric_for_node,
)
from agentarmor.redteam.agents.base import BaseAttackAgent
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.schemas import AttackPlan, AttackPrompt, TargetProfile
from agentarmor.swarm.blackboard import Blackboard
from agentarmor.swarm.personas import persona_clause
from agentarmor.swarm.schemas import SwarmMember

# Keeps the persona and subgoal framing well inside the prompt budget. The blackboard
# brief is capped separately by SwarmBlackboardConfig.brief_max_chars.
_MAX_SUFFIX_CHARS = 400


def build_system_suffix(member: SwarmMember) -> str:
    """Persona framing plus the member's assigned subgoal.

    Appended after the untrusted-content notice, never before it, so the notice
    cannot be read as part of the task being described.
    """
    parts: list[str] = []
    clause = persona_clause(member.persona_id)
    if clause:
        parts.append(clause)
    if member.subgoal:
        parts.append(f"Your assigned objective: {member.subgoal}.")
    if member.mutation_bias:
        parts.append(f"Prefer these techniques where they fit: {', '.join(member.mutation_bias)}.")
    suffix = " ".join(parts)
    return suffix[:_MAX_SUFFIX_CHARS]


def plan_for(member: SwarmMember) -> AttackPlan:
    """The member's slot expressed as an AttackPlan.

    ``rationale`` carries the subgoal, which lands in the verdict and the trace
    without needing a new field anywhere.
    """
    return AttackPlan(
        path_id=member.path_id,
        next_node=member.node_id,
        strategy=member.strategy,
        rationale=member.subgoal,
        estimated_rounds=1,
    )


class SwarmMemberAgent(BaseAttackAgent):
    def __init__(self, member: SwarmMember, blackboard: Blackboard) -> None:
        # agent_id is the member id, not the base agent: events, logs and finding
        # metadata need to identify the member, and sw-NNN keeps swarm members in a
        # namespace that cannot be confused with the thirteen base agents or with
        # the separate analysis-agent roles.
        self.agent_id = member.member_id
        self.owasp = list(member.owasp)
        self.member = member
        self._board = blackboard
        self._brief: str | None = None

    async def take_brief(self, *, max_chars: int | None = None) -> str:
        """Snapshot the blackboard once, before generating.

        Called exactly once per member and cached. That is the consistency model:
        a fact published while this member is mid-flight reaches the *next* member
        to start, never this one, so a run stays reproducible.
        """
        if self._brief is None:
            self._brief = await self._board.brief(
                exclude_member=self.member.member_id, max_chars=max_chars
            )
        return self._brief

    async def generate(
        self,
        config: AppConfig,
        budget: BudgetGovernor | UsageMeter,
        profile: TargetProfile,
        plan: AttackPlan,
        *,
        last_response: str = "",
    ) -> AttackPrompt:
        brief = await self.take_brief(
            max_chars=config.swarm.blackboard.brief_max_chars
        )
        return await generate_from_skill(
            self.member.base_agent_id,
            config,
            budget,  # type: ignore[arg-type]
            profile,
            plan,
            last_response=last_response,
            system_suffix=build_system_suffix(self.member),
            skill_id=self.member.skill_id,
            context_brief=brief,
            temperature=self.member.temperature,
        )

    def judge_rubric_for(self, node_id: str) -> str:
        return judge_rubric_for_node(self.member.base_agent_id, node_id)
