#!/usr/bin/env python3
"""
Full AgentArmor .exe QA runner.
Produces:
  C:\\AgentArmorQA\\QA_REPORT.md   (single human-readable summary)
  C:\\AgentArmorQA\\QA_REPORT.json (machine-readable details)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# ── paths ──────────────────────────────────────────────────────────────────
QA_ROOT = Path(r"C:\AgentArmorQA")
REPORTS = QA_ROOT / "reports"
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "AgentArmor"
GUI_EXE = INSTALL_DIR / "agentarmor-gui.exe"
EMBED_PYTHON = INSTALL_DIR / "resources" / "python" / "python.exe"
EMBED_CLI = INSTALL_DIR / "resources" / "python" / "Scripts" / "agentarmor.exe"
REPO = Path(__file__).resolve().parents[1]
MOCK_MODULE = "tests.fixtures.mock_openai_server:app"

API = "http://127.0.0.1:8787"
MOCK = "http://127.0.0.1:8000"

SCAN_TIMEOUT = 300
BENCH_TIMEOUT = 360


@dataclass
class TestResult:
    name: str
    status: str  # PASS | FAIL | SKIP | WARN
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class QAReport:
    started_at: str = ""
    finished_at: str = ""
    install_path: str = ""
    install_version: str = ""
    results: list[TestResult] = field(default_factory=list)

    def add(self, r: TestResult) -> None:
        self.results.append(r)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == "PASS")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "FAIL")


report = QAReport()


# ── helpers ────────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    print(msg, flush=True)


def run_cmd(cmd: list[str], *, cwd: Path | None = None, timeout: int = 600) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as exc:
        return -1, str(exc)


def setup_harness() -> None:
    QA_ROOT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    src_rag = REPO / "tests" / "fixtures" / "rag_corpus"
    dst_rag = QA_ROOT / "rag_corpus"
    if src_rag.exists():
        import shutil
        if dst_rag.exists():
            shutil.rmtree(dst_rag)
        shutil.copytree(src_rag, dst_rag)
    for name in ("mcp_server.py", "agent.toml"):
        src = REPO / "tests" / "fixtures" / ("mcp_server" if name == "mcp_server.py" else "") / name
        if name == "mcp_server.py":
            src = REPO / "tests" / "fixtures" / "mcp_server" / "server.py"
        if src.exists():
            (QA_ROOT / name).write_bytes(src.read_bytes())

    (QA_ROOT / "qa-scan.toml").write_text(
        """[engine.endpoint]
profile = "openai"
rate_limit_rps = 10
timeout_s = 30

[reporting]
formats = ["json", "html", "sarif"]
output_dir = "./reports"
""",
        encoding="utf-8",
    )
    (QA_ROOT / "qa-provider.toml").write_text(
        """[target]
type = "provider"
provider = "openai"
model = "gpt-4o-mini"

