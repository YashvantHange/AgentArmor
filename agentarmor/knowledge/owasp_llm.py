"""OWASP LLM Top 10 reference definitions for enrichment and UI."""

from __future__ import annotations

OWASP_LLM: dict[str, dict[str, str]] = {
    "LLM01": {
        "name": "Prompt Injection",
        "description": "Manipulating LLMs via crafted inputs can cause unintended actions or disclosure.",
    },
    "LLM02": {
        "name": "Sensitive Information Disclosure",
        "description": "LLMs may reveal confidential data in responses including training or system data.",
    },
    "LLM03": {
        "name": "Supply Chain",
        "description": "Vulnerable components or compromised models/plugins in the LLM supply chain.",
    },
    "LLM04": {
        "name": "Data and Model Poisoning",
        "description": "Tampered training or retrieval data that manipulates model behavior.",
    },
    "LLM05": {
        "name": "Improper Output Handling",
        "description": "Insufficient validation of LLM output before downstream use.",
    },
    "LLM06": {
        "name": "Excessive Agency",
        "description": "Excessive permissions or autonomy leading to unintended impactful actions.",
    },
    "LLM07": {
        "name": "System Prompt Leakage",
        "description": "Exposure of system instructions or hidden policies to end users.",
    },
    "LLM08": {
        "name": "Vector and Embedding Weaknesses",
        "description": "Weaknesses in embeddings enabling retrieval manipulation or data exposure.",
    },
    "LLM09": {
        "name": "Misinformation / Overreliance",
        "description": "Overreliance on LLM outputs without verification.",
    },
    "LLM10": {
        "name": "Model Theft",
        "description": "Unauthorized access, copying, or extraction of proprietary models.",
    },
}


def owasp_entries(ids: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for oid in ids:
        entry = OWASP_LLM.get(oid, {"name": oid, "description": ""})
        out.append({"id": oid, "name": entry["name"], "description": entry["description"]})
    return out
