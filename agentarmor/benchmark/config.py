"""Benchmark configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentarmor.benchmark.models import BenchmarkTarget


class BenchmarkFileConfig(BaseModel):
    suite: str = "owasp"
    targets: list[BenchmarkTarget] = Field(default_factory=list)


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_benchmark_config(path: Path) -> tuple[str, list[BenchmarkTarget]]:
    raw = _load_toml(path)
    suite_section = raw.get("suite", {})
    suite_name = suite_section.get("name", "owasp") if isinstance(suite_section, dict) else "owasp"

    targets: list[BenchmarkTarget] = []
    for entry in raw.get("targets", []):
        ttype = entry.get("type", "provider")
        provider = entry.get("provider")
        model = entry.get("model")
        label = entry.get("label") or _default_label(ttype, provider, model)
        targets.append(
            BenchmarkTarget(label=label, type=ttype, provider=provider, model=model)
        )
    return suite_name, targets


def _default_label(ttype: str, provider: str | None, model: str | None) -> str:
    if ttype == "provider":
        return f"{provider}/{model}" if model else (provider or "provider")
    if ttype == "local":
        return Path(model or "local").name
    return model or ttype


def targets_from_providers(providers: list[str], model: str | None = None) -> list[BenchmarkTarget]:
    return [
        BenchmarkTarget(
            label=f"{p}/{model}" if model else p,
            type="provider",
            provider=p,
            model=model,
        )
        for p in providers
    ]


def target_from_provider(provider: str, model: str | None = None) -> BenchmarkTarget:
    return BenchmarkTarget(
        label=f"{provider}/{model}" if model else provider,
        type="provider",
        provider=provider,
        model=model,
    )


def target_from_local(model: str) -> BenchmarkTarget:
    return BenchmarkTarget(
        label=Path(model).name,
        type="local",
        model=model,
    )
