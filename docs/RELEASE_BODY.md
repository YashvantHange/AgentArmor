## AgentArmor v1.2.2 — Website URL chatbot scanning

Latest release. Fixes long-running website URL scans disconnecting from live progress, and improves Playwright discovery and response capture for real chatbot UIs.

### Fixed — Website URL chatbot scanning
- SSE scan progress: 30s heartbeats and discovery/planning events so long web scans no longer show "Connection to scan stream lost"
- Scan progress UI falls back to status polling if the live stream disconnects
- Playwright response capture uses baseline diffing and chat-root detection (Gandalf, Prompt Airlines-style UIs)
- Send-button heuristics skip upload/attach controls; async route guard fix in browser session
- SPA page wait for visible chat inputs; `webscan.timeout_s` default raised to 60s
- Low-confidence widget fallback and optional `llm_discovery_on_miss` config
- `ScanSummary` metadata typing for web-scan status polling (GUI production build)

### Added
- Framework hints for ChatGPT, Claude, and Gemini; chat keywords for challenge sites
- Gandalf-like HTML fixture and Playwright regression test
- GUI disclaimer on website URL testing limits vs API endpoint scanning

---

## Windows (recommended)

Download **AgentArmor_1.2.1_x64-setup.exe** or **AgentArmor_1.2.1_x64_en-US.msi** from the assets below (v1.2.2 app; installer filenames use 1.2.1).

1. Run the installer
2. Open **AgentArmor** — no Python install required
3. **Test my chatbot** → website URL or API URL → run scan → export reports

For login-required targets (ChatGPT, Claude), use **Login required (SSO)** in the website wizard.
