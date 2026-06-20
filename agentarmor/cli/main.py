"""Typer CLI entry point."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
import uvicorn

from agentarmor.cli.gate import gate_main
from agentarmor.cli.benchmark import benchmark_app
from agentarmor.core.config import load_config, merge_cli_target
from agentarmor.db.models import init_db

app = typer.Typer(
    name="agentarmor",
    help="AgentArmor — AI Security Validation Platform",
    no_args_is_help=True,
)

app.add_typer(benchmark_app, name="benchmark")


@app.command()
def scan(
    config: Optional[Path] = typer.Option(
        Path("AgentArmor.toml"), "--config", "-c", help="Path to config file"
    ),
    url: Optional[str] = typer.Option(None, "--url", help="Target API URL (OpenAI-compatible)"),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Cloud provider: openai, anthropic, gemini, ..."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="Local model path (.gguf file or HuggingFace directory)"
    ),
    agent: Optional[str] = typer.Option(
        None, "--agent", help="Agent framework: crewai, langgraph"
    ),
    mcp: Optional[str] = typer.Option(None, "--mcp", help="MCP server path or HTTP URL"),
    rag: Optional[str] = typer.Option(None, "--rag", help="RAG corpus directory"),
    embedder: Optional[str] = typer.Option(None, "--embedder", help="RAG embedder (default: bge)"),
    agent_config: Optional[Path] = typer.Option(
        None, "--agent-config", help="Agent configuration TOML file"
    ),
    fmt: Optional[str] = typer.Option(
        None, "--format", help="Report format: json, sarif, html, pdf, csv, or comma-separated"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Run a security scan (endpoint, provider, local model, agent, MCP, or RAG)."""
    try:
        cfg = merge_cli_target(
            load_config(config if config.exists() else None),
            url=url,
            provider=provider,
            model=model,
            agent=agent,
            mcp=mcp,
            rag=rag,
            embedder=embedder,
            agent_config=str(agent_config) if agent_config else None,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    from agentarmor.engines.router import validate_target

    try:
        validate_target(cfg)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    formats = None
    if fmt:
        formats = [f.strip() for f in fmt.split(",")]

    async def _run() -> None:
        from agentarmor.services.scan_service import execute_scan

        completed, paths = await execute_scan(cfg, formats=formats, output_file=output)
        typer.echo(f"Scan {completed.id} completed: {completed.finding_count} finding(s)")
        for p in paths:
            typer.echo(f"  Report: {p}")

    asyncio.run(_run())


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
    config: Optional[Path] = typer.Option(Path("AgentArmor.toml"), "--config", "-c"),
    model_dir: Optional[str] = typer.Option(None, "--model-dir", help="Bundled detection models path"),
    data_dir: Optional[str] = typer.Option(None, "--data-dir", help="Portable data directory"),
) -> None:
    """Start the AgentArmor FastAPI server."""
    import os

    os.environ.setdefault("AGENTARMOR_CONFIG", str(config))
    if model_dir:
        os.environ["AGENTARMOR_MODEL_DIR"] = model_dir
    if data_dir:
        os.environ["AGENTARMOR_DATA_DIR"] = data_dir
    uvicorn.run("agentarmor.api.app:app", host=host, port=port, reload=False)


@app.command()
def gate(
    sarif: Path = typer.Option(..., "--sarif", help="SARIF file to evaluate"),
    fail_on: str = typer.Option("HIGH,CRITICAL", "--fail-on", help="Comma-separated severities"),
) -> None:
    """Exit non-zero if SARIF contains findings at or above severity threshold."""
    gate_main(str(sarif), fail_on)


@app.command()
def db_migrate(
    config: Optional[Path] = typer.Option(Path("AgentArmor.toml"), "--config", "-c"),
) -> None:
    """Create or upgrade the local SQLite database schema."""
    cfg = load_config(config if config.exists() else None)
    init_db(cfg.database_url)
    typer.echo(f"Database ready: {cfg.database_url}")


models_app = typer.Typer(help="Detection model management")
app.add_typer(models_app, name="models")


@models_app.command("download")
def models_download(
    config: Optional[Path] = typer.Option(Path("AgentArmor.toml"), "--config", "-c"),
    force: bool = typer.Option(False, "--force", help="Re-download existing models"),
) -> None:
    """Download ONNX models to the local cache."""
    from agentarmor.detection.models.manager import get_model_manager

    cfg = load_config(config if config.exists() else None)
    manager = get_model_manager(cfg.detection.model_dir)
    for line in manager.download(force=force):
        typer.echo(line)


@models_app.command("status")
def models_status(
    config: Optional[Path] = typer.Option(Path("AgentArmor.toml"), "--config", "-c"),
) -> None:
    """Show detection model availability."""
    from agentarmor.detection.models.manager import get_model_manager

    cfg = load_config(config if config.exists() else None)
    manager = get_model_manager(cfg.detection.model_dir)
    manager.ensure_bootstrap_models()
    for item in manager.status():
        flag = "ok" if item.present else "missing"
        typer.echo(f"[{flag}] {item.name}: {item.path or '-'} ({item.source})")


if __name__ == "__main__":
    app()
