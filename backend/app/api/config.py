from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_container, require_user
from app.exchange.factory import build_exchange_adapter
from app.schemas import (
    ExchangeConfigUpdateRequest,
    ExchangeConfigView,
    RuntimeConfig,
    RuntimeProfileConfig,
    RuntimeProfileView,
    SecretsStatus,
    TelegramConfigUpdateRequest,
    TelegramConfigView,
)
from app.services.profile_mapper import profile_to_runtime_config, runtime_to_profile_view

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/runtime", response_model=RuntimeConfig, dependencies=[Depends(require_user)])
async def get_runtime_config(container=Depends(get_container)) -> RuntimeConfig:
    return container.config_store.get()


@router.put("/runtime", response_model=RuntimeConfig, dependencies=[Depends(require_user)])
async def update_runtime_config(payload: RuntimeConfig, container=Depends(get_container)) -> RuntimeConfig:
    cfg = container.config_store.update(payload.model_dump())
    await container.engine.refresh_runtime_config()
    return cfg


@router.get("/runtime/profile", response_model=RuntimeProfileView, dependencies=[Depends(require_user)])
async def get_runtime_profile(container=Depends(get_container)) -> RuntimeProfileView:
    return runtime_to_profile_view(container.config_store.get())


@router.put("/runtime/profile", response_model=RuntimeProfileView, dependencies=[Depends(require_user)])
async def update_runtime_profile(payload: RuntimeProfileConfig, container=Depends(get_container)) -> RuntimeProfileView:
    mapped = profile_to_runtime_config(payload, container.config_store.get())
    cfg = container.config_store.update(mapped.model_dump())
    await container.engine.refresh_runtime_config()
    return runtime_to_profile_view(cfg)


@router.get("/exchange", response_model=ExchangeConfigView, dependencies=[Depends(require_user)])
async def get_exchange_config(container=Depends(get_container)) -> ExchangeConfigView:
    return container.exchange_config_store.to_view()


@router.put("/exchange", response_model=ExchangeConfigView, dependencies=[Depends(require_user)])
async def update_exchange_config(
    payload: ExchangeConfigUpdateRequest,
    container=Depends(get_container),
) -> ExchangeConfigView:
    if container.engine.mode not in {"idle", "halted"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="引擎运行中禁止修改 API 配置，请先停止引擎",
        )

    cfg = container.exchange_config_store.update(payload)
    adapter = build_exchange_adapter(
        container.settings,
        grvt_env=cfg.grvt_env,
        grvt_api_key=cfg.grvt_api_key,
        grvt_api_secret=cfg.grvt_api_secret,
        grvt_trading_account_id=cfg.grvt_trading_account_id,
    )
    container.adapter = adapter
    container.engine.replace_adapter(adapter)
    return container.exchange_config_store.to_view()


@router.get("/telegram", response_model=TelegramConfigView, dependencies=[Depends(require_user)])
async def get_telegram_config(container=Depends(get_container)) -> TelegramConfigView:
    return container.telegram_config_store.to_view()


@router.put("/telegram", response_model=TelegramConfigView, dependencies=[Depends(require_user)])
async def update_telegram_config(
    payload: TelegramConfigUpdateRequest,
    container=Depends(get_container),
) -> TelegramConfigView:
    if container.engine.mode not in {"idle", "halted"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="引擎运行中禁止修改配置，请先停止引擎",
        )
    container.telegram_config_store.update(payload)
    return container.telegram_config_store.to_view()


@router.get("/secrets/status", response_model=SecretsStatus, dependencies=[Depends(require_user)])
async def get_secrets_status(container=Depends(get_container)) -> SecretsStatus:
    exchange_cfg = container.exchange_config_store.get()
    telegram_cfg = container.telegram_config_store.get()
    settings = container.settings
    return SecretsStatus(
        grvt_api_key_configured=bool(exchange_cfg.grvt_api_key),
        grvt_api_secret_configured=bool(exchange_cfg.grvt_api_secret),
        grvt_trading_account_id_configured=bool(exchange_cfg.grvt_trading_account_id),
        app_jwt_secret_configured=bool(settings.app_jwt_secret and settings.app_jwt_secret != "change-me"),
        telegram_configured=bool(telegram_cfg.telegram_bot_token and telegram_cfg.telegram_chat_id),
    )
