# Benchmark Suites

Versioned security probe suites for `agentarmor benchmark`.

## Available suites

| Alias | File | Description |
|-------|------|-------------|
| `owasp` | `owasp-llm-v1.yaml` | OWASP LLM01/02/05/06/09 coverage |

## Usage

```bash
agentarmor benchmark --provider openai --suite owasp
agentarmor benchmark --providers openai,anthropic,gemini --suite owasp -o ./reports/
agentarmor benchmark --config benchmark.toml
```

## Suite format

Suites are YAML files with OWASP categories, probe IDs, weights, and scoring rules.
Probe IDs match orchestrator probes (`l1.*`, `l2.*`, `l3.*`).
