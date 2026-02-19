from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_container, require_user
from app.core.settings import Settings, get_settings
from app.schemas import RuntimeConfig, SecretsStatus

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/runtime", response_model=RuntimeConfig, dependencies=[Depends(require_user)])
async def get_runtime_config(container=Depends(get_container)) -> RuntimeConfig:
    return container.config_store.get()


@router.put("/runtime", response_model=RuntimeConfig, dependencies=[Depends(require_user)])
async def update_runtime_config(payload: RuntimeConfig, container=Depends(get_container)) -> RuntimeConfig:
    cfg = container.config_store.update(payload.model_dump())
    await container.engine.refresh_runtime_config()
    return cfg


@router.get("/secrets/status", response_model=SecretsStatus, dependencies=[Depends(require_user)])
async def get_secrets_status(settings: Settings = Depends(get_settings)) -> SecretsStatus:
    return SecretsStatus(
        grvt_api_key_configured=bool(settings.grvt_api_key),
        grvt_api_secret_configured=bool(settings.grvt_api_secret),
        grvt_trading_account_id_configured=bool(settings.grvt_trading_account_id),
        app_jwt_secret_configured=bool(settings.app_jwt_secret and settings.app_jwt_secret != "change-me"),
        telegram_configured=bool(settings.telegram_bot_token and settings.telegram_chat_id),
    )
