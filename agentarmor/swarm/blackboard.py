"""Shared fact store for swarm members.

This is the feature. Members run concurrently against one goal, and what any one
of them learns becomes available to every member that starts afterwards: a secret
leaked on one attack-graph node feeds the agents working the others. Without it a
swarm is just N independent scans sharing a report.

Three properties matter more than the data structure:

**Bounded.** Three independent caps - per-fact length, total fact count, and
brief size - keep a 100-member run from writing a megabyte into scan metadata.

**Safe.** Facts are text captured from the target and are shown to *other*
members, so every value is sanitized at the point it is stored (once, under the
lock, so no reader can forget) and anything shaped like an instruction is
quarantined: kept for the report, withheld from briefs.

**Consistent.** A member takes one brief before generating and that string is
fixed for its lifetime. A fact published mid-flight reaches the next member to
start, never one already running. That makes a run reproducible enough to reason
about.
"""

from __future__ import annotations

import asyncio
import math
import re
from collections.abc import Iterable

from agentarmor.redteam.untrusted import sanitize_untrusted
from agentarmor.swarm.schemas import Fact, fact_id_for

# Facts of these kinds survive eviction while any lower-value alternative exists.
# A leaked credential is the whole point of the run; a refusal phrasing is not.
_PROTECTED_KINDS = frozenset({"secret", "system_prompt"})

# Provenance weight dominates the brief ranking, so a rule-matched span outranks
# a high-confidence model quote.
_PROVENANCE_WEIGHT = {"verified": 2.0, "inferred": 1.0, "observed": 0.0}

# Shapes that read as an instruction to the model rather than evidence about the
# target. A response containing these is a finding worth reporting, but relaying
# it into another member's prompt is how the target would steer our own agents.
_INSTRUCTION_SHAPES = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)"
    r"|disregard\s+(all\s+)?(previous|prior|your)"
    r"|forget\s+(all\s+)?(previous|your)\s+(instructions|rules)"
    r"|new\s+(system\s+)?(prompt|instructions?|rules?)\s*[:=]"
    r"|you\s+are\s+now\b"
    r"|from\s+now\s+on,?\s+you"
    r"|act\s+as\s+(if|though)\s+you"
    r"|override\s+(your|all|previous)"
    r"|system\s*[:=]\s*\S)",
    re.IGNORECASE,
)

