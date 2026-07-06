## AgentArmor v1.4.0 — Multi-agentic only

AgentArmor is now a **multi-agent AI red-teaming platform**. The offline analysis mode has
been removed: every scan runs capability-aware attack-graph planning, an LLM judge, and
confidence scoring. This release also fixes real correctness bugs in the multi-agentic engine.

### Changed
- **Offline analysis mode removed** — the GUI offline↔cloud picker is gone; the CLI and API
  run multi-agent (cloud) analysis on every scan.
- **Analysis API key now required** — scans without a provider key are rejected with a clear
  error. Set `AGENTARMOR_ANALYSIS_API_KEY`, or configure it in Settings / `AgentArmor.toml`.
- The local L1–L4/meta detection engine still runs as the under-the-hood scorer; local
  model-file scanning (`--model`) is unaffected.

### Fixed (multi-agentic engine)
- **Module targets now receive the real attack** — red-team attacks against agent/MCP/RAG
  targets send the generated attack (harness prompt, RAG query, MCP tool-parameter injection)
  instead of running a static probe and relabelling the display text.
- **Budget metering** — the LLM judge and web attack planner now record token/cost usage
  against the budget governor instead of bypassing it.

### Added (multi-agentic engine)
- **Per-path campaign coverage** — a finding now retires only its attack path and the campaign
  continues across the remaining paths, instead of stopping at the first finding.

---

## Windows (recommended)

Download **AgentArmor_1.4.0_x64-setup.exe** or **AgentArmor_1.4.0_x64_en-US.msi** from the assets below.

1. Run the installer
2. Open **AgentArmor** — no Python install required
3. Add your analysis provider API key in **Settings**
4. Choose a scan profile → run scan → review grouped findings → download reports
