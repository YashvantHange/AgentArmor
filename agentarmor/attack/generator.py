"""L0 attack generator — goal → seed → mutations → probe variants."""

from __future__ import annotations

from agentarmor.attack.goals import AttackGoalDef, get_goal, load_goals
from agentarmor.attack.models import L0Variant, variant_to_runnable_metadata
from agentarmor.attack.mutations.cloud import generate_cloud_mutations
from agentarmor.attack.mutations.registry import MUTATION_REGISTRY, apply_mutation
from agentarmor.attack.suites import collect_suite_probes
from agentarmor.core.config import AppConfig

__all__ = ["L0Variant", "generate_l0_probes", "generate_l0_probes_async", "variant_to_runnable_metadata"]

_MAX_MUTATION_DEPTH = 4


def _expand_goal(goal: AttackGoalDef, max_variants: int) -> list[L0Variant]:
    """BFS mutation expansion — up to max_variants per goal."""
    variants: list[L0Variant] = []
    seen_prompts: set[str] = set()

    for seed_idx, seed in enumerate(goal.seeds):
        if len(variants) >= max_variants:
            break
        seed_id = f"l0.{goal.id}.seed{seed_idx}"
        # frontier: prompt, mutation_chain, probe_id, mutated_from
        frontier: list[tuple[str, list[str], str, str | None]] = [
            (seed, [], seed_id, None),
        ]

        while frontier and len(variants) < max_variants:
            prompt, chain, probe_id, parent = frontier.pop(0)
            if prompt in seen_prompts:
                continue
            seen_prompts.add(prompt)

            if chain:
                label = " → ".join(chain)
                name = f"{goal.name} — {label}"
            else:
                name = f"{goal.name} — Seed {seed_idx + 1}"

            variants.append(
                L0Variant(
                    id=probe_id,
                    name=name,
                    owasp=list(goal.owasp),
                    prompt=prompt,
                    attack_goal=goal.id,
                    mutation_chain=list(chain),
                    mutated_from=parent,
                )
            )

            if len(chain) >= _MAX_MUTATION_DEPTH:
                continue
            for mut_name in goal.mutations:
                if len(variants) + len(frontier) >= max_variants:
                    break
                mutated = apply_mutation(mut_name, prompt)
                if mutated in seen_prompts:
                    continue
                child_id = f"l0.{goal.id}.{'_'.join(chain + [mut_name])}{seed_idx}"
                frontier.append((mutated, chain + [mut_name], child_id, probe_id))

    return variants[:max_variants]


async def _append_cloud_mutations(
    goal: AttackGoalDef,
    variants: list[L0Variant],
    config: AppConfig,
    max_variants: int,
) -> list[L0Variant]:
    """Add LLM-generated wrappers when Cloud Enhanced mode is active."""
    l0_cfg = config.detection.l0
    if not l0_cfg.cloud_mutations_enabled:
        return variants
    remaining = max(0, max_variants - len(variants))
    if remaining <= 0:
        return variants

    per_seed = max(1, min(l0_cfg.cloud_mutations_per_goal, remaining) // max(len(goal.seeds), 1))
    seen = {v.prompt for v in variants}

    for seed_idx, seed in enumerate(goal.seeds):
        if len(variants) >= max_variants:
            break
        cloud_pairs = await generate_cloud_mutations(
            goal_id=goal.id,
            goal_name=goal.name,
            seed=seed,
            config=config,
            count=per_seed,
        )
        for tech_idx, (technique, prompt) in enumerate(cloud_pairs):
            if len(variants) >= max_variants or prompt in seen:
                continue
            seen.add(prompt)
            slug = technique.lower().replace(" ", "-")[:24]
            variants.append(
                L0Variant(
                    id=f"l0.{goal.id}.cloud.{slug}{seed_idx}_{tech_idx}",
                    name=f"{goal.name} — Cloud: {technique}",
                    owasp=list(goal.owasp),
                    prompt=prompt,
                    attack_goal=goal.id,
                    mutation_chain=["cloud_llm", slug],
                    mutated_from=f"l0.{goal.id}.seed{seed_idx}",
                )
            )
    return variants


def generate_l0_probes(config: AppConfig) -> list[L0Variant]:
    """Sync entry — deterministic mutations only (offline)."""
    return _generate_l0_probes_sync(config)


async def generate_l0_probes_async(config: AppConfig) -> list[L0Variant]:
    """Async entry — deterministic + cloud LLM mutations when enabled."""
    l0_cfg = config.detection.l0
    if not l0_cfg.enabled:
        return []

    max_variants = max(1, l0_cfg.max_variants_per_goal)
    all_goals = load_goals()
    variants: list[L0Variant] = []

    for goal_id in l0_cfg.goals:
        goal = all_goals.get(goal_id) or get_goal(goal_id)
        if goal is None:
            continue
        cloud_slots = 0
        if (
            l0_cfg.cloud_mutations_enabled
            and config.detection.analysis_mode == "cloud"
            and config.detection.agentic.enabled
            and (config.detection.agentic.api_key or "")
        ):
            cloud_slots = min(l0_cfg.cloud_mutations_per_goal, max_variants // 2)
        det_cap = max(1, max_variants - cloud_slots)
        goal_variants = _expand_goal(goal, det_cap)
        goal_variants = await _append_cloud_mutations(goal, goal_variants, config, max_variants)
        variants.extend(goal_variants[:max_variants])

    variants.extend(collect_suite_probes(config, l0_cfg.suites))
    return variants


def _generate_l0_probes_sync(config: AppConfig) -> list[L0Variant]:
    l0_cfg = config.detection.l0
    if not l0_cfg.enabled:
        return []

    max_variants = max(1, l0_cfg.max_variants_per_goal)
    all_goals = load_goals()
    variants: list[L0Variant] = []

    for goal_id in l0_cfg.goals:
        goal = all_goals.get(goal_id) or get_goal(goal_id)
        if goal is None:
            continue
        variants.extend(_expand_goal(goal, max_variants))

    variants.extend(collect_suite_probes(config, l0_cfg.suites))
    return variants
