"""Configuration loading from TOML and CLI overrides."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from agentarmor.core.models import Target, TargetType

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _substitute_env(value: Any) -> Any:
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            return os.environ.get(match.group(1), "")

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    return value


def _sanitize_target_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Drop Authorization when Bearer token is empty (avoids httpx illegal header)."""
    cleaned = dict(headers or {})
    auth = cleaned.get("Authorization", "").strip()
    if auth.lower() in ("", "bearer", "bearer "):
        cleaned.pop("Authorization", None)
    return cleaned


class EndpointEngineConfig(BaseModel):
    rate_limit_rps: float = 5.0
    timeout_s: float = 30.0
    profile: str = "auto"  # auto | openai | openai_compat | custom | message_reply | ...
    detected_profile: str | None = None
    request_template: str | None = None
    response_path: str | None = None
    extra_body: dict[str, Any] = Field(default_factory=dict)
    http_method: str = "POST"


class ProviderEngineConfig(BaseModel):
    rate_limit_rps: float = 5.0


class LocalEngineConfig(BaseModel):
    backend: str = "auto"  # auto | llama_cpp | transformers
    gpu_layers: int = 0
    memory_warn_gb: float = 8.0


class AgentModuleConfig(BaseModel):
    canary_secret: str = "CANARY_SECRET_9f3a2b"
    timeout_s: float = 30.0


class McpModuleConfig(BaseModel):
    transport: str = "stdio"
    timeout_s: float = 30.0


class RagModuleConfig(BaseModel):
    embedder: str = "bge"
    top_k: int = 3
    chunk_size: int = 512


class FusionWeightsConfig(BaseModel):
    l1: float = 0.6
    l4: float = 0.4


class AgenticConfig(BaseModel):
    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    api_key_env: str = "AGENTARMOR_ANALYSIS_API_KEY"
    max_findings_per_scan: int = 20
    temperature: float = 0.1
    max_output_tokens: int = 800


class SelfPlayConfig(BaseModel):
    enabled: bool = False
    max_rounds: int = 20
    stop_on_success: bool = True
    defender_enabled: bool = False
    discovery_enabled: bool = True
    goals: list[str] = Field(
        default_factory=lambda: ["extract_system_prompt", "bypass_safety"]
    )


class L0AttackConfig(BaseModel):
    enabled: bool = True
    max_variants_per_goal: int = 100
    cloud_mutations_enabled: bool = True
    cloud_mutations_per_goal: int = 10
    goals: list[str] = Field(
        default_factory=lambda: [
            "extract_system_prompt",
            "bypass_safety",
            "exfiltrate_secrets",
            "trigger_tool_abuse",
            "poison_memory",
        ]
    )
    suites: list[str] = Field(
        default_factory=lambda: [
            "prompt_leak",
            "model_theft",
            "memory_poison",
            "poisoning",
        ]
    )


class DetectionConfig(BaseModel):
    mode: str = "local"  # local | api | hybrid
    analysis_mode: str = "offline"  # offline | cloud
    l0: L0AttackConfig = Field(default_factory=L0AttackConfig)
    self_play: SelfPlayConfig = Field(default_factory=SelfPlayConfig)
    api_url: str = "http://127.0.0.1:8787"
    agentic: AgenticConfig = Field(default_factory=AgenticConfig)
    redteam_plugins: list[str] = Field(
        default_factory=lambda: [
            "security:prompt-injection",
            "security:disclosure",
            "trust:refusal-bypass",
        ]
    )
    l1_enabled: bool = True
    l2_enabled: bool = True
    l3_enabled: bool = True
    l4_enabled: bool = True
    meta_enabled: bool = True
    l5_enabled: bool = False
    judge_model: str = "gpt-3.5-turbo"
    confidence_judge_band: tuple[float, float] = (0.4, 0.6)
    model_dir: str = "~/.agentarmor/models"
    l3_similarity_threshold: float = 0.82
    fusion_weights: FusionWeightsConfig = Field(default_factory=FusionWeightsConfig)
    warn_threshold: float = 0.4
    fail_threshold: float = 0.7
    fail_on: list[str] = Field(default_factory=lambda: ["HIGH", "CRITICAL"])

    @field_validator("confidence_judge_band", mode="before")
    @classmethod
    def _coerce_judge_band(cls, v: object) -> tuple[float, float]:
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return (float(v[0]), float(v[1]))
        return (0.4, 0.6)


