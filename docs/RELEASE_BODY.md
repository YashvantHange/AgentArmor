## AgentArmor v1.2.1 — Multi-agent red team & web scan

This release ships the multi-agent OWASP red team roster and enterprise chatbot URL scanner improvements from the latest `main` branch.

### Multi-agent OWASP red team
- `agentarmor/redteam/` orchestrator with attack-graph planner, budget governor, and verdict scoring
- 16 skill YAML bundles and 13 dedicated agent classes (LLM01–LLM10, Memory, A2A, MCP)
- `scan_mode=multi_agent_redteam` on `/v1/scans` (requires cloud analysis API key)
- Web scans: `multi_agentic` + `planner_enabled` runs red team against discovered widgets
- Findings include confidence, reproducibility, and impact scores
- GUI toggle for multi-agent red team; quality gates and regression tests in CI

### Chatbot URL scanner
- Enterprise `manual_session` auth with headed browser login and encrypted session storage
- `POST /v1/web-scans/prepare-session` and continue flow for SSO-style targets
- LLM attack planner for multi-agentic web scans
- Multi-turn memory probe without page reload
- Daily web scan rate limiting and HTML report attack-plan summary

### Packaging
- Embedded Python bundle includes red team skills and Playwright for packaged `.exe` builds
- Version aligned to 1.2.1 across Python, Tauri, and npm

---

## Windows (recommended)

Download **AgentArmor_*_x64-setup.exe** or **.msi** from the assets below.

1. Run the installer (or portable `.exe`)
2. Double-click **AgentArmor** — no Python install required
3. Pick a scan type → configure → run → export HTML/SARIF/PDF from Reports

Portable mode: run from a folder containing a `PORTABLE` file; data is stored in `./data/`.

## macOS

A native Mac `.app` is **not bundled** (Windows desktop first). Use the CLI + web UI:

```bash
pip install agentarmor
pip install agentarmor[local]   # optional: offline .gguf scanning
agentarmor models download
agentarmor serve --port 8787
cd AgentArmor/gui && npm install && npm run dev
```

See [docs/MAC.md](https://github.com/YashvantHange/AgentArmor/blob/main/docs/MAC.md).

## Linux / PyPI

```bash
pip install agentarmor
agentarmor scan --url http://localhost:8000/v1/chat/completions
```

## GitHub Action (CI)

```yaml
- uses: YashvantHange/AgentArmor/action@v1
  with:
    url: https://api.example.com/v1/chat/completions
```
