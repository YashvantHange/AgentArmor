"""Database session helpers and persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from agentarmor.core.models import Finding, Scan, ScanStatus, Target, TargetType
from agentarmor.db.models import FindingRecord, ScanRecord, get_session_factory, init_db


class ScanRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._session_factory = get_session_factory(database_url)

    def ensure_schema(self) -> None:
        init_db(self._database_url)

    def save_scan(self, scan: Scan) -> None:
        with self._session_factory() as session:
            record = ScanRecord(
                id=scan.id,
                target_type=scan.target.type.value,
                target_url=scan.target.url,
                status=scan.status.value,
                probe_count=scan.probe_count,
                finding_count=scan.finding_count,
                metadata_json=json.dumps(scan.metadata),
                started_at=scan.started_at,
                completed_at=scan.completed_at,
            )
            session.merge(record)
            session.commit()

    def get_scan(self, scan_id: str) -> Scan | None:
        with self._session_factory() as session:
            record = session.get(ScanRecord, scan_id)
            if not record:
                return None
            return Scan(
                id=record.id,
                target=Target(type=TargetType(record.target_type), url=record.target_url),
                status=ScanStatus(record.status),
                probe_count=record.probe_count,
                finding_count=record.finding_count,
                started_at=record.started_at,
                completed_at=record.completed_at,
                metadata=json.loads(record.metadata_json or "{}"),
            )

    def save_finding(self, finding: Finding) -> None:
        self._write_finding(finding, merge=False)

    def merge_finding(self, finding: Finding) -> None:
        self._write_finding(finding, merge=True)

    def _write_finding(self, finding: Finding, *, merge: bool) -> None:
        meta = dict(finding.metadata)
        with self._session_factory() as session:
            record = FindingRecord(
                id=finding.id,
                scan_id=finding.scan_id,
                probe_id=finding.probe_id,
                probe_name=finding.probe_name,
                owasp_json=json.dumps(finding.owasp),
                title=finding.title,
                description=finding.description,
                severity=finding.severity.value,
                decision=finding.decision.value,
                risk_score=finding.risk_score,
                evidence_json=json.dumps(finding.evidence),
                request_summary=finding.request_summary,
                response_excerpt=finding.response_excerpt,
                metrics_json=json.dumps(meta),
                cluster_id=meta.get("cluster_id"),
                cluster_size=int(meta.get("cluster_size", 1)),
                related_probe_ids_json=json.dumps(meta.get("related_probe_ids", [])),
                root_cause=meta.get("root_cause"),
                confidence=meta.get("detection_confidence"),
                created_at=finding.created_at,
            )
            if merge:
                session.merge(record)
            else:
                session.merge(record)
            session.commit()

    def list_findings(self, scan_id: str | None = None) -> list[Finding]:
        with self._session_factory() as session:
            query = session.query(FindingRecord)
            if scan_id:
                query = query.filter(FindingRecord.scan_id == scan_id)
            records = query.order_by(FindingRecord.created_at.desc()).all()
            return [_finding_from_record(r) for r in records]

    def count_web_scans_since(self, since: datetime) -> int:
        with self._session_factory() as session:
            records = (
                session.query(ScanRecord)
                .filter(ScanRecord.created_at >= since)
                .all()
            )
            count = 0
            for record in records:
                meta = json.loads(record.metadata_json or "{}")
                if meta.get("scan_kind") == "web":
                    count += 1
            return count


def _finding_from_record(record: FindingRecord) -> Finding:
    from agentarmor.core.models import Decision, Severity

    meta = json.loads(record.metrics_json or "{}")
    if record.cluster_id:
        meta.setdefault("cluster_id", record.cluster_id)
    if record.cluster_size and record.cluster_size > 1:
        meta.setdefault("cluster_size", record.cluster_size)
    if record.root_cause:
        meta.setdefault("root_cause", record.root_cause)
    if record.confidence is not None:
        meta.setdefault("detection_confidence", record.confidence)
    related = json.loads(record.related_probe_ids_json or "[]")
    if related:
        meta.setdefault("related_probe_ids", related)

    return Finding(
        id=record.id,
        scan_id=record.scan_id,
        probe_id=record.probe_id,
        probe_name=record.probe_name,
        owasp=json.loads(record.owasp_json),
        title=record.title,
        description=record.description,
        severity=Severity(record.severity),
        decision=Decision(record.decision),
        risk_score=record.risk_score,
        evidence=json.loads(record.evidence_json),
        request_summary=record.request_summary,
        response_excerpt=record.response_excerpt,
        metadata=meta,
        created_at=record.created_at or datetime.now(timezone.utc),
    )
