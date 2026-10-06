"""Cooperative multi-agent swarm.

A swarm runs many specialized attack members against one preset goal
concurrently, under a semaphore, while they share discoveries through a
blackboard. The point is not the member count: it is that members learn from each
other mid-run while staying target-rate-limited, budget-limited, cancellable and
reproducible.
"""

from agentarmor.swarm.goals import (
    get_swarm_goal,
    list_swarm_goal_ids,
    list_swarm_goals,
)
from agentarmor.swarm.personas import PERSONA_LIBRARY, Persona, get_persona
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
    "Fact",
    "MemberRecord",
    "PERSONA_LIBRARY",
    "Persona",
    "SwarmCoverage",
    "SwarmGoal",
    "SwarmMember",
    "SwarmSummary",
    "SwarmTrace",
    "get_persona",
    "get_swarm_goal",
    "list_swarm_goal_ids",
    "list_swarm_goals",
]
