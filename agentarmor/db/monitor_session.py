"""Monitoring schedule persistence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from agentarmor.db.models import ScheduleRecord, get_session_factory, init_db
from agentarmor.monitoring.models import MonitorSchedule


class MonitorRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._session_factory = get_session_factory(database_url)

    def ensure_schema(self) -> None:
        init_db(self._database_url)

    def save_schedule(self, schedule: MonitorSchedule) -> MonitorSchedule:
        with self._session_factory() as session:
            record = ScheduleRecord(
                id=schedule.id,
                name=schedule.name,
                target_type=schedule.target_type,
                config_json=json.dumps(schedule.target_config),
                cron=schedule.cron,
                enabled=1 if schedule.enabled else 0,
                last_run_at=_parse_dt(schedule.last_run_at),
                last_scan_id=schedule.last_scan_id,
                last_finding_count=schedule.last_finding_count,
                drift_detected=1 if schedule.drift_detected else 0,
            )
            session.merge(record)
            session.commit()
        return schedule

    def create_schedule(
        self,
        *,
        name: str,
        target_type: str,
        target_config: dict,
        cron: str = "daily",
    ) -> MonitorSchedule:
        schedule = MonitorSchedule(
            id=str(uuid.uuid4()),
            name=name,
            target_type=target_type,
            target_config=target_config,
            cron=cron,
        )
        return self.save_schedule(schedule)

    def list_schedules(self) -> list[MonitorSchedule]:
        with self._session_factory() as session:
            records = session.query(ScheduleRecord).order_by(ScheduleRecord.created_at.desc()).all()
            return [_from_record(r) for r in records]

    def get_schedule(self, schedule_id: str) -> MonitorSchedule | None:
        with self._session_factory() as session:
            record = session.get(ScheduleRecord, schedule_id)
            return _from_record(record) if record else None

    def delete_schedule(self, schedule_id: str) -> bool:
        with self._session_factory() as session:
            record = session.get(ScheduleRecord, schedule_id)
            if not record:
                return False
            session.delete(record)
            session.commit()
            return True

    def update_after_run(
        self,
        schedule_id: str,
        *,
        scan_id: str,
        finding_count: int,
        drift_detected: bool,
    ) -> None:
        with self._session_factory() as session:
            record = session.get(ScheduleRecord, schedule_id)
            if not record:
                return
            record.last_run_at = datetime.now(timezone.utc)
            record.last_scan_id = scan_id
            record.last_finding_count = finding_count
            record.drift_detected = 1 if drift_detected else 0
            session.commit()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _from_record(record: ScheduleRecord) -> MonitorSchedule:
    return MonitorSchedule(
        id=record.id,
        name=record.name,
        target_type=record.target_type,
        target_config=json.loads(record.config_json or "{}"),
        cron=record.cron,
        enabled=bool(record.enabled),
        last_run_at=record.last_run_at.isoformat() if record.last_run_at else None,
        last_scan_id=record.last_scan_id,
        last_finding_count=record.last_finding_count,
        drift_detected=bool(record.drift_detected),
    )
