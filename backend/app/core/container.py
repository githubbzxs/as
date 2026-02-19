from __future__ import annotations

from dataclasses import dataclass

from app.core.settings import Settings
from app.engine.strategy_engine import StrategyEngine
from app.exchange.base import ExchangeAdapter
from app.backtest.service import BacktestService
from app.services.alerting import AlertService
from app.services.event_bus import EventBus
from app.services.exchange_config import ExchangeConfigStore
from app.services.monitoring import MonitoringService
from app.services.runtime_config import RuntimeConfigStore
from app.services.telegram_config import TelegramConfigStore


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    adapter: ExchangeAdapter
    config_store: RuntimeConfigStore
    exchange_config_store: ExchangeConfigStore
    telegram_config_store: TelegramConfigStore
    monitor: MonitoringService
    event_bus: EventBus
    alert_service: AlertService
    backtest_service: BacktestService
    engine: StrategyEngine
