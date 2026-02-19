import asyncio
from unittest.mock import AsyncMock, Mock

from app.engine.strategy_engine import StrategyEngine
from app.models import PositionSnapshot, QuoteDecision
from app.schemas import RuntimeConfig


def _build_engine(config: RuntimeConfig | None = None):
    adapter = Mock()
    adapter.cancel_all_orders = AsyncMock()
    adapter.fetch_open_orders = AsyncMock(return_value=[])
    adapter.place_limit_order = AsyncMock()

    config_store = Mock()
    config_store.get = Mock(return_value=config or RuntimeConfig())

    monitor = Mock()
    monitor.record_cancel = Mock()

    event_bus = Mock()
    event_bus.publish = AsyncMock()

    alert = Mock()
    alert.send = AsyncMock()

    engine = StrategyEngine(
        adapter=adapter,
        config_store=config_store,
        monitor=monitor,
        event_bus=event_bus,
        alert_service=alert,
    )
    return engine, adapter, config_store, event_bus, alert


def test_start_enters_running_mode_immediately(monkeypatch):
    engine, adapter, _, _, alert = _build_engine()

    async def fake_run_loop():
        await engine._stop_event.wait()  # noqa: SLF001

    monkeypatch.setattr(engine, "_run_loop", fake_run_loop)

    async def scenario():
        mode = await engine.start()
        assert mode == "running"
        assert engine.mode == "running"
        assert engine._readonly_until is None  # noqa: SLF001
        await engine.stop("test")

    asyncio.run(scenario())

    adapter.cancel_all_orders.assert_awaited_once()
    alert.send.assert_any_await("Engine", "做市引擎已启动，开始自动做市")


def test_sync_orders_places_both_sides_when_orders_missing():
    cfg = RuntimeConfig(symbol="BNB_USDT_Perp")
    engine, adapter, _, _, _ = _build_engine(cfg)

    position = PositionSnapshot(symbol=cfg.symbol, base_position=0.0, notional=0.0)
    decision = QuoteDecision(
        bid_price=100.0,
        ask_price=100.2,
        quote_size_base=0.1,
        quote_size_notional=10.0,
        spread_bps=20.0,
        gamma=0.2,
        reservation_price=100.1,
    )

    async def scenario():
        return await engine._sync_orders(cfg, position, decision)  # noqa: SLF001

    result = asyncio.run(scenario())

    assert result.requoted is True
    assert set(result.reason.split(",")) == {"missing-side-buy", "missing-side-sell"}

    adapter.cancel_all_orders.assert_awaited_once_with(cfg.symbol)
    assert adapter.place_limit_order.await_count == 2

    side_to_call = {call.kwargs["side"]: call.kwargs for call in adapter.place_limit_order.await_args_list}
    assert set(side_to_call.keys()) == {"buy", "sell"}
    assert side_to_call["buy"]["price"] == decision.bid_price
    assert side_to_call["sell"]["price"] == decision.ask_price
    assert side_to_call["buy"]["size"] == decision.quote_size_base
    assert side_to_call["sell"]["size"] == decision.quote_size_base
    assert side_to_call["buy"]["post_only"] is True
    assert side_to_call["sell"]["post_only"] is True
    assert side_to_call["buy"]["client_order_id"].isdigit()
    assert side_to_call["sell"]["client_order_id"].isdigit()


def test_ensure_min_quote_size_applies_floor():
    decision = QuoteDecision(
        bid_price=100.0,
        ask_price=100.2,
        quote_size_base=0.008,
        quote_size_notional=0.8,
        spread_bps=20.0,
        gamma=0.2,
        reservation_price=100.1,
    )

    StrategyEngine._ensure_min_quote_size(decision, mid_price=605.0, min_size_base=0.01)

    assert decision.quote_size_base == 0.01
    assert decision.quote_size_notional == 6.05


def test_post_only_guard_rounds_price_to_tick():
    decision = QuoteDecision(
        bid_price=606.081510934,
        ask_price=606.368489066,
        quote_size_base=0.01,
        quote_size_notional=6.06,
        spread_bps=4.0,
        gamma=0.2,
        reservation_price=606.22,
    )

    tick = StrategyEngine._infer_price_tick(606.22, 606.23)
    engine, _, _, _, _ = _build_engine()
    engine._post_only_guard(606.22, 606.23, decision, tick)  # noqa: SLF001

    assert tick == 0.01
    assert abs(decision.bid_price - round(decision.bid_price, 2)) < 1e-9
    assert abs(decision.ask_price - round(decision.ask_price, 2)) < 1e-9
    assert decision.bid_price <= 606.22
    assert decision.ask_price >= 606.23
    assert decision.bid_price < decision.ask_price
