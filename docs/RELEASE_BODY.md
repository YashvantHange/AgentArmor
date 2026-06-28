## AgentArmor v1.2.3 — Readable findings, scan progress, and report download

Latest release. Makes scan results easier to understand, adds live progress with ETA, and one-click report downloads from the GUI.

### Added — GUI UX
- **Findings:** executive summary, excerpt-first cards sorted by severity, attack chains collapsed by default
- **Scan progress:** live stopwatch, progress bar, ETA, human probe labels; technical SSE log collapsed
- **Reports:** download PDF, HTML, SARIF, JSON, or ZIP from Findings, Progress, and Reports pages
- Report download API with path traversal guard (`GET /v1/scans/{id}/reports/download`)

### Fixed
- `composite_vuln_score()` crash when all assertions pass (agent scans)
- Empty `Authorization: Bearer` header from config breaking connectivity checks

---

## Windows (recommended)

Download **AgentArmor_1.2.1_x64-setup.exe** or **AgentArmor_1.2.1_x64_en-US.msi** from the assets below (v1.2.3 app; installer filenames use 1.2.1).

1. Run the installer
2. Open **AgentArmor** — no Python install required
3. Run a scan → review findings with plain-language summaries → download reports from the header

For login-required chatbot targets, use **Login required (SSO)** in the website wizard.
