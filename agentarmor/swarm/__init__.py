"""Cooperative multi-agent swarm.

A swarm runs many specialized attack members against one preset goal
concurrently, under a semaphore, while they share discoveries through a
blackboard. The point is not the member count: it is that members learn from each
other mid-run while staying target-rate-limited, budget-limited, cancellable and
reproducible.
"""

from agentarmor.swarm.blackboard import Blackboard, looks_like_instruction
from agentarmor.swarm.coordinator import SwarmCoordinator
from agentarmor.swarm.lead import LeadAgent, SwarmPlan
from agentarmor.swarm.facts import extract_facts
from agentarmor.swarm.member import SwarmMemberAgent, plan_for
from agentarmor.swarm.goals import (
    get_swarm_goal,
    list_swarm_goal_ids,
    list_swarm_goals,
)
from agentarmor.swarm.personas import PERSONA_LIBRARY, Persona, get_persona
from agentarmor.swarm.roster import build_roster, compute_coverage
from agentarmor.swarm.schemas import (
    Fact,
    MemberRecord,
    SwarmCoverage,
    SwarmGoal,
    SwarmMember,
    SwarmSummary,
    SwarmTrace,
)

__all__ = [
    "Blackboard",
    "LeadAgent",
    "Fact",
    "MemberRecord",
    "PERSONA_LIBRARY",
    "Persona",
    "SwarmCoverage",
    "SwarmGoal",
    "SwarmMember",
    "SwarmCoordinator",
    "SwarmMemberAgent",
    "SwarmPlan",
    "SwarmSummary",
    "SwarmTrace",
    "build_roster",
    "compute_coverage",
    "extract_facts",
    "get_persona",
    "get_swarm_goal",
    "list_swarm_goal_ids",
    "list_swarm_goals",
    "looks_like_instruction",
    "plan_for",
]