class ReportingConfig(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["json", "sarif"])
    output_dir: str = "./reports"


class WebScanRiskWeights(BaseModel):
    per_tool: float = 0.5
    per_tool_cap: float = 3.0
    external_actions: float = 2.0
    rag: float = 1.5
    memory: float = 1.5
    mcp: float = 2.0
    mcp_tools_combo: float = 1.0
    high_agentic: float = 1.0
    high_agentic_threshold: float = 0.8


class WebScanConfig(BaseModel):
    max_scans_per_day: int = 10
    max_probes_per_scan: int = 30
    multi_agentic_max_probes: int = 45
    llm_discovery_min_confidence: float = 0.4
    llm_discovery_on_miss: bool = False
    max_concurrent_browsers: int = 2
    session_ttl_hours: int = 24
    timeout_s: float = 60.0
    stable_ms: int = 1500
    max_wait_ms: int = 45000
    allowlist: list[str] = Field(default_factory=list)
    blocklist: list[str] = Field(default_factory=list)
    risk_weights: WebScanRiskWeights = Field(default_factory=WebScanRiskWeights)


class RedTeamBudgetConfig(BaseModel):
    max_tokens: int = 50_000
    max_cost_usd: float = 2.0
    warn_at_pct: float = 80.0


class RedTeamMultiAgentConfig(BaseModel):
    enabled: bool = True
    max_rounds: int = 12
    stop_on_vulnerability: bool = True


class RedTeamConfig(BaseModel):
    multi_agent: RedTeamMultiAgentConfig = Field(default_factory=RedTeamMultiAgentConfig)
    budget: RedTeamBudgetConfig = Field(default_factory=RedTeamBudgetConfig)


