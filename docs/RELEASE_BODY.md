## AgentArmor v1.3.0 — Scan quality overhaul

Major release: OWASP Planner v2, finding clustering, calibrated progress/ETA, scan profiles, and production hardening.

### Added
- **OWASP Planner v2** — ~50 probes at standard depth, Quick/Standard/Deep budgets, capability-aware selection
- **Finding clustering** — root-cause cards, semantic merge, replay bundles, grouped findings API
- **Scan progress** — weighted work units, ETA confidence bands, planner-aware layer tracking
- **Risk-based planning** — probe reorder after early failures; adaptive depth escalation
- **Scan profiles** — 8 presets including `production_readiness` and `owasp_audit` (GUI picker)
- **API** — plan preview, metrics, regression compare, attack narrative graph
- **Parallel L1/L2 batches** with per-probe fault isolation

### Fixed
- Failed scans set `FAILED` status (no stuck `RUNNING`)
- Budget preflight rejects over-limit scans before start
- Grouped findings endpoint and web planner crashes

---

## Windows (recommended)

Download **AgentArmor_1.3.0_x64-setup.exe** or **AgentArmor_1.3.0_x64_en-US.msi** from the assets below.

1. Run the installer
2. Open **AgentArmor** — no Python install required
3. Choose a scan profile → run scan → review grouped findings → download reports
