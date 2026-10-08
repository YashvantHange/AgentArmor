"""`agentarmor swarm` commands.

Shares ``execute_swarm`` with the API, the same way ``scan`` and ``POST /v1/scans``
share ``execute_scan``. The only differences are that the CLI mints its own scan id
and owns the event loop.

Heavy imports stay function-local, matching ``cli/main.py``, so starting the CLI
does not pay for the detection stack.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

swarm_app = typer.Typer(
    help="Agent swarm - many specialized agents pursuing one preset goal",
    no_args_is_help=True,
)


@swarm_app.command("goals")
def goals(
    config: Optional[Path] = typer.Option(Path("AgentArmor.toml"), "--config", "-c"),
) -> None:
    """List the preset goals a swarm can pursue."""
    from agentarmor.core.config import load_config
    from agentarmor.swarm.goals import list_swarm_goals

    cfg = load_config(config if config and config.exists() else None)
    typer.echo(f"{'ID':<24} {'OWASP':<16} NAME")
    for goal in list_swarm_goals():
        typer.echo(f"{goal.id:<24} {','.join(goal.owasp):<16} {goal.name}")
    typer.echo("")
    typer.echo(
        f"Default {cfg.swarm.default_agents} agents, "
        f"max {cfg.swarm.max_agents}, "
        f"concurrency {cfg.swarm.default_concurrent} (max {cfg.swarm.max_concurrent})."
    )


@swarm_app.command("run")
def run(
    goal: str = typer.Option(..., "--goal", help="Preset goal id (see: swarm goals)"),
    url: Optional[str] = typer.Option(None, "--url", help="Target chat API URL"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    model: Optional[str] = typer.Option(None, "--model"),
    agents: Optional[int] = typer.Option(None, "--agents", help="Roster size"),
    concurrency: Optional[int] = typer.Option(
        None, "--concurrency", help="How many agents talk to the target at once"
    ),
    fmt: Optional[str] = typer.Option(None, "--format", help="json,html,sarif,pdf,csv"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    config: Optional[Path] = typer.Option(Path("AgentArmor.toml"), "--config", "-c"),
    analysis_provider: Optional[str] = typer.Option(None, "--analysis-provider"),
    analysis_model: Optional[str] = typer.Option(None, "--analysis-model"),
    analysis_api_key: Optional[str] = typer.Option(None, "--analysis-api-key"),
    auth_token: Optional[str] = typer.Option(None, "--auth-token"),
) -> None:
    """Run a swarm against a target.

    Only run this against systems you own or are authorised to test: a swarm sends
    considerably more traffic than a single scan.
    """
    from agentarmor.core.config import (
        apply_analysis_options,
        apply_swarm_options,
        ensure_analysis_ready,
        load_config,
        merge_cli_target,
    )
    from agentarmor.engines.router import validate_target
    from agentarmor.swarm.goals import get_swarm_goal, list_swarm_goal_ids

    if get_swarm_goal(goal) is None:
        typer.echo(f"Error: unknown goal '{goal}'.", err=True)
        typer.echo(f"Valid goals: {', '.join(list_swarm_goal_ids())}", err=True)
        raise typer.Exit(1)

    cfg = load_config(config if config and config.exists() else None)
    try:
        cfg = merge_cli_target(cfg, url=url, provider=provider, model=model)
        cfg = apply_analysis_options(
            cfg,
            analysis_provider=analysis_provider,
            analysis_model=analysis_model,
            analysis_api_key=analysis_api_key,
            auth_token=auth_token,
        )
        cfg, effective_agents, effective_concurrency = apply_swarm_options(
            cfg, agents=agents, max_concurrent=concurrency
        )
        if not cfg.swarm.enabled:
            raise ValueError("Swarm is disabled (swarm.enabled=false).")
        ensure_analysis_ready(cfg)
        validate_target(cfg)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    from agentarmor.detection.agentic.preflight import validate_analysis_key

    try:
        asyncio.run(validate_analysis_key(cfg))
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    if agents is not None and agents != effective_agents:
        typer.echo(f"Requested {agents} agents; running {effective_agents} (configured maximum).")

    formats = [f.strip() for f in fmt.split(",")] if fmt else None

    async def _run() -> None:
        from agentarmor.services.swarm_service import execute_swarm

        try:
            completed, paths = await execute_swarm(
                cfg,
                goal_id=goal,
                agents=effective_agents,
                max_concurrent=effective_concurrency,
                formats=formats,
                output_file=output,
            )
        except asyncio.CancelledError:
            typer.echo("Swarm cancelled; partial results were saved.", err=True)
            raise typer.Exit(130) from None

        summary = (completed.metadata or {}).get("swarm_summary") or {}
        coverage = summary.get("coverage") or {}
        typer.echo("")
        typer.echo(
            f"Agents {coverage.get('agents', effective_agents)} | "
            f"Attack paths {coverage.get('attack_paths', 0)} | "
            f"Personas {coverage.get('personas', 0)} | "
            f"Strategies {coverage.get('strategies', 0)} | "
            f"Concurrency {coverage.get('concurrency', effective_concurrency)}"
        )
        typer.echo(
            f"Swarm {completed.id} {completed.status.value}: "
            f"{completed.finding_count} finding(s), "
            f"{summary.get('blackboard_facts', 0)} shared fact(s)"
        )
        typer.echo(
            f"  Cost: members ${summary.get('member_cost_usd', 0):.4f} + "
            f"enrichment ${summary.get('enrichment_cost_usd', 0):.4f} = "
            f"${summary.get('total_cost_usd', 0):.4f} "
            f"({summary.get('tokens_used', 0)} tokens)"
        )
        if summary.get("stopped"):
            typer.echo(f"  Budget stopped: {summary.get('stop_reason')}", err=True)
        elif summary.get("degraded"):
            typer.echo("  Budget warning threshold reached.", err=True)

        _echo_member_costs(completed)

        health = (completed.metadata or {}).get("analysis_health") or {}
        if health.get("cloud_ok") is False:
            typer.echo(f"Warning: {health.get('message')}", err=True)
        for path in paths:
            typer.echo(f"  Report: {path}")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        # The expected CLI cancel. Partial results are already persisted.
        typer.echo("\nInterrupted; partial results were saved.", err=True)
        raise typer.Exit(130) from None


def _echo_member_costs(completed, *, limit: int = 10) -> None:
    """Per-member cost table - the first per-agent attribution the tool can report."""
    trace = (completed.metadata or {}).get("swarm_trace") or {}
    members = [m for m in (trace.get("members") or []) if not m.get("error")]
    if not members:
        return
    members.sort(key=lambda m: m.get("cost_usd", 0.0), reverse=True)
    typer.echo("")
    typer.echo(f"  {'MEMBER':<10} {'NODE':<24} {'PERSONA':<20} {'TOKENS':>7} {'COST':>9}  VULN")
    for member in members[:limit]:
        typer.echo(
            f"  {member.get('member_id', ''):<10} "
            f"{member.get('node_id', ''):<24} "
            f"{member.get('persona_id', ''):<20} "
            f"{member.get('tokens', 0):>7} "
            f"${member.get('cost_usd', 0.0):>8.4f}  "
            f"{'yes' if member.get('vulnerable') else ''}"
        )
    if len(members) > limit:
        typer.echo(f"  ... and {len(members) - limit} more")
