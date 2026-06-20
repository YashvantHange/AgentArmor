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


class EndpointEngineConfig(BaseModel):
    rate_limit_rps: float = 5.0
    timeout_s: float = 30.0


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


class DetectionConfig(BaseModel):
    mode: str = "local"  # local | api | hybrid
    api_url: str = "http://127.0.0.1:8787"
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
        headers=target_raw.get("headers", {}),
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
        detection=DetectionConfig(**raw.get("detection", {})),
        reporting=ReportingConfig(**raw.get("reporting", {})),
    )


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