class AppConfig(BaseModel):
    target: Target = Field(default_factory=Target)
    engine_endpoint: EndpointEngineConfig = Field(default_factory=EndpointEngineConfig)
    engine_provider: ProviderEngineConfig = Field(default_factory=ProviderEngineConfig)
    engine_local: LocalEngineConfig = Field(default_factory=LocalEngineConfig)
    module_agent: AgentModuleConfig = Field(default_factory=AgentModuleConfig)
    module_mcp: McpModuleConfig = Field(default_factory=McpModuleConfig)
    module_rag: RagModuleConfig = Field(default_factory=RagModuleConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    webscan: WebScanConfig = Field(default_factory=WebScanConfig)
    redteam: RedTeamConfig = Field(default_factory=RedTeamConfig)
    database_url: str = "sqlite:///./agentarmor.db"
    plugin_dirs: list[str] = Field(
        default_factory=lambda: ["probes", "detectors", "reporters", "engines", "plugins"]
    )


def load_config(path: Path | None = None) -> AppConfig:
    if path is None or not path.exists():
        return AppConfig()

    raw = _substitute_env(_load_toml(path))
    target_raw = raw.get("target", {})
    engine_section = raw.get("engine", {})
    if not isinstance(engine_section, dict):
        engine_section = {}
    engine_endpoint_raw = engine_section.get("endpoint", {})
    engine_provider_raw = engine_section.get("provider", {})
    engine_local_raw = engine_section.get("local", {})
    module_section = raw.get("module", {})
    if not isinstance(module_section, dict):
        module_section = {}

    target = Target(
        type=TargetType(target_raw.get("type", "endpoint")),
        url=target_raw.get("url"),
        headers=_sanitize_target_headers(target_raw.get("headers", {})),
        model=target_raw.get("model", "gpt-3.5-turbo"),
        provider=target_raw.get("provider"),
        agent_framework=target_raw.get("agent_framework") or target_raw.get("agent"),
        agent_config=target_raw.get("agent_config"),
        mcp_target=target_raw.get("mcp") or target_raw.get("mcp_target"),
        mcp_transport=target_raw.get("mcp_transport", "stdio"),
        rag_corpus=target_raw.get("rag") or target_raw.get("rag_corpus"),
        embedder=target_raw.get("embedder", "bge"),
    )

    return AppConfig(
        target=target,
        engine_endpoint=EndpointEngineConfig(**engine_endpoint_raw)
        if engine_endpoint_raw
        else EndpointEngineConfig(),
        engine_provider=ProviderEngineConfig(**engine_provider_raw)
        if engine_provider_raw
        else ProviderEngineConfig(),
        engine_local=LocalEngineConfig(**engine_local_raw)
        if engine_local_raw
        else LocalEngineConfig(),
        module_agent=AgentModuleConfig(**module_section.get("agent", {})),
        module_mcp=McpModuleConfig(**module_section.get("mcp", {})),
        module_rag=RagModuleConfig(**module_section.get("rag", {})),
        detection=_load_detection_config(raw.get("detection", {})),
        reporting=ReportingConfig(**raw.get("reporting", {})),
        webscan=_load_webscan_config(raw.get("webscan", {})),
        redteam=_load_redteam_config(raw.get("redteam", {})),
    )


def _load_webscan_config(raw: object) -> WebScanConfig:
    if not isinstance(raw, dict) or not raw:
        return WebScanConfig()
    data = dict(raw)
    rw = data.pop("risk_weights", None)
    if isinstance(rw, dict):
        data["risk_weights"] = WebScanRiskWeights(**rw)
    return WebScanConfig(**data)


def _load_redteam_config(raw: object) -> RedTeamConfig:
    if not isinstance(raw, dict) or not raw:
        return RedTeamConfig()
    data = dict(raw)
    budget_raw = data.pop("budget", None)
    multi_raw = data.pop("multi_agent", None)
    if isinstance(budget_raw, dict):
        data["budget"] = RedTeamBudgetConfig(**budget_raw)
    if isinstance(multi_raw, dict):
        data["multi_agent"] = RedTeamMultiAgentConfig(**multi_raw)
    return RedTeamConfig(**data)


def _load_detection_config(raw: object) -> DetectionConfig:
    if not isinstance(raw, dict) or not raw:
        return DetectionConfig()
    data = dict(raw)
    agentic_raw = data.pop("agentic", None)
    if isinstance(agentic_raw, dict):
        data["agentic"] = AgenticConfig(**agentic_raw)
    l0_raw = data.pop("l0", None)
    if isinstance(l0_raw, dict):
        data["l0"] = L0AttackConfig(**l0_raw)
    self_play_raw = data.pop("self_play", None)
    if isinstance(self_play_raw, dict):
        data["self_play"] = SelfPlayConfig(**self_play_raw)
    return DetectionConfig(**data)


def apply_analysis_options(
    config: AppConfig,
    *,
    analysis_mode: str | None = None,
    analysis_provider: str | None = None,
    analysis_model: str | None = None,
    analysis_api_key: str | None = None,
    auth_token: str | None = None,
) -> AppConfig:
    if analysis_mode:
        config.detection.analysis_mode = analysis_mode
        config.detection.agentic.enabled = analysis_mode == "cloud"
    if analysis_provider:
        config.detection.agentic.provider = analysis_provider
    if analysis_model:
        config.detection.agentic.model = analysis_model
    if analysis_api_key:
        config.detection.agentic.api_key = analysis_api_key
    elif config.detection.analysis_mode == "cloud":
        env_key = os.environ.get(config.detection.agentic.api_key_env, "")
        if env_key:
            config.detection.agentic.api_key = env_key
    if auth_token and auth_token.strip():
        config.target.headers = _sanitize_target_headers(config.target.headers)
        token = auth_token.strip()
        if token.lower().startswith("bearer "):
            config.target.headers["Authorization"] = token
        else:
            config.target.headers["Authorization"] = f"Bearer {token}"
    else:
        config.target.headers = _sanitize_target_headers(config.target.headers)
    return config


def apply_endpoint_options(
    config: AppConfig,
    *,
    endpoint_profile: str | None = None,
    request_template: str | None = None,
    response_path: str | None = None,
    extra_body: dict[str, Any] | None = None,
    redteam_plugins: list[str] | None = None,
) -> AppConfig:
    if endpoint_profile:
        config.engine_endpoint.profile = endpoint_profile
        config.engine_endpoint.detected_profile = None
    if request_template is not None:
        config.engine_endpoint.request_template = request_template
        if endpoint_profile is None:
            config.engine_endpoint.profile = "custom"
    if response_path is not None:
        config.engine_endpoint.response_path = response_path
    if extra_body:
        config.engine_endpoint.extra_body = dict(extra_body)
    if redteam_plugins:
        config.detection.redteam_plugins = list(redteam_plugins)
    return config


def apply_redteam_options(
    config: AppConfig,
    *,
    l0_enabled: bool | None = None,
    max_variants_per_goal: int | None = None,
    l0_suites: list[str] | None = None,
    cloud_mutations_enabled: bool | None = None,
    self_play_enabled: bool | None = None,
    self_play_max_rounds: int | None = None,
    self_play_stop_on_success: bool | None = None,
    self_play_discovery_enabled: bool | None = None,
    self_play_defender_enabled: bool | None = None,
) -> AppConfig:
    if l0_enabled is not None:
        config.detection.l0.enabled = l0_enabled
    if max_variants_per_goal is not None:
        config.detection.l0.max_variants_per_goal = max(1, max_variants_per_goal)
    if l0_suites is not None:
        config.detection.l0.suites = list(l0_suites)
    if cloud_mutations_enabled is not None:
        config.detection.l0.cloud_mutations_enabled = cloud_mutations_enabled
    if self_play_enabled is not None:
        config.detection.self_play.enabled = self_play_enabled
    if self_play_max_rounds is not None:
        config.detection.self_play.max_rounds = max(1, self_play_max_rounds)
    if self_play_stop_on_success is not None:
        config.detection.self_play.stop_on_success = self_play_stop_on_success
    if self_play_discovery_enabled is not None:
        config.detection.self_play.discovery_enabled = self_play_discovery_enabled
    if self_play_defender_enabled is not None:
        config.detection.self_play.defender_enabled = self_play_defender_enabled
    return config


def apply_multi_agent_redteam_options(
    config: AppConfig,
    *,
    scan_mode: str | None = None,
    max_rounds: int | None = None,
    max_tokens: int | None = None,
    max_cost_usd: float | None = None,
) -> AppConfig:
    if max_rounds is not None:
        config.redteam.multi_agent.max_rounds = max(1, max_rounds)
    if max_tokens is not None:
        config.redteam.budget.max_tokens = max(1000, max_tokens)
    if max_cost_usd is not None:
        config.redteam.budget.max_cost_usd = max(0.01, max_cost_usd)
    if scan_mode == "multi_agent_redteam":
        config.detection.analysis_mode = "cloud"
        config.detection.agentic.enabled = True
        if not config.detection.agentic.api_key:
            env_key = os.environ.get(config.detection.agentic.api_key_env, "")
            if env_key:
                config.detection.agentic.api_key = env_key
    return config


def merge_cli_target(
    config: AppConfig,
    *,
    url: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    agent: str | None = None,
    mcp: str | None = None,
    rag: str | None = None,
    embedder: str | None = None,
    agent_config: str | None = None,
) -> AppConfig:
    flags = [f for f in (url, provider, model, agent, mcp, rag) if f]
    if len(flags) > 1:
        raise ValueError(
            "Only one scan target may be specified "
            "(--url, --provider, --model, --agent, --mcp, or --rag)."
        )

    if url:
        config.target.url = url
        config.target.type = TargetType.ENDPOINT
    elif provider:
        config.target.provider = provider
        config.target.type = TargetType.PROVIDER
    elif model:
        config.target.model = model
        config.target.type = TargetType.LOCAL
    elif agent:
        config.target.agent_framework = agent
        config.target.type = TargetType.AGENT
        if agent_config:
            config.target.agent_config = agent_config
    elif mcp:
        config.target.mcp_target = mcp
        config.target.type = TargetType.MCP
    elif rag:
        config.target.rag_corpus = rag
        config.target.type = TargetType.RAG
    if embedder:
        config.target.embedder = embedder
        config.module_rag.embedder = embedder
    return config
