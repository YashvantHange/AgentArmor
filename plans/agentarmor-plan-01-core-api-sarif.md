# AgentArmor Plan 01 — Milestone 1: Core + API Scanner + SARIF

**Depends on:** Nothing (greenfield start)  
**Unlocks:** Milestone 2 (Detection Pipeline)  
**Estimated effort:** ~1–2 weeks

## Goal

Ship the **first useful, open-source tool**: install via pip, scan an OpenAI-compatible API, run basic probes, produce SARIF, gate CI on HIGH/CRITICAL.

This is the Nuclei moment — useful on day one, even before ML detection.

## Shippable Outcome

```bash
pip install agentarmor
agentarmor scan --url http://localhost:8000/v1/chat/completions
agentarmor scan --config AgentArmor.toml --format sarif -o findings.sarif
agentarmor gate --sarif findings.sarif --fail-on HIGH,CRITICAL
```

GitHub Action uploads SARIF to Security tab.

---

## Scope

### In scope
- Monorepo scaffold (`uv`, `pyproject.toml`, package layout)
- Config system (`AgentArmor.toml` + CLI flags)
- Domain models (Pydantic): `Target`, `ProbeResult`, `Finding`, `Scan`, `Severity`, `Decision`
- SQLite schema: `scans`, `findings`, `templates`, `targets`, `metrics`
- Plugin loader ABCs + empty drop-in dirs
- FastAPI shell: `POST /v1/scans`, `GET /v1/scans/{id}`, `GET /v1/findings`, health, SSE progress
- Typer CLI: `scan`, `serve`, `db migrate`, `gate`
- **Endpoint / API engine** (MVP #1): httpx, rate limit, OpenAI-compat adapter
- **Attack orchestrator L1 only**: single-prompt probes (ignore-instructions, reveal-system-prompt, hidden-rules, act-as-root)
- **Detection stub**: rule-based scoring (regex in Python) — replaced by full pipeline in M2
- **Reporting**: JSON + SARIF 2.1
- **OWASP tags** on findings: LLM01, LLM02 (basic mapping)
- Example GitHub Action workflow + composite action skeleton
- pytest + mock OpenAI-compat target server

### Out of scope (deferred to later milestones)
- Rust L1, ONNX, FAISS, XGBoost (M2)
- Provider / local model / agent / MCP / RAG scanners (M3)
- HTML/PDF reports (M3/M4)
- Tauri GUI (M4)
- Windows packaging (M4)

---

## File Checklist

```
AgentArmor/
├── pyproject.toml
├── AgentArmor.toml
├── README.md
├── agentarmor/
│   ├── __init__.py
│   ├── cli/main.py
│   ├── api/app.py
│   ├── api/routes/scans.py
│   ├── core/config.py
│   ├── core/models.py
│   ├── core/events.py
│   ├── db/models.py
│   ├── db/session.py
│   ├── engines/endpoint/client.py
│   ├── engines/endpoint/adapter.py
│   ├── orchestrator/runner.py
│   ├── orchestrator/probes/l1_single.py
│   ├── detection/stub.py          # temporary rule-based scorer
│   ├── reporting/json_reporter.py
│   ├── reporting/sarif_reporter.py
│   ├── reporting/owasp.py
│   └── plugins/base.py
├── probes/ detectors/ reporters/ engines/ plugins/
├── action/action.yml
├── .github/workflows/ci.yml
├── .github/workflows/agentarmor-scan.yml
└── tests/
    ├── test_config.py
    ├── test_endpoint_engine.py
    ├── test_sarif.py
    └── fixtures/mock_openai_server.py
```

---

## Implementation Steps

### Step 1 — Scaffold
- `uv init` workspace, Python 3.12
- Dependencies: `typer`, `fastapi`, `uvicorn`, `httpx`, `sqlalchemy`, `alembic`, `pydantic-settings`, `tomli`, `jinja2` (stub for later)
- `agentarmor` console script entry point

### Step 2 — Config + models
- Load `AgentArmor.toml`; env var substitution (`${API_KEY}`)
- CLI flags: `--config`, `--url`, `--format`, `-o`
- Pydantic models for scan lifecycle

### Step 3 — Database
- SQLAlchemy models for 5 tables
- Alembic initial migration
- `agentarmor db migrate` command

### Step 4 — Endpoint engine
- Async httpx with timeout, retries, rate limit
- OpenAI chat/completions request/response normalizer
- Output: `ProbeResult { request, response, metadata, latency_ms }`

### Step 5 — Orchestrator (L1 probes)
- 4 built-in single-prompt probes, OWASP-tagged
- Sequential execution with concurrency cap
- Emit SSE events: `probe.started`, `probe.completed`, `scan.completed`

### Step 6 — Detection stub
- Python regex rules for obvious jailbreaks / leakage patterns
- Output: `risk_score`, `severity`, `decision` (PASS/WARN/FAIL)
- Interface designed so M2 drops in real pipeline without API changes

### Step 7 — Reporting
- JSON: full scan artifact
- SARIF 2.1: one result per finding, OWASP rule IDs in `properties`
- `agentarmor gate`: parse SARIF, exit 1 on configured severities

### Step 8 — FastAPI + CLI integration
- `agentarmor scan` runs orchestrator → detection → reporters → SQLite
- `agentarmor serve` for local API (prep for GUI in M4)

### Step 9 — CI
- `action/action.yml`: install, scan, upload SARIF, gate
- `.github/workflows/ci.yml`: pytest on PR

---

## Config Example

```toml
[target]
type = "endpoint"
url = "http://localhost:8000/v1/chat/completions"
headers = { Authorization = "Bearer ${API_KEY}" }

[engine.endpoint]
rate_limit_rps = 5
timeout_s = 30

[detection]
fail_on = ["HIGH", "CRITICAL"]

[reporting]
formats = ["json", "sarif"]
output_dir = "./reports"
```

---

## Definition of Done

- [ ] `pip install -e .` succeeds on Windows/Linux
- [ ] `agentarmor scan --url <mock-server>` completes with findings in SQLite
- [ ] SARIF file validates and uploads to GitHub Security tab
- [ ] `agentarmor gate --fail-on HIGH,CRITICAL` exits non-zero on bad findings
- [ ] 4 L1 probes run against mock OpenAI-compat server
- [ ] Plugin loader discovers drop-in probe from `probes/` dir
- [ ] pytest passes in CI
- [ ] README documents install, scan, and GitHub Action setup

## Handoff to Milestone 2A

M2A replaces `detection/stub.py` with Rust L1 + L4 structural analysis and a simple fusion scorer. The `ProbeResult` → `Finding` interface must remain stable for M2B to extend with ML layers.
