from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from app.models import EngineTick, OrderSnapshot, TradeSnapshot
from app.schemas import MetricsSummary, TimeSeriesPoint


class MonitoringService:
    """聚合监控指标与时序数据。"""

    def __init__(self, max_points: int = 1200) -> None:
        self._summary = MetricsSummary(
            timestamp=datetime.now(timezone.utc),
            mid_price=0.0,
            spread_bps=0.0,
            sigma=0.0,
            sigma_zscore=0.0,
            inventory_base=0.0,
            inventory_notional=0.0,
            equity=0.0,
            pnl=0.0,
            drawdown_pct=0.0,
            quote_size_base=0.0,
            quote_size_notional=0.0,
            mode="idle",
            consecutive_failures=0,
        )
        self._series: dict[str, deque[TimeSeriesPoint]] = {
            "sigma": deque(maxlen=max_points),
            "spread_bps": deque(maxlen=max_points),
            "inventory_notional": deque(maxlen=max_points),
            "mid_price": deque(maxlen=max_points),
            "quote_size_notional": deque(maxlen=max_points),
        }
        self._open_orders: list[OrderSnapshot] = []
        self._recent_trades: list[TradeSnapshot] = []

    def update_tick(
        self,
        tick: EngineTick,
        drawdown_pct: float,
        mode: str,
        consecutive_failures: int,
    ) -> None:
        self._summary = MetricsSummary(
            timestamp=tick.timestamp,
            mid_price=tick.market.mid,
            spread_bps=tick.decision.spread_bps,
            sigma=tick.sigma,
            sigma_zscore=tick.sigma_zscore,
            inventory_base=tick.position.base_position,
            inventory_notional=tick.position.notional,
            equity=tick.equity,
            pnl=tick.pnl,
            drawdown_pct=drawdown_pct,
            quote_size_base=tick.decision.quote_size_base,
            quote_size_notional=tick.decision.quote_size_notional,
            mode=mode,
            consecutive_failures=consecutive_failures,
        )

        self._series["sigma"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.sigma))
        self._series["spread_bps"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.decision.spread_bps))
        self._series["inventory_notional"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.position.notional))
        self._series["mid_price"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.market.mid))
        self._series["quote_size_notional"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.decision.quote_size_notional))

    def update_orders(self, orders: list[OrderSnapshot]) -> None:
        self._open_orders = orders

    def update_trades(self, trades: list[TradeSnapshot]) -> None:
        self._recent_trades = trades[-100:]

    @property
    def summary(self) -> MetricsSummary:
        return self._summary

    def series(self) -> dict[str, list[TimeSeriesPoint]]:
        return {k: list(v) for k, v in self._series.items()}

    @property
    def open_orders(self) -> list[OrderSnapshot]:
        return list(self._open_orders)

    @property
    def recent_trades(self) -> list[TradeSnapshot]:
        return list(self._recent_trades)
