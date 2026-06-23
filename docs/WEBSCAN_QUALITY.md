# Web Scan Quality Standards

This document defines quality gates for the Chatbot URL Scanner (`agentarmor.webscan`).

## Scope

Web scans discover embedded chat widgets on public pages, infer agent capabilities (RAG, tools, MCP, memory, A2A), run OWASP LLM Top 10 probes via Playwright, and produce findings. API endpoint scans are unchanged.

## Capability Detection

| Signal | Sources | Minimum confidence |
|--------|---------|-------------------|
| RAG | DOM copy, `/retrieve`/`/search` network paths | DOM phrase match |
| Tools | Action buttons/chips, network tool endpoints | ≥2 hints for high confidence |
| MCP | JSON-RPC paths, `__MCP__` globals, well-known URLs | DOM or network marker |
| Memory | UI copy, localStorage keys, `/memory` paths | ≥1 indicator |
| A2A | Agent card URLs, multi-agent framework markers | Network or well-known hit |

Detectors must be deterministic on fixture HTML; Playwright tests cover each layer.

## Agent Risk Score (0–10)

Computed from configurable weights in `[webscan.risk_weights]` (`AgentArmor.toml`):

- Per detected tool (capped)
- RAG, memory, MCP flags
- MCP + tools combination
- External action tools (email, CRM, payment, etc.)
- High agentic score threshold

Scores are bounded `[0, 10]` with human-readable `risk_reasons` for reports and GUI.

## Probe Selection

`select_probes_for_capabilities()` adds capability-specific probes:

- **RAG** → full `web.rag.*` set (LLM08, LLM01, LLM02)
- **Memory** → `web.memory.*` (LLM01, LLM02, LLM04)
- **MCP** → `web.mcp.*` (LLM06)
- **Tools** → per-tool abuse probes + permission escalation when LLM06 is in scope

Base OWASP filters: LLM01, LLM02, LLM05, LLM06, LLM07, LLM08, LLM09.

## SSRF & Browser Safety

- URL validation blocks private IPs, localhost, and link-local ranges before navigation.
- Playwright route guards block unexpected file/data schemes.
- Browser pool respects `max_concurrent_browsers` from config.

## Testing Requirements

### Unit tests (no browser)

- URL validator, probe catalog, risk profile, attack planner, tool/MCP network heuristics

### Playwright tests (optional extra)

Install: `pip install -e ".[browser]"` then `playwright install chromium`

Fixtures live in `tests/fixtures/webscan/`:

- `rag_widget.html`, `tool_actions.html`, `mcp_jsonrpc.html`, `memory_chat.html`, `a2a_agent_card.json`

Run: `pytest tests/test_webscan_*.py`

## CI

The CI workflow installs the `browser` extra, installs Chromium, and runs the full webscan test suite alongside the main pytest job.

## GUI

Discovery step shows `CapabilityMapView` and `AgentRiskCard`. HTML reports include a Capability Map section when scan metadata contains `capability_map`.

## Regression

Before merging Part 2+ changes:

1. `pytest tests/test_webscan_*.py`
2. `pytest tests/` (full suite)
3. `npm run build` in `gui/` when frontend types or components change

## Out of Scope (future)

- Docker worker pool (1 browser = 1 container)
- macOS `.app` with Playwright bundle

## Part 4 — Enterprise + Autonomous Red Team

| Feature | Behavior |
|---------|----------|
| `auth_mode: manual_session` | `prepare-session` opens headed browser; `continue` encrypts storage state (24h TTL) |
| `planner_enabled` | Multi-agentic + cloud API key; LLM generates 3–8 custom probes |
| Multi-turn memory | `web.memory.poison-verify` runs two turns without page reload |
| Rate limits | `webscan.max_scans_per_day` enforced via DB count |
| Reports | HTML attack plan summary (rule + LLM probe counts) |

### Part 4 sign-off

```
Part 4 Plan Audit
[x] session_store.py + prepare-session / continue API
[x] AuthSessionStep.tsx + planner checkbox in WebScanWizard
[x] llm_planner.py + plan_web_attack_with_llm
[x] Multi-turn memory probe + discovery_feedback on miss
[x] test_webscan_auth_session.py, test_webscan_llm_planner.py, test_webscan_rate_limits.py
```

| Feature | Behavior |
|---------|----------|
| `ScanDepth.MULTI_AGENTIC` | Cloud API key required; enables L5 judge + LLM widget discovery |
| `planning/attack_planner.py` | Expands probe budget and prioritizes capability probes |
| `multi_agentic` + `planner_enabled` | Runs `RedTeamOrchestrator` with attack-graph paths from `CapabilityMap` |
| `redteam/` package | Budget-governed multi-agent loop; 13 agents + skill YAML; see [`REDTEAM_QUALITY.md`](REDTEAM_QUALITY.md) |
| `discovery/llm_classifier.py` | Layer 3 LLM widget refinement when heuristics are weak |
| Windows bundle | `setup-embed-python.ps1` installs `[ml,browser]` + Chromium to `resources/playwright/` |
| Tauri sidecar | Sets `PLAYWRIGHT_BROWSERS_PATH` when bundled browsers exist |
| Smoke test | `packaging/test-embed-webscan.ps1` |

### Part 3 sign-off

```
Part 3 Plan Audit
[x] llm_classifier.py, attack_planner.py, ScanDepthPicker
[x] multi_agentic API (400 without key)
[x] Orchestrator judge + LLM discovery wiring
[x] PLAYWRIGHT_BROWSERS_PATH in lib.rs
[x] test_webscan_agentic.py + packaging smoke script
```
