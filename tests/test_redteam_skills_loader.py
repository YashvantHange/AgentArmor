"""Skill loader tests."""

from agentarmor.redteam.skills.loader import get_skill, load_skills, skills_for_agent


def test_load_all_skills():
    skills = load_skills()
    assert "llm01_prompt_injection" in skills
    assert "memory_poison" in skills
    assert "a2a_handoff" in skills
    assert "mcp_enumeration" in skills


def test_skills_for_llm06():
    skills = skills_for_agent("llm06")
    assert len(skills) >= 1
    assert skills[0].owasp == ["LLM06"]


def test_get_skill_judge_rubric():
    skill = get_skill("llm07_system_prompt_leak")
    assert skill is not None
    assert "system prompt" in skill.judge_rubric.lower()
