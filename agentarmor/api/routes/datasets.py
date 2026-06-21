"""Research dataset export API."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agentarmor.core.config import load_config
from agentarmor.db.session import ScanRepository
from agentarmor.export.dataset import export_dataset_jsonl

router = APIRouter(prefix="/v1/datasets", tags=["datasets"])

_config_path = Path("AgentArmor.toml")
_app_config = load_config(_config_path if _config_path.exists() else None)
_repo = ScanRepository(_app_config.database_url)


class DatasetExportRequest(BaseModel):
    scan_ids: list[str] = Field(default_factory=list)
    anonymize: bool = True


@router.post("/export")
def export_dataset(body: DatasetExportRequest) -> dict:
    _repo.ensure_schema()
    try:
        path = export_dataset_jsonl(
            _repo,
            scan_ids=body.scan_ids or None,
            anonymize=body.anonymize,
        )
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    return {"path": str(path), "format": "jsonl", "anonymized": body.anonymize}


@router.get("/export/download")
def download_latest_export(path: str) -> FileResponse:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "export file not found")
    return FileResponse(file_path, media_type="application/x-ndjson", filename=file_path.name)
