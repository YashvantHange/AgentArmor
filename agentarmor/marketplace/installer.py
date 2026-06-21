"""Install and publish marketplace rules."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agentarmor.marketplace.catalog import bundled_probe_path, get_rule
from agentarmor.marketplace.models import InstalledRule, RuleManifest
from agentarmor.sdk.probe_sdk import validate_probe_module


def default_install_dir(data_dir: Path | None = None) -> Path:
    base = data_dir or Path.home() / ".agentarmor"
    dest = base / "marketplace" / "installed"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def install_rule(
    rule_id: str,
    *,
    install_dir: Path | None = None,
    data_dir: Path | None = None,
) -> InstalledRule:
    manifest = get_rule(rule_id)
    if not manifest:
        raise ValueError(f"unknown marketplace rule: {rule_id}")

    dest_root = install_dir or default_install_dir(data_dir)
    rule_dir = dest_root / rule_id
    rule_dir.mkdir(parents=True, exist_ok=True)

    if manifest.category == "suite":
        from agentarmor.marketplace.catalog import BUILTIN_RULES, bundled_probe_path as bpp

        installed_any = False
        for child in BUILTIN_RULES:
            if child.category != "probe":
                continue
            src = bpp(child)
            if not src:
                continue
            shutil.copy2(src, rule_dir / src.name)
            installed_any = True
        if not installed_any:
            raise ValueError(f"suite {rule_id} has no installable probe files")
    else:
        src = bundled_probe_path(manifest)
        if not src:
            raise ValueError(f"rule {rule_id} has no probe file")
        target = rule_dir / src.name
        shutil.copy2(src, target)
        errors = validate_probe_module(target)
        if errors:
            target.unlink(missing_ok=True)
            raise ValueError("; ".join(errors))

    manifest_path = rule_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    installed = InstalledRule(
        id=str(uuid.uuid4()),
        manifest_id=manifest.id,
        name=manifest.name,
        version=manifest.version,
        install_path=str(rule_dir),
        installed_at=datetime.now(timezone.utc).isoformat(),
    )
    return installed


def uninstall_rule(rule_id: str, *, install_dir: Path | None = None, data_dir: Path | None = None) -> bool:
    dest_root = install_dir or default_install_dir(data_dir)
    rule_dir = dest_root / rule_id
    if not rule_dir.exists():
        return False
    shutil.rmtree(rule_dir)
    return True


def list_installed(install_dir: Path | None = None, data_dir: Path | None = None) -> list[InstalledRule]:
    dest_root = install_dir or default_install_dir(data_dir)
    if not dest_root.exists():
        return []
    installed: list[InstalledRule] = []
    for child in dest_root.iterdir():
        if not child.is_dir():
            continue
        manifest_path = child / "manifest.json"
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            installed.append(
                InstalledRule(
                    id=child.name,
                    manifest_id=data.get("id", child.name),
                    name=data.get("name", child.name),
                    version=data.get("version", "1.0.0"),
                    install_path=str(child),
                    installed_at=datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc).isoformat(),
                )
            )
    return installed


def publish_local_probe(
    probe_path: Path,
    *,
    manifest: RuleManifest,
    install_dir: Path | None = None,
    data_dir: Path | None = None,
) -> InstalledRule:
    """Publish a user-authored probe to the local marketplace."""
    errors = validate_probe_module(probe_path)
    if errors:
        raise ValueError("; ".join(errors))

    dest_root = install_dir or default_install_dir(data_dir)
    rule_dir = dest_root / manifest.id
    rule_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(probe_path, rule_dir / probe_path.name)
    (rule_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    return InstalledRule(
        id=str(uuid.uuid4()),
        manifest_id=manifest.id,
        name=manifest.name,
        version=manifest.version,
        install_path=str(rule_dir),
        installed_at=datetime.now(timezone.utc).isoformat(),
    )


def marketplace_plugin_dirs(data_dir: Path | None = None) -> list[str]:
    """Return relative plugin dirs for installed marketplace probes."""
    installed = list_installed(data_dir=data_dir)
    return [str(Path(i.install_path)) for i in installed if Path(i.install_path).exists()]


def discover_installed_probes() -> None:
    """Load probe modules from installed marketplace packages."""
    from agentarmor.plugins.base import _load_module_from_path

    for installed in list_installed():
        probe_dir = Path(installed.install_path)
        if not probe_dir.is_dir():
            continue
        for py in probe_dir.glob("*.py"):
            if py.name.startswith("_"):
                continue
            try:
                _load_module_from_path(py)
            except Exception:
                continue