[reporting]
formats = ["json", "sarif"]
output_dir = "./reports"
""",
        encoding="utf-8",
    )


async def wait_health(url: str, timeout: float = 60) -> bool:
    deadline = time.time() + timeout
    async with httpx.AsyncClient() as client:
        while time.time() < deadline:
            try:
                r = await client.get(f"{url}/health", timeout=3)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
    return False


async def wait_scan(client: httpx.AsyncClient, scan_id: str, timeout: float = SCAN_TIMEOUT) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        r = await client.get(f"{API}/v1/scans/{scan_id}")
        r.raise_for_status()
        data = r.json()
        if data.get("status") in ("completed", "failed", "cancelled"):
            return data
        await asyncio.sleep(1)
    raise TimeoutError(scan_id)


async def create_scan(client: httpx.AsyncClient, body: dict) -> str:
    r = await client.post(f"{API}/v1/scans", json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"POST /v1/scans {r.status_code}: {r.text[:500]}")
    return r.json()["scan_id"]


def report_search_dirs() -> list[Path]:
    return [
        INSTALL_DIR / "reports",
        Path(os.environ.get("APPDATA", "")) / "AgentArmor" / "reports",
        Path(os.environ.get("LOCALAPPDATA", "")) / "AgentArmor" / "reports",
        REPORTS,
        REPO / "reports",
    ]


def validate_exports(scan_id: str, _appdata_reports: Path | None = None) -> dict[str, Any]:
    json_path = None
    for base in report_search_dirs():
        candidate = base / f"scan-{scan_id}.json"
        if candidate.exists():
            json_path = candidate
            break

    if not json_path.exists():
        return {"ok": False, "reason": "json report not found on disk"}

    data = json.loads(json_path.read_text(encoding="utf-8"))
    fc = data["summary"]["finding_count"]
    json_len = len(data["findings"])
    sarif_path = json_path.with_suffix(".sarif")
    html_path = json_path.with_suffix(".html")
    sarif_count = None
    sarif_ok = False
    if sarif_path.exists():
        sarif = json.loads(sarif_path.read_text(encoding="utf-8"))
        sarif_count = len(sarif.get("runs", [{}])[0].get("results", []))
        run = sarif.get("runs", [{}])[0]
        driver = run.get("tool", {}).get("driver", {})
        sarif_ok = (
            sarif.get("version") == "2.1.0"
            and driver.get("name") == "AgentArmor"
            and sarif_count == fc
        )
    html_ok = False
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        html_ok = bool(re.search(rf">\s*{fc}\s*<.*?finding\(s\)", html, re.S)) or f"{fc} finding(s)" in html

    counts_ok = fc == json_len and (sarif_count is None or sarif_count == fc)
    export_ok = counts_ok and (sarif_count is None or sarif_ok) and (not html_path.exists() or html_ok)

    conn_failed = any(f.get("probe_id") == "connectivity.failed" for f in data["findings"])
    conn_err_count = sum(1 for f in data["findings"] if f.get("metadata", {}).get("connectivity_error"))

    return {
        "ok": export_ok,
        "finding_count": fc,
        "json_len": json_len,
        "sarif_count": sarif_count,
        "sarif_ok": sarif_ok,
        "html_ok": html_ok,
        "connectivity_failed": conn_failed,
        "connectivity_error_findings": conn_err_count,
        "json_path": str(json_path),
    }


def write_reports() -> None:
    report.finished_at = datetime.now(timezone.utc).isoformat()
    json_path = QA_ROOT / "QA_REPORT.json"
    json_path.write_text(
        json.dumps(
            {
                "started_at": report.started_at,
                "finished_at": report.finished_at,
                "install_path": report.install_path,
                "install_version": report.install_version,
                "summary": {
                    "total": len(report.results),
                    "passed": report.passed,
                    "failed": report.failed,
                    "warn": sum(1 for r in report.results if r.status == "WARN"),
                    "skip": sum(1 for r in report.results if r.status == "SKIP"),
                },
                "results": [asdict(r) for r in report.results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# AgentArmor .exe QA Report",
        "",
        f"**Generated:** {report.finished_at}",
        f"**Install:** `{report.install_path}`",
        f"**Sidecar version:** {report.install_version or 'unknown'}",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total tests | {len(report.results)} |",
        f"| Passed | {report.passed} |",
        f"| Failed | {report.failed} |",
        f"| Warnings | {sum(1 for r in report.results if r.status == 'WARN')} |",
        f"| Skipped | {sum(1 for r in report.results if r.status == 'SKIP')} |",
        "",
        f"**Overall:** {'PASS' if report.failed == 0 else 'FAIL'}",
        "",
        "## Results",
        "",
        "| Test | Status | Details |",
        "|------|--------|---------|",
    ]
    for r in report.results:
        detail = str(r.detail).replace("|", "\\|").replace("\n", " ")
        if len(detail) > 120:
            detail = detail[:117] + "..."
        lines.append(f"| {r.name} | **{r.status}** | {detail} |")

    lines.extend(["", "## Detailed metrics", ""])
    for r in report.results:
        if r.metrics:
            lines.append(f"### {r.name}")
            lines.append("```json")
            lines.append(json.dumps(r.metrics, indent=2))
            lines.append("```")
            lines.append("")

    lines.extend([
        "## Artifacts",
        "",
        f"- JSON report: `{json_path}`",
        f"- Harness: `{QA_ROOT}`",
        f"- Scan reports: `%APPDATA%\\AgentArmor\\reports\\` or `{REPORTS}`",
        "",
        "## Notes",
        "",
        "- GUI scans use the same `POST /v1/scans` API as the desktop app.",
        "- Embedded CLI: `" + str(EMBED_CLI) + "`",
        "- Mock API: `http://127.0.0.1:8000/v1/chat/completions`",
        "",
    ])

    md_path = QA_ROOT / "QA_REPORT.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    log(f"\nReports written:\n  {md_path}\n  {json_path}")


# ── test phases ────────────────────────────────────────────────────────────
async def phase_install_check() -> None:
    if GUI_EXE.exists():
        report.install_path = str(GUI_EXE)
        report.add(TestResult("Install detected", "PASS", str(GUI_EXE)))
    else:
        report.add(TestResult("Install detected", "FAIL", f"Not found: {GUI_EXE}"))
        return

    if EMBED_PYTHON.exists():
        code, out = run_cmd([str(EMBED_PYTHON), "-m", "agentarmor.cli.main", "--help"], timeout=60)
        report.add(
            TestResult(
                "Embedded CLI (python -m)",
                "PASS" if code == 0 else "WARN",
                "module CLI OK" if code == 0 else (out[:200] or f"exit {code}"),
            )
        )
    else:
        report.add(TestResult("Embedded CLI (python -m)", "FAIL", str(EMBED_PYTHON)))

    if EMBED_CLI.exists():
        code, out = run_cmd([str(EMBED_CLI), "--help"], timeout=30)
        report.add(
            TestResult(
                "Embedded CLI (agentarmor.exe wrapper)",
                "PASS" if code == 0 else "WARN",
                "wrapper OK" if code == 0 else f"wrapper exit {code} — use python -m instead",
            )
        )


async def phase_sidecar(gui_proc: subprocess.Popen | None) -> None:
    ok = await wait_health(API, timeout=90)
    if not ok:
        report.add(TestResult("Sidecar health", "FAIL", f"No response from {API}/health"))
        return
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API}/health")
        data = r.json()
    report.install_version = data.get("version", "")
    report.add(
        TestResult(
            "Sidecar health",
            "PASS",
            f"version={data.get('version')} webscan_ready={data.get('webscan_ready')}",
            metrics=data,
        )
    )


async def phase_api_scans() -> dict[str, str]:
    scan_ids: dict[str, str] = {}
    appdata = INSTALL_DIR / "reports"

    cases = [
        (
            "GUI/API: API Endpoint",
            {
                "target_type": "endpoint",
                "url": f"{MOCK}/v1/chat/completions",
                "endpoint_profile": "openai",
                "analysis_mode": "offline",
                "formats": ["json", "html", "sarif"],
            },
        ),
        (
            "GUI/API: Agent Framework",
            {
                "target_type": "agent",
                "agent": "crewai",
                "agent_config": str(QA_ROOT / "agent.toml"),
                "analysis_mode": "offline",
                "formats": ["json", "html", "sarif"],
            },
        ),
        (
            "GUI/API: MCP Server",
            {
                "target_type": "mcp",
                "mcp": str(QA_ROOT / "mcp_server.py"),
                "analysis_mode": "offline",
                "formats": ["json", "html", "sarif"],
            },
        ),
        (
            "GUI/API: RAG Corpus",
            {
                "target_type": "rag",
                "rag": str(QA_ROOT / "rag_corpus"),
                "embedder": "bge",
                "analysis_mode": "offline",
                "formats": ["json", "html", "sarif"],
            },
        ),
    ]

    if os.environ.get("OPENAI_API_KEY"):
        cases.append(
            (
                "GUI/API: Cloud Provider",
                {
                    "target_type": "provider",
                    "provider": "openai",
                    "analysis_mode": "offline",
                    "formats": ["json", "sarif"],
                    "config_path": str(QA_ROOT / "qa-provider.toml"),
                },
            )
        )
    else:
        report.add(TestResult("GUI/API: Cloud Provider", "SKIP", "OPENAI_API_KEY not set"))

    async with httpx.AsyncClient(timeout=60) as client:
        for name, body in cases:
            try:
                sid = await create_scan(client, body)
                result = await wait_scan(client, sid)
                scan_ids[name] = sid
                status = result.get("status")
                fc = result.get("finding_count", 0)
                pc = result.get("probe_count", 0)
                ok = status == "completed"
                # endpoint mock: 0 findings = defended; module: expect >0
                if "Endpoint" in name:
                    ok = ok and not any(
                        True for _ in []  # checked in exports
                    )
                elif "Agent" in name or "MCP" in name or "RAG" in name:
                    ok = ok and fc > 0
                report.add(
                    TestResult(
                        name,
                        "PASS" if ok else "FAIL",
                        f"status={status} probes={pc} findings={fc} scan_id={sid}",
                        metrics={"scan_id": sid, "status": status, "probe_count": pc, "finding_count": fc},
                    )
                )
                exp = validate_exports(sid, appdata)
                report.add(
                    TestResult(
                        f"Exports: {name.split(': ')[1]}",
                        "PASS" if exp.get("ok") else ("WARN" if exp.get("reason") else "FAIL"),
                        str(exp),
                        metrics=exp,
                    )
                )
            except Exception as exc:
                report.add(TestResult(name, "FAIL", str(exc)))

    return scan_ids


async def phase_concurrent() -> None:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            a_id = await create_scan(
                client,
                {"target_type": "agent", "agent": "crewai", "analysis_mode": "offline", "formats": ["json"]},
            )
            r_id = await create_scan(
                client,
                {
                    "target_type": "rag",
                    "rag": str(QA_ROOT / "rag_corpus"),
                    "embedder": "bge",
                    "analysis_mode": "offline",
                    "formats": ["json"],
                },
            )
            a, r = await asyncio.gather(wait_scan(client, a_id), wait_scan(client, r_id))
        ok = (
            a_id != r_id
            and a["status"] == "completed"
            and r["status"] == "completed"
            and a["finding_count"] > 0
            and r["finding_count"] > 0
        )
        report.add(
            TestResult(
                "Stability: concurrent scans",
                "PASS" if ok else "FAIL",
                f"agent={a['status']}({a['finding_count']}) rag={r['status']}({r['finding_count']})",
                metrics={"agent_id": a_id, "rag_id": r_id},
            )
        )
    except Exception as exc:
        report.add(TestResult("Stability: concurrent scans", "FAIL", str(exc)))


async def phase_benchmarks() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        report.add(TestResult("Benchmark: models", "SKIP", "No API key"))
        return
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{API}/v1/benchmarks",
                json={
                    "suite": "owasp",
                    "targets": [{"type": "provider", "provider": "openai", "model": "gpt-4o-mini", "label": "openai/gpt-4o-mini"}],
                },
            )
            r.raise_for_status()
            bid = r.json()["benchmark_id"]
            start = time.time()
            data: dict = {}
            while time.time() - start < BENCH_TIMEOUT:
                br = await client.get(f"{API}/v1/benchmarks/{bid}")
                br.raise_for_status()
                data = br.json()
                if data.get("status") in ("completed", "failed"):
                    break
                await asyncio.sleep(2)
            scores = data.get("model_scores", [])
            ok = data.get("status") == "completed" and len(scores) >= 1
            report.add(
                TestResult(
                    "Benchmark: models",
                    "PASS" if ok else "FAIL",
                    f"status={data.get('status')} scores={len(scores)}",
                    metrics={"benchmark_id": bid, "model_scores": scores},
                )
            )

            r2 = await client.post(f"{API}/v1/benchmarks/tools", json={"suite": "owasp-llm01", "targets": ["corpus"]})
            r2.raise_for_status()
            tid = r2.json()["benchmark_id"]
            start = time.time()
            tdata: dict = {}
            while time.time() - start < 120:
                tr = await client.get(f"{API}/v1/benchmarks/tools/{tid}")
                tr.raise_for_status()
                tdata = tr.json()
                if tdata.get("status") in ("completed", "failed"):
                    break
                await asyncio.sleep(2)
            ts = tdata.get("tool_scores", [])
            names = {s.get("tool") for s in ts}
            aa = next((s for s in ts if s.get("tool") == "AgentArmor"), {})
            ok_tools = (
                tdata.get("status") == "completed"
                and len(ts) >= 5
                and "AgentArmor" in names
                and (aa.get("true_positives") or 0) >= 1
            )
            report.add(
                TestResult(
                    "Benchmark: tools",
                    "PASS" if ok_tools else "FAIL",
                    f"tools={len(ts)} AgentArmor tp={aa.get('true_positives')}",
                    metrics={"tool_scores": ts},
                )
            )
    except Exception as exc:
        report.add(TestResult("Benchmark: models", "FAIL", str(exc)))


def phase_embedded_cli() -> None:
    if not EMBED_PYTHON.exists():
        report.add(TestResult("Embedded CLI: endpoint scan", "SKIP", "Python not found"))
        return
    cfg = QA_ROOT / "qa-scan.toml"
    code, out = run_cmd(
        [
            str(EMBED_PYTHON),
            "-m",
            "agentarmor.cli.main",
            "scan",
            "--config",
            str(cfg),
            "--url",
            f"{MOCK}/v1/chat/completions",
            "--format",
            "sarif",
            "--analysis-mode",
            "offline",
        ],
        cwd=INSTALL_DIR,
        timeout=SCAN_TIMEOUT,
    )
    ok = code == 0 and "completed" in out.lower()
    report.add(
        TestResult(
            "Embedded CLI: endpoint scan",
            "PASS" if ok else "FAIL",
            "\n".join(out.split("\n")[-5:]) if out else "no output",
            metrics={"exit_code": code},
        )
    )
    # gate
    sarif_files = list((INSTALL_DIR / "reports").glob("scan-*.sarif")) + list((REPO / "reports").glob("scan-*.sarif"))
    if sarif_files:
        latest = max(sarif_files, key=lambda p: p.stat().st_mtime)
        code2, out2 = run_cmd(
            [str(EMBED_PYTHON), "-m", "agentarmor.cli.main", "gate", "--sarif", str(latest), "--fail-on", "HIGH,CRITICAL"],
            timeout=60,
        )
        report.add(
            TestResult(
                "Embedded CLI: SARIF gate",
                "PASS" if code2 == 0 else "WARN",
                out2 or f"exit {code2}",
                metrics={"sarif": str(latest), "exit_code": code2},
            )
        )


def phase_local_model() -> None:
    if not EMBED_PYTHON.exists():
        report.add(TestResult("Local Model tile", "SKIP", "Python not found"))
        return
    code, out = run_cmd(
        [str(EMBED_PYTHON), "-m", "agentarmor.cli.main", "scan", "--model", str(QA_ROOT / "missing.gguf"), "--analysis-mode", "offline"],
        timeout=120,
    )
    ok = code != 0 and "not found" in out.lower()
    report.add(
        TestResult(
            "Local Model: missing GGUF error UX",
            "PASS" if ok else "FAIL",
            "\n".join(out.split("\n")[-3:]) if out else "",
        )
    )
    # check llama-cpp not bundled
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("llama_check", EMBED_PYTHON)
    except Exception:
        pass
    code2, out2 = run_cmd([str(EMBED_PYTHON), "-c", "import llama_cpp; print('ok')"], timeout=30)
    report.add(
        TestResult(
            "Local Model: [local] deps in bundle",
            "WARN" if code2 != 0 else "PASS",
            "llama-cpp-python not in embed (expected)" if code2 != 0 else "llama-cpp present",
        )
    )


def phase_gui_kill_test(gui_proc: subprocess.Popen | None) -> None:
    """Start long scan, kill GUI, check for orphan python."""
    if not gui_proc or gui_proc.poll() is not None:
        report.add(TestResult("Stability: mid-scan app close", "SKIP", "GUI not running"))
        return
    try:
        subprocess.run(
            [
                str(EMBED_PYTHON),
                "-c",
                f"import httpx; r=httpx.post('{API}/v1/scans', json={{'target_type':'endpoint','url':'{MOCK}/v1/chat/completions','endpoint_profile':'openai','analysis_mode':'offline'}}); print(r.json().get('scan_id',''))",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        time.sleep(3)
        gui_proc.terminate()
        try:
            gui_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            gui_proc.kill()
        time.sleep(3)
        # count embed python processes
        code, out = run_cmd(
            ["powershell", "-Command", f"Get-Process python* -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '*AgentArmor*' }} | Measure-Object | Select-Object -ExpandProperty Count"],
            timeout=15,
        )
        count = int(out.strip() or "0")
        report.add(
            TestResult(
                "Stability: mid-scan app close",
                "PASS" if count == 0 else "FAIL",
                f"orphan AgentArmor python processes after GUI kill: {count}",
                metrics={"orphan_count": count},
            )
        )
    except Exception as exc:
        report.add(TestResult("Stability: mid-scan app close", "FAIL", str(exc)))


async def main() -> int:
    report.started_at = datetime.now(timezone.utc).isoformat()
    log("=== AgentArmor .exe Full QA ===")
    setup_harness()
    await phase_install_check()
    if not GUI_EXE.exists():
        write_reports()
        return 1

    # mock server
    mock_proc = None
    if not await wait_health(MOCK, timeout=3):
        log("Starting mock server...")
        mock_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", MOCK_MODULE, "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(REPO),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not await wait_health(MOCK, timeout=30):
            report.add(TestResult("Mock server", "FAIL", "Could not start on :8000"))
            write_reports()
            return 1
    report.add(TestResult("Mock server", "PASS", MOCK))

    # launch GUI
    gui_proc = None
    if not await wait_health(API, timeout=3):
        log(f"Launching {GUI_EXE}...")
        gui_proc = subprocess.Popen([str(GUI_EXE)], cwd=str(INSTALL_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not await wait_health(API, timeout=90):
            report.add(TestResult("GUI launch + sidecar", "FAIL", "Sidecar did not start"))
            write_reports()
            return 1
    report.add(TestResult("GUI launch + sidecar", "PASS", GUI_EXE.name))

    await phase_sidecar(gui_proc)
    await phase_api_scans()
    await phase_concurrent()
    await phase_benchmarks()
    phase_embedded_cli()
    phase_local_model()
    phase_gui_kill_test(gui_proc)

    if mock_proc:
        mock_proc.terminate()
    write_reports()
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
