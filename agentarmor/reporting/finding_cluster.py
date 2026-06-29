"""Finding clustering, root-cause labels, and replay bundles."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Finding
from agentarmor.orchestrator.planning.probe_catalog import probe_issue_type

ROOT_CAUSE_LABELS: dict[str, str] = {
    "prompt_injection": "Prompt Injection",
    "sensitive_disclosure": "Sensitive Information Disclosure",
    "output_handling": "Improper Output Handling",
    "overreliance": "Misinformation / Overreliance",
    "supply_chain": "Supply Chain Risk",
    "data_poisoning": "Data and Model Poisoning",
    "embedding_weakness": "Vector and Embedding Weaknesses",
    "model_theft": "Model Theft",
    "excessive_agency": "Excessive Agency",
    "other": "Security Issue",
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())[:500]


def evidence_fingerprint(finding: Finding) -> str:
    parts = [_normalize_text(finding.response_excerpt)]
    for ev in finding.evidence[:3]:
        parts.append(_normalize_text(ev))
    primary_owasp = finding.owasp[0] if finding.owasp else "none"
    issue = probe_issue_type(finding.probe_id)
    raw = "|".join(parts) + f"|{primary_owasp}|{issue}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def root_cause_for(finding: Finding) -> str:
    meta_rc = finding.metadata.get("root_cause")
    if isinstance(meta_rc, str) and meta_rc:
        return meta_rc
    return probe_issue_type(finding.probe_id)


def detection_confidence(finding: Finding) -> float:
    if isinstance(finding.metadata.get("detection_confidence"), (int, float)):
        return float(finding.metadata["detection_confidence"])
    layers = finding.metadata.get("detection_layers", {})
    if isinstance(layers, dict):
        meta = layers.get("meta", {})
        if isinstance(meta, dict) and "confidence" in meta:
            return float(meta["confidence"])
        judge = layers.get("l5_judge", {})
        if isinstance(judge, dict) and judge.get("confidence"):
            return float(judge["confidence"])
    ra = finding.risk_assessment
    if ra is not None:
        return min(1.0, max(0.0, ra.confidence))
    return min(1.0, max(0.0, finding.risk_score))


def build_replay_bundle(
    finding: Finding,
    config: AppConfig | None = None,
) -> dict[str, Any]:
    conversation = finding.metadata.get("conversation")
    if not isinstance(conversation, list):
        conversation = [{"role": "user", "content": finding.request_summary}]

    url = ""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if config and config.target.url:
        url = config.target.url
        if config.target.headers:
            headers.update(
                {k: v for k, v in config.target.headers.items() if k.lower() != "authorization"}
            )

    body = {
        "model": (config.target.model if config else None) or "gpt-3.5-turbo",
        "messages": conversation,
    }
    body_json = json.dumps(body, ensure_ascii=False)
    safe_json = body_json.replace("'", "'\"'\"'")
    curl = (
        f'curl -X POST "{url}" '
        f'-H "Content-Type: application/json" '
        f"-d '{safe_json}'"
        if url
        else f"# Set target URL\n# curl -X POST \"$URL\" -H \"Content-Type: application/json\" -d @request.json"
    )

    return {
        "prompt": finding.request_summary,
        "request": body,
        "response": finding.response_excerpt,
        "headers": headers,
        "conversation": conversation,
        "curl": curl,
    }


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", _normalize_text(text)))


def text_similarity(a: str, b: str) -> float:
    """Jaccard similarity for semantic-ish clustering without embeddings."""
    sa, sb = _token_set(a), _token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _same_cluster_family(a: Finding, b: Finding) -> bool:
    if root_cause_for(a) == root_cause_for(b):
        return True
    oa = a.owasp[0] if a.owasp else ""
    ob = b.owasp[0] if b.owasp else ""
    return bool(oa and oa == ob)


def _merge_semantic_buckets(buckets: dict[str, list[Finding]], threshold: float = 0.65) -> dict[str, list[Finding]]:
    """Merge fingerprint buckets with high response similarity and same OWASP/root cause."""
    keys = list(buckets.keys())
    merged: dict[str, list[Finding]] = {}
    used: set[str] = set()

    for i, ki in enumerate(keys):
        if ki in used:
            continue
        group = list(buckets[ki])
        used.add(ki)
        rep = group[0]

        for kj in keys[i + 1 :]:
            if kj in used:
                continue
            other = buckets[kj]
            if not _same_cluster_family(rep, other[0]):
                continue
            if text_similarity(rep.response_excerpt, other[0].response_excerpt) >= threshold:
                group.extend(other)
                used.add(kj)

        merged[ki] = group
    return merged


def cluster_findings(
    findings: list[Finding],
    config: AppConfig | None = None,
    *,
    semantic_merge: bool = True,
) -> list[Finding]:
    """Group findings by fingerprint; optionally merge semantically similar clusters."""
    if not findings:
        return []

    buckets: dict[str, list[Finding]] = {}
    for f in findings:
        fp = evidence_fingerprint(f)
        buckets.setdefault(fp, []).append(f)

    if semantic_merge:
        buckets = _merge_semantic_buckets(buckets)

    result: list[Finding] = []
    for fp, group in buckets.items():
        group.sort(key=lambda x: (-x.risk_score, x.probe_id))
        primary = group[0]
        related = [g.probe_id for g in group[1:]]
        rc = root_cause_for(primary)
        primary.metadata["cluster_id"] = fp
        primary.metadata["cluster_size"] = len(group)
        primary.metadata["related_probe_ids"] = related
        primary.metadata["root_cause"] = rc
        primary.metadata["root_cause_label"] = ROOT_CAUSE_LABELS.get(rc, rc)
        primary.metadata["detection_confidence"] = detection_confidence(primary)
        primary.metadata["replay"] = build_replay_bundle(primary, config)
        primary.metadata["is_cluster_primary"] = True
        result.append(primary)

        for sibling in group[1:]:
            sibling.metadata["cluster_id"] = fp
            sibling.metadata["cluster_size"] = len(group)
            sibling.metadata["related_probe_ids"] = [primary.probe_id] + [
                g.probe_id for g in group if g.id not in (primary.id, sibling.id)
            ]
            sibling.metadata["root_cause"] = rc
            sibling.metadata["root_cause_label"] = ROOT_CAUSE_LABELS.get(rc, rc)
            sibling.metadata["detection_confidence"] = detection_confidence(sibling)
            sibling.metadata["replay"] = build_replay_bundle(sibling, config)
            sibling.metadata["is_cluster_primary"] = False
            sibling.metadata["clustered_under"] = primary.probe_id
            result.append(sibling)

    result.sort(key=lambda x: (-x.risk_score, x.probe_id))
    return result


def grouped_findings_api(findings: list[Finding]) -> list[dict[str, Any]]:
    """Return one card per cluster (primary only)."""
    primaries = [f for f in findings if f.metadata.get("is_cluster_primary", True)]
    if not primaries:
        primaries = findings
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for f in primaries:
        cid = f.metadata.get("cluster_id", f.id)
        if cid in seen:
            continue
        seen.add(cid)
        payload = f.model_dump(mode="json")
        payload["cluster_size"] = f.metadata.get("cluster_size", 1)
        payload["related_probe_ids"] = f.metadata.get("related_probe_ids", [])
        payload["root_cause"] = f.metadata.get("root_cause")
        payload["root_cause_label"] = f.metadata.get("root_cause_label")
        payload["detection_confidence"] = f.metadata.get("detection_confidence")
        payload["replay"] = f.metadata.get("replay")
        out.append(payload)
    return out
