"""Parallel execution for independent probes."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar

T = TypeVar("T")

PARALLEL_LAYERS = frozenset({"L1", "L2", "plugin"})


class _ProbeLike(Protocol):
    id: str
    layer: str
    multi_turn: object | None
    memory_turns: object | None
    module_kind: str | None


def is_parallel_safe(probe: _ProbeLike) -> bool:
    if probe.layer not in PARALLEL_LAYERS:
        return False
    if probe.multi_turn is not None or probe.memory_turns is not None:
        return False
    if probe.module_kind:
        return False
    return True


def partition_probes(probes: list[_ProbeLike]) -> list[list[_ProbeLike]]:
    """Group consecutive parallel-safe probes into batches; stateful probes run alone."""
    batches: list[list[_ProbeLike]] = []
    current: list[_ProbeLike] = []

    for probe in probes:
        if is_parallel_safe(probe):
            current.append(probe)
        else:
            if current:
                batches.append(current)
                current = []
            batches.append([probe])

    if current:
        batches.append(current)
    return batches


async def run_batches(
    batches: list[list[_ProbeLike]],
    runner: Callable[[_ProbeLike], Awaitable[T]],
    *,
    max_parallel: int = 4,
) -> list[T]:
    results: list[T] = []
    sem = asyncio.Semaphore(max(1, max_parallel))

    async def _run_one(probe: _ProbeLike) -> T:
        async with sem:
            return await runner(probe)

    for batch in batches:
        if len(batch) == 1 or not is_parallel_safe(batch[0]):
            results.append(await runner(batch[0]))
        else:
            batch_results = await asyncio.gather(*[_run_one(p) for p in batch])
            results.extend(batch_results)
    return results
