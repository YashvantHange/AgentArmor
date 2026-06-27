# AgentArmor

**The Armor for AI Security** — continuously test, audit, and red-team LLM APIs, agents, MCP servers, and RAG systems.

AgentArmor runs structured security probes against your AI stack, scores findings with an enterprise risk model (0–100), maps results to **OWASP LLM Top 10**, and exports reports for developers and security teams (SARIF, HTML, PDF, CSV).

**Latest release:** [v1.2.2](https://github.com/YashvantHange/AgentArmor/releases/tag/v1.2.2) · [Changelog](CHANGELOG.md)

---

## What AgentArmor does

| Capability | Description |
|------------|-------------|
| **Endpoint scanning** | Test any OpenAI-compatible or auto-detected chat API URL |
| **Cloud providers** | OpenAI, Anthropic, Gemini, and more via LiteLLM |
| **Local models** | Offline scanning of `.gguf` and HuggingFace models |
| **Agent / MCP / RAG** | Security probes for tool-calling agents, MCP servers, and retrieval pipelines |
| **L0 adaptive attacks** | 100+ mutation variants per attack goal (jailbreak, prompt leak, exfiltration) |
| **Self-play red teaming** | Attacker → Target → Judge loop to find vulns static probes miss |
| **Benchmarking** | Compare models and tools (AgentArmor vs PyRIT, Garak, Promptfoo, Inspect AI) |
| **Marketplace** | Install community probes and OWASP packs |
| **Monitoring** | Scheduled rescans with drift detection |
| **CI/CD** | GitHub Action + `agentarmor gate` for pipeline security gates |


**End users on Windows:** download the [release installer](https://github.com/YashvantHange/AgentArmor/releases/latest), double-click, and run scans — no Python, Rust, or Node install needed.

**Developers / CLI users:** need Python 3.10+. Rust is only for compiling the optional native signature engine or building the Tauri GUI yourself.

---

## Quick install

### Windows desktop (recommended)

1. Download **`AgentArmor_1.2.1_x64-setup.exe`** or **`.msi`** from [Releases](https://github.com/YashvantHange/AgentArmor/releases/latest) (v1.2.2 release; installer filenames still use 1.2.1)
2. Run the installer
3. Open **AgentArmor** → choose scan type (API, Local Model, Agent, MCP, RAG, Benchmark)
4. Configure target → run scan → review findings → export reports

Portable mode: place a file named `PORTABLE` next to the executable; data is stored in `./data/`.

### CLI (all platforms)

```bash
pip install agentarmor

# Optional: offline local model scanning
pip install agentarmor[local]

# One-time detection model download
agentarmor models download
```

### Docker

```bash
docker build -f docker/Dockerfile -t agentarmor/agentarmor .
docker run -p 8787:8787 agentarmor/agentarmor
```

---

## Usage examples

### Scan an API endpoint

```bash
# OpenAI-compatible chat API (use the POST URL from DevTools, not the HTML page)
agentarmor scan --url http://localhost:8000/v1/chat/completions

# Cloud provider
export OPENAI_API_KEY=sk-...
agentarmor scan --provider openai

# With cloud enrichment + self-play red teaming
agentarmor scan --url https://api.example.com/v1/chat/completions \
  --analysis-mode cloud \
  --self-play-enabled
```

### Scan agents, MCP, and RAG

```bash
agentarmor scan --agent crewai --agent-config agent.toml
agentarmor scan --mcp ./filesystem-mcp
agentarmor scan --rag ./corpus --embedder bge
```

### Local models (offline)

```bash
pip install agentarmor[local]
agentarmor scan --model llama-3.gguf
agentarmor scan --model ./models/qwen3
```

### Benchmarks

```bash
# Model leaderboard
agentarmor benchmark --providers openai,anthropic,gemini --suite owasp

# Tools comparison
agentarmor benchmark tools --suite owasp-llm01 --targets corpus
```

### Ecosystem (v1.2)

```bash
agentarmor marketplace list
agentarmor marketplace install roleplay-injection

agentarmor monitor add "Daily API" --url https://api.example.com/v1/chat/completions --cron daily
agentarmor monitor run <schedule-id>

agentarmor dataset export -o research.jsonl --anonymize
```

### Reports and CI gates

```bash
agentarmor scan --url http://localhost:8000/v1/chat/completions --format html,sarif,pdf -o ./reports/
agentarmor gate --sarif ./reports/findings.sarif --fail-on HIGH,CRITICAL
```

### Config file

```bash
agentarmor scan --config AgentArmor.toml
```

See [AgentArmor.toml](AgentArmor.toml) for endpoint profiles, L0 attack goals, detection mode, and plugin directories.

---

## Desktop GUI

The Tauri v2 GUI includes:

| Screen | Purpose |
|--------|---------|
| **Home** | Scan type picker + benchmark shortcut |
| **Chatbot wizard** | Guided API scan with offline/cloud analysis |
| **Scan progress** | Live SSE probe stream |
| **Findings** | Risk scores, attack chains, evidence graph |
| **Reports** | Export HTML, SARIF, PDF, CSV, JSON |
| **Benchmark** | Model leaderboard + tools comparison |
| **Marketplace** | Install community probes |
| **Monitoring** | Schedules, drift alerts, dataset export |
| **Settings** | L0, self-play, detection, API keys |

For GUI development only (not required for end users):

```bash
agentarmor serve --port 8787
cd gui && npm install && npm run dev   # http://localhost:1420
```

See [gui/README.md](gui/README.md) for Tauri build instructions.

---

## API server

```bash
agentarmor serve --port 8787
```

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Sidecar status |
| `POST /v1/scans` | Start a scan |
| `GET /v1/scans/{id}` | Scan status + metadata |
| `GET /v1/scans/{id}/events` | SSE live progress |
| `GET /v1/findings` | List findings |
| `POST /v1/benchmarks` | Run benchmark |
| `GET /v1/marketplace/rules` | List marketplace packs |
| `POST /v1/monitoring/schedules` | Create monitor schedule |
| `POST /v1/datasets/export` | Export research JSONL |

---

## GitHub Action (CI/CD)

```yaml
name: AI Security Scan
on: [push, pull_request]

jobs:
  agentarmor:
    runs-on: ubuntu-latest
    steps:
      - uses: YashvantHange/AgentArmor/action@v1
        with:
          url: https://api.example.com/v1/chat/completions
          fail-on: HIGH,CRITICAL
```

See [action/action.yml](action/action.yml).

---

## Provider API keys

| Provider | Environment variable |
|----------|---------------------|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Gemini | `GEMINI_API_KEY` |
| Mistral | `MISTRAL_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Together | `TOGETHER_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Azure | `AZURE_API_KEY`, `AZURE_API_BASE` |
| Bedrock | `AWS_*` credentials |

Cloud enrichment and self-play require an API key for the analysis provider (configured in GUI Settings or `AgentArmor.toml`).

---

## Custom probes

Author probes with the SDK and publish to your local marketplace:

```bash
agentarmor marketplace validate probes/custom_probe.py
agentarmor marketplace publish probes/custom_probe.py --id my.probe --name "My Probe"
```

See [probes/custom_probe.py](probes/custom_probe.py) and `agentarmor.sdk.probe_sdk`.

---

## macOS

No native Mac `.app` yet (Windows desktop first). Use PyPI + CLI or dev GUI:

```bash
pip install agentarmor
agentarmor models download
agentarmor serve --port 8787
```

See [docs/MAC.md](docs/MAC.md).

---

## Development

```bash
git clone https://github.com/YashvantHange/AgentArmor.git
cd AgentArmor
pip install -e ".[dev]"
pytest
```

Optional native L1 engine (requires Rust):

```bash
cd native/l1_signatures && pip install maturin && maturin develop --release
```

Without Rust, the Python L1 fallback is used automatically.

Windows installer build (maintainers):

```powershell
powershell -File packaging/build-installer.ps1
```

---

## License

See repository license file.
