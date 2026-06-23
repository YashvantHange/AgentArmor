"""Domain models for web scans."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ScanDepth(str, Enum):
    STANDARD = "standard"
    MULTI_AGENTIC = "multi_agentic"


class AuthMode(str, Enum):
    NONE = "none"
    MANUAL_SESSION = "manual_session"


class WidgetCandidate(BaseModel):
    input_selector: str
    send_selector: str | None = None
    frame_path: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    framework: str | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    tag_name: str = ""
    placeholder: str = ""


class ToolHint(BaseModel):
    name: str
    source: str = "dom"
    confidence: float = 0.5


class MCPDetectionResult(BaseModel):
    mcp_enabled: bool = False
    confidence: float = 0.0
    servers: list[str] = Field(default_factory=list)
    jsonrpc_detected: bool = False
    methods_observed: list[str] = Field(default_factory=list)


class MemoryDetectionResult(BaseModel):
    memory_enabled: bool = False
    confidence: float = 0.0
    indicators: list[str] = Field(default_factory=list)


class A2ADetectionResult(BaseModel):
    a2a_enabled: bool = False
    confidence: float = 0.0
    registry_urls: list[str] = Field(default_factory=list)


class CapabilityMap(BaseModel):
    framework: str | None = None
    rag: bool = False
    memory: bool = False
    mcp: bool = False
    a2a: bool = False
    tools: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    memory_indicators: list[str] = Field(default_factory=list)
    agentic_score: float = 0.0
    risk_score: float = 0.0
    risk_reasons: list[str] = Field(default_factory=list)


class AgentRiskProfile(BaseModel):
    tool_count: int = 0
    rag_enabled: bool = False
    memory_enabled: bool = False
    mcp_enabled: bool = False
    external_actions: bool = False
    agentic_score: float = 0.0
    risk_score: float = 0.0
    risk_reasons: list[str] = Field(default_factory=list)
    risk_factors: dict[str, float] = Field(default_factory=dict)


class DiscoveryResult(BaseModel):
    page_url: str
    widget: WidgetCandidate | None = None
    framework: str | None = None
    candidates: list[WidgetCandidate] = Field(default_factory=list)
    screenshot_path: str | None = None
    error: str | None = None
    capability_map: CapabilityMap | None = None
    agent_risk: AgentRiskProfile | None = None


class WebProbeDef(BaseModel):
    id: str
    name: str
    owasp: list[str]
    prompt: str
    turns: int = 1
    follow_up_prompt: str | None = None


class StableResponse(BaseModel):
    text: str
    complete: bool = True
    wait_ms: float = 0.0
    stream_detected: bool = False
    partial: bool = False


class WebScanMetadata(BaseModel):
    scan_kind: str = "web"
    page_url: str
    scan_depth: ScanDepth = ScanDepth.STANDARD
    auth_mode: AuthMode = AuthMode.NONE
    discovery: dict[str, Any] = Field(default_factory=dict)
    owasp_filters: list[str] = Field(default_factory=list)
    capability_map: dict[str, Any] = Field(default_factory=dict)
