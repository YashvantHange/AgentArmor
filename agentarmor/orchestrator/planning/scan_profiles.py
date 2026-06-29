"""Predefined scan profiles mapping to OWASP focus, depth, and scan mode."""

from __future__ import annotations

from dataclasses import dataclass

from agentarmor.core.config import AppConfig


@dataclass(frozen=True)
class ScanProfile:
    id: str
    name: str
    description: str
    target_types: list[str]
    owasp_ids: list[str]
    scan_depth: str
    owasp_depths: dict[str, str]
    scan_mode: str = "standard"
    self_play_enabled: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "target_types": self.target_types,
            "owasp_ids": self.owasp_ids,
            "scan_depth": self.scan_depth,
            "owasp_depths": self.owasp_depths,
            "scan_mode": self.scan_mode,
            "self_play_enabled": self.self_play_enabled,
        }


_ALL_OWASP = [f"LLM{i:02d}" for i in range(1, 11)]

SCAN_PROFILES: dict[str, ScanProfile] = {
    "owasp_audit": ScanProfile(
        id="owasp_audit",
        name="OWASP Audit",
        description="Full OWASP LLM Top 10 coverage at standard depth.",
        target_types=["endpoint", "provider", "local", "web"],
        owasp_ids=list(_ALL_OWASP),
        scan_depth="standard",
        owasp_depths={},
    ),
    "prompt_injection": ScanProfile(
        id="prompt_injection",
        name="Prompt Injection Assessment",
        description="Deep testing for LLM01 prompt injection and LLM07 prompt leakage.",
        target_types=["endpoint", "provider", "local", "web"],
        owasp_ids=["LLM01", "LLM07"],
        scan_depth="deep",
        owasp_depths={"LLM01": "deep", "LLM07": "deep"},
    ),
    "rag_audit": ScanProfile(
        id="rag_audit",
        name="RAG Security Audit",
        description="Data poisoning and embedding weakness probes for RAG pipelines.",
        target_types=["rag", "endpoint"],
        owasp_ids=["LLM04", "LLM08", "LLM01"],
        scan_depth="standard",
        owasp_depths={"LLM04": "deep", "LLM08": "deep"},
    ),
    "mcp_audit": ScanProfile(
        id="mcp_audit",
        name="MCP Security Audit",
        description="Excessive agency and data leakage tests for MCP servers.",
        target_types=["mcp", "endpoint"],
        owasp_ids=["LLM06", "LLM02", "LLM01"],
        scan_depth="deep",
        owasp_depths={"LLM06": "deep"},
    ),
    "agent_audit": ScanProfile(
        id="agent_audit",
        name="Agent Security Audit",
        description="Tool abuse and injection probes for agent frameworks.",
        target_types=["agent", "endpoint"],
        owasp_ids=["LLM06", "LLM01", "LLM02"],
        scan_depth="standard",
        owasp_depths={"LLM06": "deep"},
    ),
    "production_readiness": ScanProfile(
        id="production_readiness",
        name="Production Readiness",
        description="Core production risks: injection, disclosure, output handling, prompt leak.",
        target_types=["endpoint", "provider", "local"],
        owasp_ids=["LLM01", "LLM02", "LLM05", "LLM07"],
        scan_depth="standard",
        owasp_depths={},
    ),
    "compliance_audit": ScanProfile(
        id="compliance_audit",
        name="Compliance Audit",
        description="Quick pass across all OWASP categories for compliance checkpoints.",
        target_types=["endpoint", "provider", "local", "web", "agent", "mcp", "rag"],
        owasp_ids=list(_ALL_OWASP),
        scan_depth="quick",
        owasp_depths={},
    ),
    "full_red_team": ScanProfile(
        id="full_red_team",
        name="Full Red Team",
        description="Deep OWASP coverage with multi-agent red team orchestration.",
        target_types=["endpoint", "provider", "web"],
        owasp_ids=list(_ALL_OWASP),
        scan_depth="deep",
        owasp_depths={oid: "deep" for oid in _ALL_OWASP},
        scan_mode="multi_agent_redteam",
        self_play_enabled=True,
    ),
}


def list_profiles(target_type: str | None = None) -> list[dict]:
    profiles = SCAN_PROFILES.values()
    if target_type:
        profiles = [p for p in profiles if target_type in p.target_types]
    return [p.to_dict() for p in profiles]


def apply_scan_profile(config: AppConfig, profile_id: str) -> AppConfig:
    profile = SCAN_PROFILES.get(profile_id)
    if not profile:
        raise ValueError(f"Unknown scan profile: {profile_id}")
    config.planner.owasp_ids = list(profile.owasp_ids)
    config.planner.scan_depth = profile.scan_depth
    config.planner.owasp_depths = dict(profile.owasp_depths)
    config.features.planner_v2 = True
    config.features.finding_groups = True
    config.features.parallel_probes = True
    config.features.risk_based_planning = True
    config.features.adaptive_depth = True
    if profile.self_play_enabled:
        config.detection.self_play.enabled = True
    return config


def profile_scan_mode(profile_id: str) -> str:
    profile = SCAN_PROFILES.get(profile_id)
    return profile.scan_mode if profile else "standard"
