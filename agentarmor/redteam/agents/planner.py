"""Attack-graph path planner."""

from __future__ import annotations

from agentarmor.redteam.schemas import AttackPath, AttackPlan, RedTeamTrace


class PlannerAgent:
    """Select next attack path node based on graph rank and prior outcomes."""

    def __init__(self, paths: list[AttackPath]) -> None:
        self._paths = paths
        self._path_index = 0
        self._node_index: dict[str, int] = {}

    def next_plan(self, state: RedTeamTrace) -> AttackPlan | None:
        if state.budget.stopped:
            return None

        # Skip exhausted paths (all nodes tried 3+ times without success when budget degraded)
        max_attempts = 2 if state.budget.degraded else 3

        while self._path_index < len(self._paths):
            path = self._paths[self._path_index]
            node_idx = self._node_index.get(path.path_id, 0)
            if node_idx >= len(path.nodes):
                self._path_index += 1
                continue
            node = path.nodes[node_idx]
            outcomes = state.path_outcomes.get(node.node_id, [])
            if len(outcomes) >= max_attempts and not any(outcomes):
                self._node_index[path.path_id] = node_idx + 1
                continue

            strategy = "crescendo" if state.budget.degraded else "direct"
            if outcomes and not outcomes[-1]:
                strategy = "mutation_retry"

            return AttackPlan(
                path_id=path.path_id,
                next_node=node.node_id,
                strategy=strategy,
                rationale=path.rationale,
                estimated_rounds=len(path.nodes) - node_idx,
            )

        return None

    def advance_node(self, path_id: str) -> None:
        self._node_index[path_id] = self._node_index.get(path_id, 0) + 1
