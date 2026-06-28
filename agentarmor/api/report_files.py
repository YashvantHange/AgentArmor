"""Shared report path resolution and download helpers for scan APIs."""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

from fastapi import HTTPException

from agentarmor.core.models import Scan

REPORT_FORMATS = ("pdf", "html", "sarif", "json", "csv")

FORMAT_EXTENSIONS: dict[str, str] = {
    "pdf": ".pdf",
    "html": ".html",
    "sarif": ".sarif",
    "json": ".json",
    "csv": ".csv",
}

MEDIA_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "html": "text/html",
    "sarif": "application/sarif+json",
    "json": "application/json",
    "csv": "text/csv",
    "zip": "application/zip",
}


def _ensure_under_root(path: Path, root: Path) -> Path:
    """Resolve path and reject traversal outside output_dir."""
    root_resolved = root.resolve()
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise HTTPException(404, "report file not found") from exc
    if not resolved.is_relative_to(root_resolved):
        raise HTTPException(403, "report path outside output directory")
    if not resolved.is_file():
        raise HTTPException(404, "report file not found")
    return resolved


def _candidate_paths(scan: Scan, fmt: str, output_dir: Path) -> list[Path]:
    ext = FORMAT_EXTENSIONS[fmt]
    candidates: list[Path] = []
    for raw in scan.metadata.get("reports", []):
        p = Path(str(raw))
        if p.suffix.lower() == ext:
            candidates.append(p)
    candidates.append(output_dir / f"scan-{scan.id}{ext}")
    return candidates


def resolve_report_path(scan: Scan, fmt: str, output_dir: Path) -> Path:
    """Return a validated report file path for a single format."""
    normalized = fmt.lower()
    if normalized not in FORMAT_EXTENSIONS:
        raise HTTPException(400, f"unsupported format: {fmt}")

    root = output_dir.resolve()
    for candidate in _candidate_paths(scan, normalized, root):
        if candidate.exists() and candidate.is_file():
            return _ensure_under_root(candidate, root)

    raise HTTPException(404, f"{normalized} report not found")


def collect_report_paths(scan: Scan, output_dir: Path) -> list[Path]:
    """Collect all available report files for a scan."""
    root = output_dir.resolve()
    found: list[Path] = []
    seen: set[Path] = set()

    for fmt in REPORT_FORMATS:
        for candidate in _candidate_paths(scan, fmt, root):
            if not candidate.exists() or not candidate.is_file():
                continue
            try:
                resolved = _ensure_under_root(candidate, root)
            except HTTPException:
                continue
            if resolved not in seen:
                seen.add(resolved)
                found.append(resolved)

    for raw in scan.metadata.get("reports", []):
        p = Path(str(raw))
        if not p.exists() or not p.is_file():
            continue
        try:
            resolved = _ensure_under_root(p, root)
        except HTTPException:
            continue
        if resolved not in seen:
            seen.add(resolved)
            found.append(resolved)

    return found


def create_zip_archive(scan: Scan, output_dir: Path) -> Path:
    """Bundle available reports into a temp ZIP file; caller must delete after send."""
    paths = collect_report_paths(scan, output_dir)
    if not paths:
        raise HTTPException(404, "no reports available for download")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    zip_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in paths:
                zf.write(path, arcname=path.name)
    except OSError as exc:
        os.unlink(zip_path)
        raise HTTPException(500, "failed to create report archive") from exc
    return zip_path


def unlink_path(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
