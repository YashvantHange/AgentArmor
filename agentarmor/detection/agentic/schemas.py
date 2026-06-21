"""Pydantic schemas for multi-agent enrichment output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TriageResult(BaseModel):
    category: str = "other"  # injection | disclosure | agency | rag | other
    rationale: str = ""


class AnalystResult(BaseModel):
    narrative: str = ""
    evidence_quotes: list[str] = Field(default_factory=list)
    technique: str = ""


class OwaspMappingResult(BaseModel):
    owasp_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    rationale: str = ""


class RemediationResult(BaseModel):
    steps: list[str] = Field(default_factory=list)


class SynthesisResult(BaseModel):
    summary: str = ""
    analyst_notes: str = ""


class AgenticEnrichment(BaseModel):
    triage: TriageResult | None = None
    analyst: AnalystResult | None = None
    owasp: OwaspMappingResult | None = None
    remediation: RemediationResult | None = None
    synthesis: SynthesisResult | None = None
