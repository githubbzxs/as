from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.backtest.engine import run_backtest
from app.core.settings import Settings
from app.schemas import BacktestJobRequest, BacktestJobStatus, BacktestJobView, BacktestReport


@dataclass(slots=True)
class _BacktestJobState:
    job_id: str
    request: BacktestJobRequest
    status: BacktestJobStatus
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    report: BacktestReport | None = None


class BacktestService:
    """管理简化回测任务。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jobs: dict[str, _BacktestJobState] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, payload: BacktestJobRequest) -> BacktestJobView:
        request = payload.model_copy(update={"data_file": str(self._resolve_data_file(payload.data_file))})
        now = datetime.now(timezone.utc)
        job_id = uuid4().hex
        state = _BacktestJobState(
            job_id=job_id,
            request=request,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        async with self._lock:
            self._jobs[job_id] = state

        asyncio.create_task(self._run(job_id), name=f"backtest-{job_id}")
        return self._to_view(state)

    async def get_job(self, job_id: str) -> BacktestJobView | None:
        async with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return None
            return self._to_view(state)

    async def get_report(self, job_id: str) -> BacktestReport | None:
        async with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return None
            return state.report

    async def _run(self, job_id: str) -> None:
        async with self._lock:
            state = self._jobs[job_id]
            state.status = "running"
            state.updated_at = datetime.now(timezone.utc)
            request = state.request

        try:
            report = await asyncio.to_thread(run_backtest, request)
            async with self._lock:
                finished = self._jobs[job_id]
                finished.status = "completed"
                finished.report = report
                finished.updated_at = datetime.now(timezone.utc)
        except Exception as exc:  # noqa: BLE001
            async with self._lock:
                failed = self._jobs[job_id]
                failed.status = "failed"
                failed.error = str(exc)
                failed.updated_at = datetime.now(timezone.utc)

    def _resolve_data_file(self, data_file: str) -> Path:
        raw = Path(data_file)
        if raw.is_absolute():
            path = raw
        else:
            path = Path(self._settings.data_dir) / raw
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"回测数据文件不存在: {resolved}")
        return resolved

    @staticmethod
    def _to_view(state: _BacktestJobState) -> BacktestJobView:
        return BacktestJobView(
            job_id=state.job_id,
            status=state.status,
            error=state.error,
            created_at=state.created_at,
            updated_at=state.updated_at,
        )
