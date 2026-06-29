"""Plugin base classes and discovery."""

from __future__ import annotations

import importlib.util
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, TypeVar

from agentarmor.core.config import AppConfig
from agentarmor.core.models import ProbeRequest, ProbeResult

T = TypeVar("T")
_REGISTRY: dict[str, dict[str, type]] = {
    "probe": {},
    "detector": {},
    "reporter": {},
    "engine": {},
}


def register(kind: str) -> Callable[[type[T]], type[T]]:
    def decorator(cls: type[T]) -> type[T]:
        _REGISTRY.setdefault(kind, {})[getattr(cls, "id", cls.__name__)] = cls
        return cls
    return decorator


class BaseProbe(ABC):
    id: str = "probe.base"
    name: str = "Base Probe"
    owasp: list[str] = []

    @abstractmethod
    def build_request(self, config: AppConfig) -> ProbeRequest:
        ...

    def evaluate_response(self, content: str) -> dict[str, Any] | None:
        return None


class BaseDetector(ABC):
    id: str = "detector.base"

    @abstractmethod
    def analyze(self, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        ...


class BaseReporter(ABC):
    id: str = "reporter.base"

    @abstractmethod
    def write(self, scan: Any, findings: list[Any], output_path: Path) -> Path:
        ...


class BaseEngine(ABC):
    id: str = "engine.base"

    @abstractmethod
    async def send(self, config: AppConfig, request: ProbeRequest) -> ProbeResult:
        ...


def _load_module_from_path(path: Path) -> None:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)


def discover_plugins(dirs: list[str], root: Path | None = None) -> None:
    root = root or Path.cwd()
    for dir_name in dirs:
        plugin_dir = root / dir_name
        if not plugin_dir.is_dir():
            continue
        for py_file in plugin_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                _load_module_from_path(py_file)
            except Exception:
                continue


def get_registered_probes() -> dict[str, type[BaseProbe]]:
    return dict(_REGISTRY.get("probe", {}))


def get_registered_detectors() -> dict[str, type[BaseDetector]]:
    return dict(_REGISTRY.get("detector", {}))
