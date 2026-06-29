"""Phase 4 CLI — marketplace, monitoring, dataset export."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from agentarmor.core.config import load_config
from agentarmor.db.monitor_session import MonitorRepository
from agentarmor.db.session import ScanRepository
from agentarmor.export.dataset import export_dataset_jsonl
from agentarmor.marketplace.catalog import list_rules
from agentarmor.marketplace.installer import install_rule, list_installed, publish_local_probe, uninstall_rule
from agentarmor.marketplace.models import RuleManifest
from agentarmor.monitoring.runner import run_scheduled_scan
from agentarmor.sdk.probe_sdk import validate_probe_module
from agentarmor.sdk.detector_sdk import validate_detector_module

marketplace_app = typer.Typer(help="Community rule marketplace")
monitor_app = typer.Typer(help="Continuous monitoring schedules")
dataset_app = typer.Typer(help="Research dataset export")


@marketplace_app.command("list")
def marketplace_list(category: Optional[str] = typer.Option(None, "--category")) -> None:
    """List available marketplace rules."""
    for rule in list_rules(category=category):
        typer.echo(f"{rule.id:24} {rule.category:8} {rule.name}")


@marketplace_app.command("installed")
def marketplace_installed() -> None:
    """List locally installed marketplace rules."""
    for item in list_installed():
        typer.echo(f"{item.manifest_id:24} v{item.version}  {item.install_path}")


@marketplace_app.command("install")
def marketplace_install(
    rule_id: str,
    trust: bool = typer.Option(False, "--trust", help="Trust detector plugins (required for detectors)"),
) -> None:
    """Install a marketplace rule."""
    try:
        installed = install_rule(rule_id, trust=trust)
        typer.echo(f"Installed {installed.name} -> {installed.install_path}")
        if not trust:
            typer.echo("Note: marketplace detectors require --trust to run at scan time.")
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@marketplace_app.command("uninstall")
def marketplace_uninstall(rule_id: str) -> None:
    """Remove an installed marketplace rule."""
    if uninstall_rule(rule_id):
        typer.echo(f"Removed {rule_id}")
    else:
        typer.echo(f"Not installed: {rule_id}", err=True)
        raise typer.Exit(1)


@marketplace_app.command("validate")
def marketplace_validate(
    probe: Path,
    detector: bool = typer.Option(False, "--detector", help="Validate a detector module"),
) -> None:
    """Validate a custom probe or detector before publishing."""
    errors = validate_detector_module(probe) if detector else validate_probe_module(probe)
    if errors:
        for err in errors:
            typer.echo(f"  - {err}", err=True)
        raise typer.Exit(1)
    kind = "Detector" if detector else "Probe"
    typer.echo(f"{kind} module is valid.")


@marketplace_app.command("publish")
def marketplace_publish(
    probe: Path,
    rule_id: str = typer.Option(..., "--id"),
    name: str = typer.Option(..., "--name"),
    version: str = typer.Option("1.0.0", "--version"),
) -> None:
    """Publish a local probe to your marketplace install directory."""
    manifest = RuleManifest(
        id=rule_id,
        name=name,
        version=version,
        author="local",
        description=f"User-published probe {rule_id}",
        category="probe",
        probe_file=probe.name,
        builtin=False,
    )
    try:
        installed = publish_local_probe(probe, manifest=manifest)
        typer.echo(f"Published {installed.name} -> {installed.install_path}")
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@monitor_app.command("add")
def monitor_add(
    name: str,
    target_type: str = typer.Option("endpoint", "--type"),
    url: Optional[str] = typer.Option(None, "--url"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    cron: str = typer.Option("daily", "--cron", help="hourly|daily|weekly|manual"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Add a monitoring schedule."""
    cfg = load_config(config if config and config.exists() else None)
    repo = MonitorRepository(cfg.database_url)
    repo.ensure_schema()
    target_config: dict = {}
    if url:
        target_config["url"] = url
    if provider:
        target_config["provider"] = provider
    schedule = repo.create_schedule(
        name=name,
        target_type=target_type,
        target_config=target_config,
        cron=cron,
    )
    typer.echo(f"Schedule {schedule.id} created ({schedule.cron})")


@monitor_app.command("list")
def monitor_list(config: Optional[Path] = typer.Option(None, "--config", "-c")) -> None:
    """List monitoring schedules."""
    cfg = load_config(config if config and config.exists() else None)
    repo = MonitorRepository(cfg.database_url)
    repo.ensure_schema()
    for s in repo.list_schedules():
        flag = "on" if s.enabled else "off"
        drift = " DRIFT" if s.drift_detected else ""
        typer.echo(f"[{flag}] {s.id[:8]}… {s.name:20} {s.cron:8} findings={s.last_finding_count}{drift}")


@monitor_app.command("remove")
def monitor_remove(
    schedule_id: str,
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Delete a monitoring schedule."""
    cfg = load_config(config if config and config.exists() else None)
    repo = MonitorRepository(cfg.database_url)
    if repo.delete_schedule(schedule_id):
        typer.echo(f"Removed {schedule_id}")
    else:
        typer.echo("Schedule not found", err=True)
        raise typer.Exit(1)


@monitor_app.command("run")
def monitor_run(
    schedule_id: str,
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Run a scheduled scan immediately."""
    import asyncio

    cfg = load_config(config if config and config.exists() else None)
    repo = MonitorRepository(cfg.database_url)
    try:
        result = asyncio.run(run_scheduled_scan(schedule_id, repo=repo, config=cfg))
        typer.echo(
            f"Scan {result.scan_id}: {result.finding_count} findings "
            f"({result.new_findings} new, regressed={result.regressed})"
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@dataset_app.command("export")
def dataset_export(
    output: Path = typer.Option(Path("dataset.jsonl"), "--output", "-o"),
    scan_id: Optional[list[str]] = typer.Option(None, "--scan-id"),
    anonymize: bool = typer.Option(True, "--anonymize/--no-anonymize"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Export findings as anonymized JSONL research dataset."""
    cfg = load_config(config if config and config.exists() else None)
    repo = ScanRepository(cfg.database_url)
    repo.ensure_schema()
    path = export_dataset_jsonl(
        repo,
        scan_ids=scan_id,
        anonymize=anonymize,
        output_path=output,
    )
    typer.echo(f"Dataset written: {path}")
