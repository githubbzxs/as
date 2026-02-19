from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_container, require_user
from app.schemas import BacktestJobRequest, BacktestJobView, BacktestReport

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/jobs", response_model=BacktestJobView, dependencies=[Depends(require_user)])
async def create_backtest_job(payload: BacktestJobRequest, container=Depends(get_container)) -> BacktestJobView:
    try:
        return await container.backtest_service.create_job(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=BacktestJobView, dependencies=[Depends(require_user)])
async def get_backtest_job(job_id: str, container=Depends(get_container)) -> BacktestJobView:
    job = await container.backtest_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回测任务不存在")
    return job


@router.get("/jobs/{job_id}/report", response_model=BacktestReport, dependencies=[Depends(require_user)])
async def get_backtest_report(job_id: str, container=Depends(get_container)) -> BacktestReport:
    job = await container.backtest_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回测任务不存在")
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"回测任务未完成，当前状态: {job.status}")

    report = await container.backtest_service.get_report(job_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="回测报告不存在")
    return report
