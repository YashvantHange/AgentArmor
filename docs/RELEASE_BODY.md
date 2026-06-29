## AgentArmor v1.3.1 — Detection stack overhaul

Release focused on detection accuracy, reproducibility, and enterprise-ready policy hooks.

### Added
- **Echo-aware scoring** — L1/L2 echo stripping; tiered compliance assertions (Sprint 1)
- **ONNX/FAISS hardening** — tokenizer bundles, index versioning, honest fallback (Sprint 2)
- **Regression harness** — 70 fixtures, `agentarmor eval detection`, baseline JSON (Sprint 2)
- **Unified judge** — `JudgeService` with legacy config migration (Sprint 3)
- **Rule catalog** — single YAML source for L1/L2/L4 (Sprint 3)
- **Per-probe thresholds** + **meta calibration** scaffold (Sprint 4)
- **Detector plugins** — SDK, marketplace `--trust`, LLM-rubric assertions (Sprint 5)
- **Webscan partial-stream gate** — completeness-aware WARN/FAIL (Sprint 5)
- **Policy engine, evidence spans, version stamps, active-learning queue** (P5)

### Fixed
- Meta scorer hard-signal floor for clear L1/L4 hits
- Webscan partial streams no longer blanket-WARN when hard outcomes are present

---

## Windows (recommended)

Download **AgentArmor_1.3.1_x64-setup.exe** or **AgentArmor_1.3.1_x64_en-US.msi** from the assets below.

1. Run the installer
2. Open **AgentArmor** — no Python install required
3. Choose a scan profile → run scan → review grouped findings → download reports
