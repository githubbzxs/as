from __future__ import annotations

from dataclasses import dataclass

from app.engine.strategy_engine import StrategyEngine
from app.exchange.base import ExchangeAdapter
from app.services.alerting import AlertService
from app.services.event_bus import EventBus
from app.services.monitoring import MonitoringService
from app.services.runtime_config import RuntimeConfigStore


@dataclass(slots=True)
class AppContainer:
    adapter: ExchangeAdapter
    config_store: RuntimeConfigStore
    monitor: MonitoringService
    event_bus: EventBus
    alert_service: AlertService
    engine: StrategyEngine
