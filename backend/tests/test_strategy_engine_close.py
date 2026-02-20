import asyncio
from unittest.mock import AsyncMock, Mock

from app.engine.strategy_engine import StrategyEngine
from app.exchange.base import PositionDustError
from app.models import PositionSnapshot
from app.schemas import RuntimeConfig


def _build_engine(cfg: RuntimeConfig):
    adapter = Mock()
    adapter.cancel_all_orders = AsyncMock()
    adapter.flatten_position_taker = AsyncMock()
    adapter.fetch_open_orders = AsyncMock(return_value=[])
    adapter.place_limit_order = AsyncMock()

    config_store = Mock()
    config_store.get = Mock(return_value=cfg)

    monitor = Mock()
    monitor.record_cancel = Mock()
    monitor.reset_session = Mock()
    monitor.summary = Mock(
        mode="running",
        equity=0,
        pnl_total=0,
        pnl_daily=0,
        inventory_notional=0,
        run_duration_sec=0,
        total_trade_volume_notional=0,
        total_fee_rebate=0,
        total_fee_cost=0,
    )

    event_bus = Mock()
    event_bus.publish = AsyncMock()

    alert = Mock()
    alert.send_event = AsyncMock()
    alert.send = AsyncMock()

    engine = StrategyEngine(
        adapter=adapter,
        config_store=config_store,
        monitor=monitor,
        event_bus=event_bus,
        alert_service=alert,
    )
    return engine, adapter, event_bus


def test_stop_flattens_position_until_zero():
    cfg = RuntimeConfig(close_retry_base_delay_sec=0.05, close_retry_max_delay_sec=0.1)
    engine, adapter, event_bus = _build_engine(cfg)

    adapter.fetch_position = AsyncMock(
        side_effect=[
            PositionSnapshot(symbol=cfg.symbol, base_position=0.5, notional=100.0),
            PositionSnapshot(symbol=cfg.symbol, base_position=0.1, notional=20.0),
            PositionSnapshot(symbol=cfg.symbol, base_position=0.0, notional=0.0),
        ]
    )

    asyncio.run(engine.stop("manual"))

    adapter.cancel_all_orders.assert_awaited_once_with(cfg.symbol)
    assert adapter.flatten_position_taker.await_count == 2
    event_bus.publish.assert_any_await(
        "close_done",
        {"symbol": cfg.symbol, "trigger": "stop", "retries": 2, "remaining_base": 0.0},
    )


def test_stop_retries_when_flatten_failed():
    cfg = RuntimeConfig(close_retry_base_delay_sec=0.05, close_retry_max_delay_sec=0.1)
    engine, adapter, _ = _build_engine(cfg)

    adapter.fetch_position = AsyncMock(
        side_effect=[
            PositionSnapshot(symbol=cfg.symbol, base_position=0.3, notional=80.0),
            PositionSnapshot(symbol=cfg.symbol, base_position=0.3, notional=80.0),
            PositionSnapshot(symbol=cfg.symbol, base_position=0.0, notional=0.0),
        ]
    )
    adapter.flatten_position_taker = AsyncMock(side_effect=[RuntimeError("boom"), None])

    asyncio.run(engine.stop("manual"))

    assert adapter.flatten_position_taker.await_count == 2


def test_stop_finishes_when_position_is_dust():
    cfg = RuntimeConfig(close_retry_base_delay_sec=0.05, close_retry_max_delay_sec=0.1)
    engine, adapter, event_bus = _build_engine(cfg)

    adapter.fetch_position = AsyncMock(return_value=PositionSnapshot(symbol=cfg.symbol, base_position=0.4, notional=2.0))
    adapter.flatten_position_taker = AsyncMock(side_effect=PositionDustError(cfg.symbol, 0.4, 1.0))

    asyncio.run(engine.stop("manual"))

    adapter.flatten_position_taker.assert_awaited_once_with(cfg.symbol)
    event_bus.publish.assert_any_await(
        "close_done",
        {
            "symbol": cfg.symbol,
            "trigger": "stop",
            "retries": 0,
            "remaining_base": 0.4,
            "dust": True,
            "min_close_size": 1.0,
        },
    )
