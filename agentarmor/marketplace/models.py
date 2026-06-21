"""Marketplace data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RuleManifest(BaseModel):
    id: str
    name: str
    version: str = "1.0.0"
    author: str = "AgentArmor"
    description: str = ""
    category: str = "probe"  # probe | assertion | suite
    owasp: list[str] = Field(default_factory=list)
    probe_file: str = ""
    tags: list[str] = Field(default_factory=list)
    builtin: bool = True


class InstalledRule(BaseModel):
    id: str
    manifest_id: str
    name: str
    version: str
    install_path: str
    installed_at: str
