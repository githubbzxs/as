from datetime import timedelta

from app.models import EngineTick, MarketSnapshot, PositionSnapshot, QuoteDecision, TradeSnapshot, utcnow
from app.services.monitoring import MonitoringService


def _build_tick(ts, pnl_total: float, pnl_daily: float) -> EngineTick:
    market = MarketSnapshot(
        symbol="BNB_USDT_Perp",
        bid=100.0,
        ask=100.2,
        mid=100.1,
        depth_score=1.0,
        trade_intensity=1.0,
        timestamp=ts,
    )
    decision = QuoteDecision(
        bid_price=100.0,
        ask_price=100.2,
        quote_size_base=0.1,
        quote_size_notional=10.0,
        spread_bps=20.0,
        gamma=0.1,
        reservation_price=100.1,
    )
    position = PositionSnapshot(symbol="BNB_USDT_Perp", base_position=0.2, notional=20.0)
    return EngineTick(
        timestamp=ts,
        market=market,
        decision=decision,
        position=position,
        equity=1000.0 + pnl_total,
        pnl=pnl_total,
        pnl_total=pnl_total,
        pnl_daily=pnl_daily,
        sigma=0.001,
        sigma_zscore=0.2,
        distance_bid_bps=1.0,
        distance_ask_bps=1.1,
    )


def test_monitoring_accumulates_trade_volume_and_fee_split():
    now = utcnow()
    monitor = MonitoringService(max_points=100)
    monitor.reset_session(started_at=now - timedelta(seconds=120))
    monitor.set_target_hourly_notional(10000.0)

    trades = [
        TradeSnapshot(trade_id="t1", side="buy", price=100.0, size=0.3, fee=-0.02, created_at=now),
        TradeSnapshot(trade_id="t2", side="sell", price=101.0, size=0.4, fee=0.03, created_at=now),
    ]
    monitor.update_trades(trades)
    monitor.update_tick(_build_tick(now, pnl_total=25.0, pnl_daily=12.0), drawdown_pct=1.0, mode="running", consecutive_failures=0)
    summary = monitor.summary

    assert summary.run_duration_sec >= 120
    assert summary.total_trade_count == 2
    assert summary.total_trade_volume_notional == abs(100.0 * 0.3) + abs(101.0 * 0.4)
    assert abs(summary.total_fee - 0.01) < 1e-9
    assert summary.total_fee_rebate == 0.02
    assert summary.total_fee_cost == 0.03
    assert summary.pnl_total == 25.0
    assert summary.pnl_daily == 12.0
    assert summary.trade_volume_notional_1h > 0
    assert summary.target_hourly_notional == 10000.0
    assert summary.target_completion_ratio > 0
    expected_ratio = summary.total_trade_volume_notional / (
        summary.target_hourly_notional * max(summary.run_duration_sec / 3600.0, 1.0 / 60.0)
    )
    assert abs(summary.target_completion_ratio_session - expected_ratio) < 1e-9
    expected_wear = -summary.pnl_total / summary.total_trade_volume_notional * 10000.0
    assert abs(summary.wear_per_10k - expected_wear) < 1e-9


def test_monitoring_dedup_trade_by_trade_id():
    now = utcnow()
    monitor = MonitoringService(max_points=100)
    monitor.reset_session(started_at=now - timedelta(seconds=30))
    trade = TradeSnapshot(trade_id="dup", side="buy", price=100.0, size=1.0, fee=-0.01, created_at=now)

    monitor.update_trades([trade, trade])
    monitor.update_tick(_build_tick(now, pnl_total=1.0, pnl_daily=1.0), drawdown_pct=0.1, mode="running", consecutive_failures=0)

    assert monitor.summary.total_trade_count == 1


def test_monitoring_ignores_trades_before_session_start():
    now = utcnow()
    session_start = now
    monitor = MonitoringService(max_points=100)
    monitor.reset_session(started_at=session_start)

    trades = [
        TradeSnapshot(
            trade_id="old",
            side="buy",
            price=100.0,
            size=0.3,
            fee=-0.02,
            created_at=session_start - timedelta(seconds=10),
        ),
        TradeSnapshot(
            trade_id="new",
            side="sell",
            price=101.0,
            size=0.4,
            fee=0.03,
            created_at=session_start + timedelta(seconds=1),
        ),
    ]
    monitor.update_trades(trades)
    monitor.update_tick(
        _build_tick(session_start + timedelta(seconds=2), pnl_total=1.0, pnl_daily=1.0),
        drawdown_pct=0.1,
        mode="running",
        consecutive_failures=0,
    )

    assert monitor.summary.total_trade_count == 1
    assert monitor.summary.total_trade_volume_notional == abs(101.0 * 0.4)
    assert monitor.summary.total_fee == 0.03
