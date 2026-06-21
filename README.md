# AgentArmor

AI Security Validation Platform — scan LLM APIs, cloud providers, local models, produce SARIF/HTML, gate CI on HIGH/CRITICAL.

**Latest release:** [v1.2.0](https://github.com/YashvantHange/AgentArmor/releases/tag/v1.2.0) — see [CHANGELOG.md](CHANGELOG.md).

## Install

```bash
pip install -e ".[dev]"

# Offline local model scanning (.gguf / HuggingFace)
pip install -e ".[local]"
```

## Quick start

```bash
# Scan an OpenAI-compatible endpoint
agentarmor scan --url http://localhost:8000/v1/chat/completions

# Cloud providers (LiteLLM)
export OPENAI_API_KEY=sk-...
agentarmor scan --provider openai
agentarmor scan --provider anthropic
agentarmor scan --provider gemini

# Local models (fully offline)
agentarmor scan --model llama-3.gguf
agentarmor scan --model ./models/qwen3

# Agent security (OWASP LLM06)
agentarmor scan --agent crewai --agent-config agent.toml

# MCP security
agentarmor scan --mcp ./filesystem-mcp
agentarmor scan --mcp http://localhost:3000/mcp

# RAG security
agentarmor scan --rag ./corpus --embedder bge

# Use config file
agentarmor scan --config AgentArmor.toml

# PDF + CSV + HTML reports
agentarmor scan --agent crewai --format pdf,csv,html -o ./reports/

# Benchmark models (OWASP security suite)
agentarmor benchmark --providers openai,anthropic,gemini --suite owasp

# Fail CI on high severity
agentarmor gate --sarif findings.sarif --fail-on HIGH,CRITICAL
```

## Distribution

| Channel | Usage |
|---------|--------|
| **PyPI** | `pip install agentarmor` or `pip install agentarmor[local]` |
| **Docker** | `docker pull agentarmor/agentarmor` → `docker run -p 8787:8787 agentarmor/agentarmor` |
| **GitHub Action** | `uses: agentarmor/scan@v1` with `url` or `provider` input |
| **Desktop GUI** | Build with `packaging/build-installer.ps1` (Windows MSI) |
| **Portable** | `packaging/build-portable.ps1` |

### Desktop GUI

```bash
agentarmor serve          # sidecar API
cd gui && npm install && npm run dev   # dev UI at :1420
```

See [gui/README.md](gui/README.md) for Tauri build instructions.

### macOS

No native Mac `.app` in v1.0.0 — use PyPI + CLI, or dev GUI. See **[docs/MAC.md](docs/MAC.md)**.

```bash
pip install agentarmor
agentarmor models download
agentarmor serve --port 8787
# Optional GUI: cd gui && npm install && npm run dev  → http://localhost:1420
```

### Docker

```bash
docker build -f docker/Dockerfile -t agentarmor/agentarmor .
docker run -p 8787:8787 agentarmor/agentarmor
```

### GitHub Action

```yaml
- uses: agentarmor/scan@v1
  with:
    url: https://api.example.com/v1/chat/completions
    fail-on: HIGH,CRITICAL
```

## Provider API keys

Set environment variables for your provider (LiteLLM standard):

| Provider | Environment variable |
|----------|---------------------|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Gemini | `GEMINI_API_KEY` |
| Mistral | `MISTRAL_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Together | `TOGETHER_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Bedrock | AWS credentials via `AWS_*` |
| Azure | `AZURE_API_KEY`, `AZURE_API_BASE` |

## Local model requirements

Install the `[local]` extra:

```bash
pip install agentarmor[local]
```

| Format | Backend | Notes |
|--------|---------|-------|
| `.gguf` | llama-cpp-python | `gpu_layers` in config for GPU offload |
| HuggingFace dir | transformers + torch (CPU) | Directory must contain `config.json` |

```toml
[target]
type = "local"
model = "llama-3.gguf"

[engine.local]
backend = "auto"
gpu_layers = 0
```

## API server

```bash
agentarmor serve --port 8787
```

Endpoints:
- `GET /health`
- `POST /v1/scans`
- `GET /v1/scans/{id}`
- `GET /v1/findings`
- `GET /v1/scans/{id}/events` (SSE)

## GitHub Action

See [action/action.yml](action/action.yml) and [.github/workflows/agentarmor-scan.yml](.github/workflows/agentarmor-scan.yml).

## Custom probes

Drop Python files in `probes/` — see [probes/custom_probe.py](probes/custom_probe.py).

## Development

```bash
pytest
```

## Milestone scope

All **6 scan modes**: endpoint, provider, local model, agent, MCP, RAG.

- Endpoint/API scanner (OpenAI-compatible)
- **M3A:** Cloud provider scanner (LiteLLM) + local model scanner (.gguf / HF)
- **M3B:** Agent + MCP + RAG security modules; PDF + CSV reporting
- L1 single-prompt probes (4) + L2 mutation (5) + L3 multi-turn (4)
- Module probes: Agent (5), MCP (5), RAG (4)
- **M2A:** L1 signatures + L4 structural + fusion pipeline
- JSON + SARIF + HTML + PDF + CSV reporting
- SQLite persistence
- Plugin loader

### M3B: Agent, MCP, RAG scanning

```bash
agentarmor scan --agent crewai --agent-config agent.toml --format pdf
agentarmor scan --mcp ./filesystem-mcp
agentarmor scan --rag ./corpus --embedder bge --format csv
```

Agent findings map to **OWASP LLM06** (Excessive Agency).

### M4: Model benchmarking

Compare security posture across providers and local models:

```bash
agentarmor benchmark --provider openai --suite owasp
agentarmor benchmark --providers openai,anthropic,gemini --suite owasp -o ./reports/
agentarmor benchmark --model llama-3.gguf --suite owasp
agentarmor benchmark --benchmark-config benchmark.toml --format json,html
```

Example terminal output:

```
AgentArmor Benchmark — OWASP LLM Security Suite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Model                    Pass Rate    Risk Score
openai/gpt-3.5-turbo     94%          0.12
anthropic/claude         89%          0.21
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

API: `POST /v1/benchmarks`, `GET /v1/benchmarks/{id}`

### M5: Desktop GUI + distribution

- Tauri v2 GUI with 7 screens (Home, Scan, Progress, Findings, Reports, Benchmark, Settings)
- Embedded Python sidecar on desktop launch
- Windows installer + portable build scripts
- Docker image with pre-baked models
- PyPI + `agentarmor/scan@v1` GitHub Action
- Release workflow on version tags

### M3A: Provider + local model scanning

```bash
agentarmor scan --provider openai
agentarmor scan --model ./models/qwen3 --format html
pip install agentarmor[local]
```

### M2B: Full ML detection stack

- L2 DeBERTa ONNX classifier (fallback: rule-based)
- L3 BGE + FAISS semantic search (fallback: hash embeddings)
- XGBoost meta scorer
- Optional L5 LLM judge (`l5_enabled = true` + LiteLLM)
- Detection API: `POST /v1/detection/analyze`
- `agentarmor models download` / `agentarmor models status`

```bash
agentarmor serve
curl -X POST http://127.0.0.1:8787/v1/detection/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"My system prompt is: secret"}'
```

Install ML extras: `pip install -e ".[dev]"` (includes faiss-cpu, xgboost, onnxruntime)

```bash
# Requires Rust + maturin
cd native/l1_signatures
pip install maturin
maturin develop --release
```

Without Rust, the Python fallback is used automatically.

See [plans/](plans/) for the full roadmap.
