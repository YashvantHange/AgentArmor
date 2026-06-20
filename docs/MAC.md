# Running AgentArmor on macOS

v1.0.0 ships a **Windows desktop installer** on GitHub Releases. macOS uses **PyPI + CLI** (native `.app` is planned post-MVP).

## Requirements

- Python 3.10+ (`python3 --version`)
- Node.js 20+ (only if you want the web GUI in dev mode)

## Quick start (CLI only)

```bash
pip install agentarmor
# Optional: local model scanning
pip install agentarmor[local]

agentarmor models download

# Scan a cloud provider
export OPENAI_API_KEY=sk-...
agentarmor scan --provider openai --format html,sarif

# Benchmark
agentarmor benchmark --providers openai,anthropic --suite owasp
```

## GUI on Mac (dev mode)

The Tauri desktop app targets Windows first. On Mac, run the API sidecar and the Vite dev UI:

```bash
# Terminal 1
agentarmor serve --port 8787

# Terminal 2
git clone https://github.com/YashvantHange/AgentArmor.git
cd AgentArmor/gui
npm install
VITE_API_URL=http://127.0.0.1:8787 npm run dev
```

Open **http://localhost:1420** in your browser.

## All scan modes (CLI)

| Mode | Command |
|------|---------|
| API endpoint | `agentarmor scan --url http://host/v1/chat/completions` |
| Cloud provider | `agentarmor scan --provider anthropic` |
| Local model | `agentarmor scan --model ./model.gguf` |
| Agent | `agentarmor scan --agent crewai` |
| MCP | `agentarmor scan --mcp ./server.py` |
| RAG | `agentarmor scan --rag ./corpus` |

## Building a Mac app (advanced)

Tauri supports macOS builds from the `gui/` folder:

```bash
cd gui
npm install
npm run tauri build
```

You must install [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) (Xcode CLT, Rust). The sidecar still expects Python with `agentarmor` installed unless you bundle embed Python (Windows-only script today).

## Roadmap

Native macOS `.dmg` with embedded Python is planned for a post-MVP release.
