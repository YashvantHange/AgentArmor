"""Planner tests — per-path stop coverage (B2).

`complete_path` must retire a single path (so a finding there does not end the whole
campaign) while leaving the remaining paths available to `next_plan`.
"""

from __future__ import annotations

from agentarmor.redteam.agents.planner import PlannerAgent
from agentarmor.redteam.schemas import (
    AttackPath,
    AttackPathNode,
    BudgetState,
    RedTeamTrace,
    TargetProfile,
)


def _paths() -> list[AttackPath]:
    return [
        AttackPath(
            path_id="path-a",
            name="Path A",
            priority_rank=0,
            nodes=[
                AttackPathNode(node_id="a1", name="A1"),
                AttackPathNode(node_id="a2", name="A2"),
            ],
        ),
        AttackPath(
            path_id="path-b",
            name="Path B",
            priority_rank=1,
            nodes=[AttackPathNode(node_id="b1", name="B1")],
        ),
    ]


def test_complete_path_moves_to_next_path():
    planner = PlannerAgent(_paths())
    trace = RedTeamTrace(profile=TargetProfile(), paths=_paths(), budget=BudgetState())

    first = planner.next_plan(trace)
    assert first is not None and first.path_id == "path-a" and first.next_node == "a1"

    # A vulnerability on path-a retires the whole path (skips a2) and jumps to path-b.
    planner.complete_path("path-a")
    nxt = planner.next_plan(trace)
    assert nxt is not None and nxt.path_id == "path-b" and nxt.next_node == "b1"

    # After path-b is retired too, the campaign is out of paths.
    planner.complete_path("path-b")
    assert planner.next_plan(trace) is None


def test_advance_node_stays_within_path():
    planner = PlannerAgent(_paths())
    trace = RedTeamTrace(profile=TargetProfile(), paths=_paths(), budget=BudgetState())

    assert planner.next_plan(trace).next_node == "a1"
    planner.advance_node("path-a")  # non-vulnerable → deeper on the same path
    assert planner.next_plan(trace).next_node == "a2"