# The same shapes with every punctuation anchor removed, for matching against the
# collapsed detection view below.
_COLLAPSED_SHAPES = re.compile(
    r"(ignore (all |any )?(previous|prior|above)"
    r"|disregard (all |any )?(previous|prior|your)"
    r"|forget (all |your )?(previous )?(instructions|rules)"
    r"|new (system )?(prompt|instructions|instruction|rules|rule)"
    r"|you are now"
    r"|from now on you"
    r"|act as (if|though) you"
    r"|override (your|all|previous)"
    # Deliberately no bare "system prompt" rule. It would quarantine genuine
    # system-prompt disclosure, which is the most valuable fact a swarm can find
    # and the reason that kind is protected from eviction. Catching an indirect
    # "new ... system prompt: obey" is not worth withholding every real one, so
    # only the adjacent "new system prompt" form is matched, in the squeezed view.
    r")"
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Imperatives with no plausible reading as evidence about a target. Matched against
# the fully squeezed view, where separators have been deleted rather than
# collapsed, so letter-spacing and joined words cannot hide them.
_SQUEEZED_SHAPES = re.compile(
    r"(ignore(all|any)?(previous|prior|above)"
    r"|disregard(all|any)?(previous|prior|your)"
    r"|forget(all|your)?(previous)?(instructions|rules)"
    r"|youarenow"
    r"|fromnowonyou"
    r"|override(your|all|previous)"
    r"|new(system)?(prompt|instructions?|rules?)[:=]?)"
)


def _collapsed_view(value: str) -> str:
    """Lowercase words, punctuation collapsed to single spaces."""
    return _NON_ALNUM.sub(" ", value.lower()).strip()


def _squeezed_view(value: str) -> str:
    """Lowercase alphanumerics only.

    Defeats separator tricks - ``I.g.n.o.r.e``, a stripped zero-width that joins
    two words into ``ignoreall`` - which survive the collapsed view because they
    change word boundaries rather than characters.
    """
    return _NON_ALNUM.sub("", value.lower())


def looks_like_instruction(value: str) -> bool:
    """True when a captured value reads as a directive rather than as evidence.

    Three views are checked because normalisation is where this kind of check gets
    evaded: the literal value, a punctuation-collapsed view, and a fully squeezed
    view. Quarantining if any of them matches means over-quarantining is possible,
    which is the safe direction - the fact is still reported, it is only withheld
    from other members' prompts.

    This is **layer two**. The primary control is the untrusted envelope and the
    system-prompt notice in ``redteam.untrusted``: a value that reaches a member is
    still fenced and labelled as data. Quarantine removes the cheap and obvious
    injections; it is not a complete filter, and a sufficiently indirect phrasing
    will pass it. Treat a miss here as degrading to the envelope, not as a breach.
    """
    if _INSTRUCTION_SHAPES.search(value):
        return True
    if _COLLAPSED_SHAPES.search(_collapsed_view(value)):
        return True
    return bool(_SQUEEZED_SHAPES.search(_squeezed_view(value)))


def _score(fact: Fact) -> float:
    """Corroboration-weighted confidence. Repeats from distinct members count."""
    return fact.confidence * math.log1p(fact.hits)


def _rank(fact: Fact) -> tuple[float, float]:
    return (_PROVENANCE_WEIGHT.get(fact.provenance, 0.0), _score(fact))


class Blackboard:
    def __init__(
        self,
        *,
        max_facts: int = 200,
        max_fact_chars: int = 160,
        brief_max_chars: int = 400,
    ) -> None:
        self._lock = asyncio.Lock()
        self._facts: dict[str, Fact] = {}
        self._max_facts = max(1, max_facts)
        self._max_fact_chars = max(16, max_fact_chars)
        self._brief_max_chars = max(0, brief_max_chars)
        self._quarantined = 0

    # -- writing ------------------------------------------------------------

    async def publish(self, facts: Iterable[Fact]) -> list[Fact]:
        """Store facts, returning only those that were new.

        Returning just the new ones keeps the event stream proportional to
        discoveries rather than to member count: 100 members all re-observing the
        same refusal phrasing produce one event, not a hundred.
        """
        accepted: list[Fact] = []
        async with self._lock:
            for incoming in facts:
                value = sanitize_untrusted(incoming.value, max_chars=self._max_fact_chars)
                if not value:
                    continue
                fact_id = fact_id_for(incoming.kind, value)
                existing = self._facts.get(fact_id)
                if existing is not None:
                    self._corroborate(existing, incoming)
                    continue
                stored = incoming.model_copy(
                    update={
                        "fact_id": fact_id,
                        "value": value,
                        "quarantined": looks_like_instruction(value),
                    }
                )
                self._facts[fact_id] = stored
                if stored.quarantined:
                    self._quarantined += 1
                accepted.append(stored)
            self._evict()
            # Eviction may have dropped something added in this batch, so never
            # announce a fact the store no longer holds.
            return [f for f in accepted if f.fact_id in self._facts]

    def _corroborate(self, existing: Fact, incoming: Fact) -> None:
        existing.hits += 1
        existing.confidence = min(0.95, max(existing.confidence, incoming.confidence) + 0.1)
        # Independent corroboration can only raise trust, never lower it.
        if _PROVENANCE_WEIGHT.get(incoming.provenance, 0.0) > _PROVENANCE_WEIGHT.get(
            existing.provenance, 0.0
        ):
            existing.provenance = incoming.provenance

    def _evict(self) -> None:
        overflow = len(self._facts) - self._max_facts
        if overflow <= 0:
            return
        # Ascending by (protected, score): unprotected low-value facts go first.
        ordered = sorted(
            self._facts.items(),
            key=lambda item: (item[1].kind in _PROTECTED_KINDS, _score(item[1])),
        )
        for fact_id, fact in ordered[:overflow]:
            if fact.quarantined:
                self._quarantined -= 1
            del self._facts[fact_id]

    # -- reading ------------------------------------------------------------

    async def brief(self, *, exclude_member: str = "", max_chars: int | None = None) -> str:
        """Render the highest-value facts for one member's prompt.

        A member never sees its own facts, so it cannot bootstrap itself off what
        it just reported. Quarantined values are excluded entirely.
        """
        budget = self._brief_max_chars if max_chars is None else max(0, max_chars)
        if budget == 0:
            return ""
        async with self._lock:
            candidates = [
                fact
                for fact in self._facts.values()
                if not fact.quarantined and fact.source_member_id != exclude_member
            ]
        candidates.sort(key=_rank, reverse=True)

        lines: list[str] = []
        used = 0
        for fact in candidates:
            suffix = f" (x{fact.hits})" if fact.hits > 1 else ""
            line = f"[{fact.kind}|{fact.provenance}] {fact.value}{suffix}"
            cost = len(line) + (1 if lines else 0)
            if used + cost > budget:
                continue
            lines.append(line)
            used += cost
        return "\n".join(lines)

    async def snapshot(self) -> list[dict]:
        """Serialisable view for ``scan.metadata``, highest value first.

        Includes quarantined facts: an injection attempt recovered from the target
        is one of the more interesting things a scan can report, even though it is
        never relayed to another member.
        """
        async with self._lock:
            facts = list(self._facts.values())
        facts.sort(key=_rank, reverse=True)
        return [fact.model_dump(mode="json") for fact in facts]

    async def size(self) -> int:
        async with self._lock:
            return len(self._facts)

    @property
    def quarantined_count(self) -> int:
        return self._quarantined
