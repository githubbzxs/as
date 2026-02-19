from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, backtest, config, engine, monitor, ws
from app.backtest.service import BacktestService
from app.core.container import AppContainer
from app.core.settings import get_settings
from app.engine.strategy_engine import StrategyEngine
from app.exchange.factory import build_exchange_adapter
from app.services.alerting import AlertService
from app.services.event_bus import EventBus
from app.services.exchange_config import ExchangeConfigStore
from app.services.monitoring import MonitoringService
from app.services.runtime_config import RuntimeConfigStore
from app.services.telegram_config import TelegramConfigStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    config_store = RuntimeConfigStore(settings.runtime_config_file)
    exchange_config_store = ExchangeConfigStore(settings.exchange_config_file, settings)
    telegram_config_store = TelegramConfigStore(settings.telegram_config_file, settings)
    exchange_cfg = exchange_config_store.get()
    monitor_service = MonitoringService(max_points=1200)
    event_bus = EventBus(queue_size=settings.stream_queue_size)
    alert_service = AlertService(telegram_config_store)
    backtest_service = BacktestService(settings)
    adapter = build_exchange_adapter(
        settings,
        grvt_env=exchange_cfg.grvt_env,
        grvt_api_key=exchange_cfg.grvt_api_key,
        grvt_api_secret=exchange_cfg.grvt_api_secret,
        grvt_trading_account_id=exchange_cfg.grvt_trading_account_id,
    )

    strategy_engine = StrategyEngine(
        adapter=adapter,
        config_store=config_store,
        monitor=monitor_service,
        event_bus=event_bus,
        alert_service=alert_service,
    )

    app.state.container = AppContainer(
        settings=settings,
        adapter=adapter,
        config_store=config_store,
        exchange_config_store=exchange_config_store,
        telegram_config_store=telegram_config_store,
        monitor=monitor_service,
        event_bus=event_bus,
        alert_service=alert_service,
        backtest_service=backtest_service,
        engine=strategy_engine,
    )

    app.include_router(auth.router)
    app.include_router(engine.router)
    app.include_router(monitor.router)
    app.include_router(config.router)
    app.include_router(backtest.router)
    app.include_router(ws.router)

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(frontend_dist / "index.html")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        if app.state.container.engine.mode != "idle":
            await app.state.container.engine.stop(reason="shutdown")

    return app


app = create_app()
