from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_container, require_user
from app.schemas import EngineCommandResponse, HealthStatus

router = APIRouter(prefix="/api", tags=["engine"])


@router.get("/status", response_model=HealthStatus, dependencies=[Depends(require_user)])
async def status(container=Depends(get_container)) -> HealthStatus:
    return container.engine.status()


@router.post("/engine/start", response_model=EngineCommandResponse, dependencies=[Depends(require_user)])
async def start_engine(container=Depends(get_container)) -> EngineCommandResponse:
    mode = await container.engine.start()
    return EngineCommandResponse(message="引擎已启动", mode=mode)


@router.post("/engine/stop", response_model=EngineCommandResponse, dependencies=[Depends(require_user)])
async def stop_engine(container=Depends(get_container)) -> EngineCommandResponse:
    mode = await container.engine.stop(reason="manual")
    return EngineCommandResponse(message="引擎已停止", mode=mode)
