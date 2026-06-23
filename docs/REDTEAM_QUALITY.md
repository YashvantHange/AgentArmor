# Red Team Agent Quality Standards

Quality gates for the multi-agent OWASP red team (`agentarmor.redteam`).

## Agent roster

| Agent ID | Module | Skills |
|----------|--------|--------|
| llm01–llm10 | `agents/attack/llm_agents.py` | `skills/llmNN.yaml` |
| memory | `agents/attack/memory_agent.py` | `skills/memory.yaml` |
| a2a | `agents/attack/a2a_agent.py` | `skills/a2a.yaml` |
| mcp | `agents/attack/mcp_agent.py` | `skills/mcp.yaml` |

Each skill YAML defines: seeds, mutations, OWASP mapping, judge rubric, optional multi_turn.

## Structural gates

Run before merge:

```bash
pytest tests/test_redteam_quality.py tests/test_redteam_*.py -v
python scripts/validate_redteam_agents.py
```

| Gate | Rule |
|------|------|
| Skill completeness | Every skill has agent, name, seeds, mutations, owasp |
| Mutation validity | All mutation names exist in `MUTATION_REGISTRY` |
| Registry coverage | Every skill.agent is in `AGENT_REGISTRY` |
| Graph coverage | Every attack-graph node resolves via `resolve_agent()` |
| Prompt presence | Each agent has a system prompt in `agents/prompts.py` |
| No secrets in seeds | Seeds must not contain real API key patterns |
| Wheel bundle | Skills load after `pip install` from wheel |

## Regression (existing features)

Red team is **opt-in only**:

- `scan_mode=multi_agent_redteam` (API scans)
- `multi_agentic + planner_enabled` (web scans)

Standard scans must continue using the linear probe loop. Run full suite:

```bash
pytest tests/ -q
pytest tests/test_webscan_*.py -v
cd gui && npm run build
```

## Exe / embed smoke

After `setup-embed-python.ps1`:

```powershell
.\packaging\test-embed-redteam.ps1
```
