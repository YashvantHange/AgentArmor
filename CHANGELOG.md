# Changelog

All notable changes to AgentArmor are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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

[1.2.0]: https://github.com/YashvantHange/AgentArmor/compare/v1.0.1...v1.2.0
[1.0.1]: https://github.com/YashvantHange/AgentArmor/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/YashvantHange/AgentArmor/releases/tag/v1.0.0
