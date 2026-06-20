"""Benchmark persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from agentarmor.benchmark.models import BenchmarkRun, BenchmarkStatus
from agentarmor.db.models import BenchmarkRecord, get_session_factory, init_db


class BenchmarkRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._session_factory = get_session_factory(database_url)

    def ensure_schema(self) -> None:
        init_db(self._database_url)

    def save_run(self, run: BenchmarkRun) -> None:
        with self._session_factory() as session:
            record = BenchmarkRecord(
                id=run.id,
                suite_id=run.suite_id,
                suite_name=run.suite_name,
                status=run.status.value,
                scores_json=json.dumps(
                    [s.model_dump(mode="json") for s in run.model_scores]
                ),
                metadata_json=json.dumps(run.metadata),
                started_at=run.started_at,
                completed_at=run.completed_at,
            )
            session.merge(record)
            session.commit()

    def get_run(self, run_id: str) -> BenchmarkRun | None:
        with self._session_factory() as session:
            record = session.get(BenchmarkRecord, run_id)
            if not record:
                return None
            from agentarmor.benchmark.models import ModelScore

            scores = [ModelScore.model_validate(s) for s in json.loads(record.scores_json or "[]")]
            return BenchmarkRun(
                id=record.id,
                suite_id=record.suite_id,
                suite_name=record.suite_name,
                status=BenchmarkStatus(record.status),
                model_scores=scores,
                started_at=record.started_at,
                completed_at=record.completed_at,
                metadata=json.loads(record.metadata_json or "{}"),
            )

    def list_runs(self, limit: int = 20) -> list[BenchmarkRun]:
        with self._session_factory() as session:
            records = (
                session.query(BenchmarkRecord)
                .order_by(BenchmarkRecord.created_at.desc())
                .limit(limit)
                .all()
            )
            runs: list[BenchmarkRun] = []
            for record in records:
                run = self.get_run(record.id)
                if run:
                    runs.append(run)
            return runs
