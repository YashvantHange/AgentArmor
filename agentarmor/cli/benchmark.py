"""Benchmark CLI command."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

from agentarmor import __version__
from agentarmor.benchmark.config import (
    load_benchmark_config,
    target_from_local,
    target_from_provider,
    targets_from_providers,
)
from agentarmor.benchmark.reporter import (
    default_report_paths,
    print_terminal_table,
    write_html_leaderboard,
    write_json_report,
)
from agentarmor.benchmark.runner import run_benchmark
from agentarmor.core.config import load_config
from agentarmor.db.benchmark_session import BenchmarkRepository

benchmark_app = typer.Typer(help="Model security benchmarking")


@benchmark_app.callback(invoke_without_command=True)
def benchmark(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(Path("AgentArmor.toml"), "--config", "-c"),
    benchmark_config: Optional[Path] = typer.Option(
        None, "--benchmark-config", help="Multi-model benchmark.toml"
    ),
    provider: Optional[str] = typer.Option(None, "--provider"),
    providers: Optional[str] = typer.Option(None, "--providers", help="Comma-separated providers"),
    model: Optional[str] = typer.Option(None, "--model", help="Local .gguf or HF path"),
    suite: str = typer.Option("owasp", "--suite"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output dir or .json file"),
    fmt: Optional[str] = typer.Option(None, "--format", help="json, html, or both"),
    no_save: bool = typer.Option(False, "--no-save", help="Skip SQLite persistence"),
) -> None:
    """Run standardized security benchmarks against models."""
    if ctx.invoked_subcommand is not None:
        return

    base_cfg = load_config(config if config.exists() else None)
    targets = []
    suite_name = suite

    if benchmark_config and benchmark_config.exists():
        suite_name, targets = load_benchmark_config(benchmark_config)
    elif providers:
        plist = [p.strip() for p in providers.split(",") if p.strip()]
        targets = targets_from_providers(plist, model=model)
    elif provider:
        targets = [target_from_provider(provider, model=model)]
    elif model:
        targets = [target_from_local(model)]
    else:
        typer.echo(
            "Error: specify --provider, --providers, --model, or --benchmark-config",
            err=True,
        )
        raise typer.Exit(1)

    async def _run() -> None:
        completed = await run_benchmark(base_cfg, suite_name, targets)
        print_terminal_table(completed)

        fmts = [f.strip().lower() for f in (fmt or "json,html").split(",")]
        out_dir = Path(base_cfg.reporting.output_dir)
        if output:
            if output.suffix == ".json":
                write_json_report(completed, output)
                typer.echo(f"Report: {output}")
            else:
                out_dir = output
                html_path, json_path = default_report_paths(out_dir, completed)
                if "html" in fmts:
                    p = write_html_leaderboard(completed, html_path, version=__version__)
                    typer.echo(f"Report: {p}")
                if "json" in fmts:
                    p = write_json_report(completed, json_path)
                    typer.echo(f"Report: {p}")
        else:
            html_path, json_path = default_report_paths(out_dir, completed)
            if "html" in fmts:
                p = write_html_leaderboard(completed, html_path, version=__version__)
                typer.echo(f"Report: {p}")
            if "json" in fmts:
                p = write_json_report(completed, json_path)
                typer.echo(f"Report: {p}")

        if not no_save:
            repo = BenchmarkRepository(base_cfg.database_url)
            repo.ensure_schema()
            repo.save_run(completed)
            typer.echo(f"Saved benchmark run: {completed.id}")

    asyncio.run(_run())
