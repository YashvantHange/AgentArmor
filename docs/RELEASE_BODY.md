## What's new in v1.0.1

- Redesigned desktop UI (security-console layout, improved scan progress)
- Fixes for SSE live progress, sidecar startup, and form validation

## Windows (recommended)

Download **AgentArmor_*_x64-setup.exe** or **.msi** from the assets below.

1. Run the installer (or portable `.exe`)
2. Double-click **AgentArmor** — no Python install required
3. Pick a scan type → configure → run → export HTML/SARIF/PDF from Reports

Portable mode: run from a folder containing a `PORTABLE` file; data is stored in `./data/`.

## macOS

A native Mac `.app` is **not bundled in v1.0.0** (Windows desktop first). Use the CLI + web UI:

```bash
# Install
pip install agentarmor
pip install agentarmor[local]   # optional: offline .gguf scanning

# Detection models (one-time)
agentarmor models download

# Terminal 1 — API sidecar
agentarmor serve --port 8787

# Terminal 2 — GUI (dev mode)
git clone https://github.com/YashvantHange/AgentArmor.git
cd AgentArmor/gui && npm install && npm run dev
# Open http://localhost:1420
```

Or use **CLI only** (no GUI):

```bash
agentarmor scan --provider openai --format html,sarif
agentarmor benchmark --providers openai,anthropic --suite owasp
```

See [docs/MAC.md](https://github.com/YashvantHange/AgentArmor/blob/main/docs/MAC.md) for full Mac instructions.

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
