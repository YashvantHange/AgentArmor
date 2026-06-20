# AgentArmor Model Assets

Bootstrap models are generated on first run in `~/.agentarmor/models/`:

| File | Description |
|------|-------------|
| `meta.ubj` | XGBoost meta classifier (when xgboost available) |
| `meta.json` | Linear meta fallback (always created) |
| `exploit_phrases.json` | Known exploit output phrases for L3 semantic index |
| `exploit.faiss` | FAISS index (requires `faiss-cpu`) |

Optional downloads via `agentarmor models download`:

| File | Description |
|------|-------------|
| `deberta-v3-security.onnx` | L2 DeBERTa 5-class classifier |
| `bge-small-en-v1.5.onnx` | L3 BGE embedding model |

Without downloaded ONNX models, L2/L3 use rule-based and hash-embedding fallbacks.
