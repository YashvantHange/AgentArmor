## AgentArmor v1.2.0 — Full Platform Release

All four development phases ship together in this release.

### Phase 1 — Universal endpoint scanning
- OpenAI / custom / auto-detected API profiles
- Connectivity guards (no silent PASS on HTML errors)
- Promptfoo-inspired plugins, strategies, and assertions
- Multi-agent cloud enrichment (judge, triage, OWASP mapping)
- Chatbot security wizard in the desktop GUI

### Phase 2 — Adaptive attack generation
- L0 attack generator with 100+ mutation variants per goal
- OWASP suites: prompt leak, poisoning, model theft, memory poison
- Enterprise risk score (0–100) with exploitability and confidence
- Attack trees and evidence graph in findings UI

### Phase 3 — Self-play red teaming
- Attacker / Defender / Judge autonomous loop
- Multi-agent attack discovery (Garak-style)
- Tools benchmark: compare AgentArmor vs PyRIT, Garak, Promptfoo, Inspect AI

### Phase 4 — Ecosystem
- Community rule marketplace (install probes and OWASP packs)
- Custom Probe SDK for third-party extensions
- Continuous monitoring with scheduled rescans and drift detection
- Research dataset export (anonymized JSONL)

### Desktop GUI
- Redesigned security-console UI
- Marketplace, Monitoring, Benchmark, and Chatbot wizard screens

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
agentarmor marketplace list
agentarmor monitor add "Daily API" --url https://api.example.com/v1/chat/completions
agentarmor dataset export -o research.jsonl
```

## GitHub Action (CI)

```yaml
- uses: YashvantHange/AgentArmor/action@v1
  with:
    url: https://api.example.com/v1/chat/completions
```
