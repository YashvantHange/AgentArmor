# Changelog

All notable changes to AgentArmor are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [1.2.2] - 2026-06-27

### Fixed — Website URL chatbot scanning
- SSE scan progress: 30s heartbeats and discovery/planning events so long web scans no longer show "Connection to scan stream lost"
- Scan progress UI falls back to status polling if the live stream disconnects
- Playwright response capture uses baseline diffing and chat-root detection (Gandalf, Prompt Airlines-style UIs)
- Send-button heuristics skip upload/attach controls; async route guard fix in browser session
- SPA page wait for visible chat inputs; `webscan.timeout_s` default raised to 60s
- Low-confidence widget fallback and optional `llm_discovery_on_miss` config

### Added
- Framework hints for ChatGPT, Claude, and Gemini; chat keywords for challenge sites
- Gandalf-like HTML fixture and Playwright regression test
- GUI disclaimer on website URL testing limits vs API endpoint scanning

## [1.2.1] - 2026-06-23

### Added — Multi-agent OWASP red team
- New `agentarmor/redteam/` package: attack-graph planner, budget governor, capability-aware attack agents (Memory, A2A, MCP, RAG, baseline LLM01/07)
- `scan_mode=multi_agent_redteam` on `/v1/scans` (requires cloud analysis API key)
- Web scans: `multi_agentic` + `planner_enabled` runs `RedTeamOrchestrator` against discovered widgets
- Findings include `confidence_score`, `reproducibility_score`, and `impact_score` via `RedTeamVerdict`
- Config: `[redteam.budget]` and `[redteam.multi_agent]` in `AgentArmor.toml`
- GUI: "Multi-agent red team" toggle (API scans), renamed cloud analysis labels
- Tests: `test_redteam_*.py` (quality gates, per-agent, regression); `docs/REDTEAM_QUALITY.md`
- 13 skill YAML bundles + dedicated LLM01–LLM10, Memory, A2A, MCP agent classes with registry

### Added — Chatbot URL Scanner (Part 4)
- Enterprise `manual_session` auth: headed browser login, encrypted local session storage (24h TTL)
- `POST /v1/web-scans/prepare-session` and `POST /v1/web-scans/{id}/continue` API flow
- LLM attack planner (`planner_enabled`) for multi-agentic scans with cloud API key
- Multi-turn memory probe (`web.memory.poison-verify`) without page reload between turns
- Daily web scan rate limiting via `webscan.max_scans_per_day`
- HTML reports: attack plan summary (rule-based + LLM probe counts)
- GUI: `AuthSessionStep`, SSO auth mode, LLM planner toggle in `WebScanWizard`

## [1.2.0] - 2026-06-20

### Added — Phase 1 (Universal endpoint scanning)
- OpenAI, custom, and auto-detected API endpoint profiles
- Connectivity guards (no silent PASS on HTML page URLs or HTTP errors)
- Promptfoo-inspired plugins, strategies, and assertions layer
- Multi-agent cloud enrichment (judge, triage, OWASP mapping, remediation)
- Chatbot security wizard in the desktop GUI

### Added — Phase 2 (Adaptive attack generation)
- L0 attack generator with 100+ mutation variants per goal
- OWASP suites: prompt leak, poisoning, model theft, memory poison
- Enterprise risk score (0–100) with exploitability, confidence, reproducibility
- Attack trees and evidence graph in the Findings UI
- RAG synthetic poisoning probes integrated with PoisoningSuite
- Expanded MCP security suite (15 probes)

### Added — Phase 3 (Self-play red teaming)
- Self-play loop: Attacker / optional Defender / Judge
- Multi-agent attack discovery (Garak-style goal proposals)
- Tools benchmark comparing AgentArmor vs PyRIT, Garak, Promptfoo, Inspect AI
- Red-team options in scan wizard and Settings

### Added — Phase 4 (Ecosystem)
- Community rule marketplace (install probes and OWASP packs)
- Custom Probe SDK (`agentarmor.sdk.probe_sdk`) with validation and publish flow
- Continuous monitoring with scheduled rescans and drift detection
- Research dataset export (anonymized JSONL)
- CLI: `agentarmor marketplace`, `agentarmor monitor`, `agentarmor dataset`
- GUI: Marketplace and Monitoring screens

### Changed
- Desktop GUI version aligned to 1.2.0 across Tauri, npm, and Python package
- Benchmark page adds Models and Tools comparison tabs

## [1.0.1] - 2026-06-20

### Added
- Redesigned desktop security-console UI
- Live SSE scan progress with probe decision details

### Fixed
- Sidecar health wait on GUI startup
- Form validation and scan progress streaming

## [1.0.0] - 2026-06-20

### Added
- Initial MVP: CLI, FastAPI sidecar, SQLite persistence
- API, provider, local model, agent, MCP, and RAG scanners
- Hybrid detection pipeline (L1–L4 + optional agentic enrichment)
- SARIF, HTML, PDF, CSV, JSON reporting
- Model benchmarking (`agentarmor benchmark`)
- Windows desktop GUI (Tauri v2) with embedded Python
- GitHub Action for CI security scans
- Docker image and PyPI package scaffolding

[1.2.2]: https://github.com/YashvantHange/AgentArmor/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/YashvantHange/AgentArmor/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/YashvantHange/AgentArmor/compare/v1.0.1...v1.2.0
[1.0.1]: https://github.com/YashvantHange/AgentArmor/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/YashvantHange/AgentArmor/releases/tag/v1.0.0
