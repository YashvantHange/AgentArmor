"""Report generation helpers."""

from __future__ import annotations

from pathlib import Path

from agentarmor.core.config import AppConfig
from agentarmor.core.models import Finding, Scan
from agentarmor import __version__
from agentarmor.reporting.csv_reporter import write_csv_report
from agentarmor.reporting.html_reporter import write_html_report
from agentarmor.reporting.json_reporter import write_json_report
from agentarmor.reporting.pdf_reporter import write_pdf_report
from agentarmor.reporting.sarif_reporter import write_sarif_report


def write_reports(
    config: AppConfig,
    scan: Scan,
    findings: list[Finding],
    output_dir: Path | None = None,
    formats: list[str] | None = None,
    output_file: Path | None = None,
) -> list[Path]:
    out = output_dir or Path(config.reporting.output_dir)
    fmts = [f.lower() for f in (formats or config.reporting.formats)]
    written: list[Path] = []

    if "json" in fmts:
        path = output_file if output_file and output_file.suffix == ".json" else out / f"scan-{scan.id}.json"
        written.append(write_json_report(scan, findings, path))

    if "sarif" in fmts:
        path = output_file if output_file and output_file.suffix == ".sarif" else out / f"scan-{scan.id}.sarif"
        written.append(write_sarif_report(scan, findings, path))

    if "html" in fmts:
        path = output_file if output_file and output_file.suffix == ".html" else out / f"scan-{scan.id}.html"
        written.append(write_html_report(scan, findings, path, version=__version__))

    if "pdf" in fmts:
        path = output_file if output_file and output_file.suffix == ".pdf" else out / f"scan-{scan.id}.pdf"
        written.append(write_pdf_report(scan, findings, path, version=__version__))

    if "csv" in fmts:
        path = output_file if output_file and output_file.suffix == ".csv" else out / f"scan-{scan.id}.csv"
        written.append(write_csv_report(scan, findings, path))

    return written
