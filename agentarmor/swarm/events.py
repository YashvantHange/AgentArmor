"""Swarm event names.

``ScanEvent.event`` is a free-form string, so these are constants rather than an
enum the bus knows about - adding a name costs nothing on the backend. The GUI is
the constrained side: ``useScanEvents`` subscribes to an explicit allowlist, so an
unlisted name is silently dropped there.

Volume is a design concern. A 100-member run emits roughly:

    plan 1 + roster 1 (batched) + agent.started 100 + agent.completed 100
    + blackboard.fact <= max_facts + progress ~1/s + completed 1 + scan.completed 1

which is a few hundred events, not a few thousand. That is why the roster ships as
one event instead of one per member, progress is coalesced rather than emitted per
state change, and only *new* facts are announced.
"""

from __future__ import annotations

SWARM_PLAN = "swarm.plan"
SWARM_ROSTER = "swarm.roster"
AGENT_STARTED = "agent.started"
AGENT_COMPLETED = "agent.completed"
AGENT_FAILED = "agent.failed"
AGENT_SKIPPED = "agent.skipped"
BLACKBOARD_FACT = "blackboard.fact"
SWARM_PROGRESS = "swarm.progress"
SWARM_COMPLETED = "swarm.completed"

# Every event name the swarm emits, for the GUI allowlist and for tests.
SWARM_EVENT_NAMES: tuple[str, ...] = (
    SWARM_PLAN,
    SWARM_ROSTER,
    AGENT_STARTED,
    AGENT_COMPLETED,
    AGENT_FAILED,
    AGENT_SKIPPED,
    BLACKBOARD_FACT,
    SWARM_PROGRESS,
    SWARM_COMPLETED,
)

# Minimum gap between swarm.progress events, in seconds. Progress is derived state
# that the GUI recomputes anyway, so emitting it per member would be noise.
PROGRESS_INTERVAL_S = 1.0
