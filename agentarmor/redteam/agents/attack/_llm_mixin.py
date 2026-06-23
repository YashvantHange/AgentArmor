"""Shared LLM attack generation mixin."""

from __future__ import annotations

import random

from agentarmor.attack.mutations.registry import apply_mutation, list_mutations
from agentarmor.core.config import AppConfig
from agentarmor.redteam.agents.prompts import AGENT_PROMPTS
from agentarmor.redteam.budget.governor import BudgetGovernor
from agentarmor.redteam.llm_client import completion_json
from agentarmor.redteam.schemas import AttackPlan, AttackPrompt, TargetProfile
from agentarmor.redteam.skills.loader import SkillDef, skill_for_node


def validate_output(parsed: dict, *, max_len: int = 500) -> bool:
    prompt = parsed.get("prompt")
    if not prompt or not isinstance(prompt, str):
        return False
    if not prompt.strip() or len(prompt) > max_len:
        return False
    return True


def build_attack_prompt(
    *,
    plan: AttackPlan,
    skill: SkillDef,
    prompt: str,
    name: str,
    techniques: list[str],
    mutations: list[str],
    multi_turn: list[str] | None = None,
) -> AttackPrompt:
    return AttackPrompt(
        probe_id=f"redteam.{plan.path_id}.{plan.next_node}",
        name=name,
        prompt=prompt,
        owasp=list(skill.owasp),
        techniques=techniques or list(skill.bypass_techniques[:3]),
        mutations_applied=mutations,
        multi_turn=multi_turn,
        attack_path=plan.path_id,
        node_id=plan.next_node,
    )


def apply_strategy_mutations(
    prompt: str,
    skill: SkillDef,
    strategy: str,
) -> tuple[str, list[str], list[str]]:
    mutations: list[str] = []
    techniques: list[str] = []
    pool = [m for m in skill.mutations if m in list_mutations()] or list_mutations()[:3]

    if strategy in ("mutation_retry", "crescendo", "direct"):
        pick = pool[0] if pool else "roleplay"
        if strategy == "mutation_retry" and len(pool) > 1:
            pick = pool[1]
        prompt = apply_mutation(pick, prompt)
        mutations.append(pick)
        techniques.append(pick)

    return prompt, mutations, techniques


async def generate_from_skill(
    agent_id: str,
    config: AppConfig,
    budget: BudgetGovernor,
    profile: TargetProfile,
    plan: AttackPlan,
    *,
    last_response: str = "",
) -> AttackPrompt:
    node_id = plan.next_node
    skill = skill_for_node(node_id, agent_id)
    if skill is None:
        from agentarmor.redteam.skills.loader import skills_for_agent

        agent_skills = skills_for_agent(agent_id)
        skill = agent_skills[0] if agent_skills else None
    if skill is None:
        raise ValueError(f"No skill for agent {agent_id} node {node_id}")

    seed = random.choice(skill.seeds) if skill.seeds else "Test security vulnerability."
    prompt, mutations, techniques = apply_strategy_mutations(seed, skill, plan.strategy)
    name = skill.name
    multi_turn = list(skill.multi_turn) if skill.multi_turn else None

    system = AGENT_PROMPTS.get(agent_id, AGENT_PROMPTS["llm01"])
    if config.detection.analysis_mode == "cloud" and config.detection.agentic.api_key and budget.allow_continue():
        user = (
            f"node_id: {node_id}\nagent: {agent_id}\nstrategy: {plan.strategy}\n"
            f"skill: {skill.id}\nprofile: {profile.model_dump()}\n"
            f"seed_prompt: {prompt[:400]}\nlast_response: {last_response[:800]}\n"
        )
        parsed, _trace = await completion_json(
            config,
            budget,
            system=system,
            user=user,
            agent_name=f"attack_{agent_id}",
            temperature=0.4,
        )
        if parsed and validate_output(parsed):
            prompt = str(parsed["prompt"])
            techniques = list(parsed.get("techniques") or techniques)
            mutations = list(parsed.get("mutations_applied") or mutations)
            if parsed.get("name"):
                name = str(parsed["name"])
            mt = parsed.get("multi_turn")
            if isinstance(mt, list) and len(mt) >= 2:
                multi_turn = [str(t) for t in mt]

    return build_attack_prompt(
        plan=plan,
        skill=skill,
        prompt=prompt,
        name=name,
        techniques=techniques,
        mutations=mutations,
        multi_turn=multi_turn,
    )


def judge_rubric_for_node(agent_id: str, node_id: str) -> str:
    skill = skill_for_node(node_id, agent_id)
    if skill and skill.judge_rubric:
        return skill.judge_rubric
    return ""
