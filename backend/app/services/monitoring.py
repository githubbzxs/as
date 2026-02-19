from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from math import ceil

from app.models import EngineTick, OrderSnapshot, TradeSnapshot
from app.schemas import MetricsSummary, TimeSeriesPoint


class MonitoringService:
    """聚合监控指标与时序数据。"""

    def __init__(self, max_points: int = 1200) -> None:
        self._summary = MetricsSummary(
            timestamp=datetime.now(timezone.utc),
            mid_price=0.0,
            spread_bps=0.0,
            distance_bid_bps=0.0,
            distance_ask_bps=0.0,
            sigma=0.0,
            sigma_zscore=0.0,
            inventory_base=0.0,
            inventory_notional=0.0,
            equity=0.0,
            pnl=0.0,
            drawdown_pct=0.0,
            quote_size_base=0.0,
            quote_size_notional=0.0,
            maker_fill_count_1m=0,
            cancel_count_1m=0,
            fill_to_cancel_ratio=0.0,
            time_in_book_p50_sec=0.0,
            time_in_book_p90_sec=0.0,
            open_order_age_buy_sec=0.0,
            open_order_age_sell_sec=0.0,
            requote_reason="none",
            mode="idle",
            consecutive_failures=0,
        )
        self._series: dict[str, deque[TimeSeriesPoint]] = {
            "sigma": deque(maxlen=max_points),
            "spread_bps": deque(maxlen=max_points),
            "distance_bid_bps": deque(maxlen=max_points),
            "distance_ask_bps": deque(maxlen=max_points),
            "inventory_notional": deque(maxlen=max_points),
            "mid_price": deque(maxlen=max_points),
            "quote_size_notional": deque(maxlen=max_points),
        }
        self._open_orders: list[OrderSnapshot] = []
        self._recent_trades: list[TradeSnapshot] = []
        self._cancel_events: deque[datetime] = deque(maxlen=max_points * 4)

    def update_tick(
        self,
        tick: EngineTick,
        drawdown_pct: float,
        mode: str,
        consecutive_failures: int,
        requote_reason: str = "none",
    ) -> None:
        now = tick.timestamp
        self._trim_window(self._cancel_events, now, window_sec=60.0)
        maker_fill_count_1m = sum(
            1
            for trade in self._recent_trades
            if 0.0 <= (now - trade.created_at).total_seconds() <= 60.0
        )
        cancel_count_1m = len(self._cancel_events)
        fill_to_cancel_ratio = (
            maker_fill_count_1m / cancel_count_1m
            if cancel_count_1m > 0
            else float(maker_fill_count_1m)
        )

        ages = self._open_order_ages(now)
        time_in_book_p50 = self._percentile(ages, 0.5)
        time_in_book_p90 = self._percentile(ages, 0.9)
        buy_age = self._side_open_order_age(now, "buy")
        sell_age = self._side_open_order_age(now, "sell")

        self._summary = MetricsSummary(
            timestamp=tick.timestamp,
            mid_price=tick.market.mid,
            spread_bps=tick.decision.spread_bps,
            distance_bid_bps=tick.distance_bid_bps,
            distance_ask_bps=tick.distance_ask_bps,
            sigma=tick.sigma,
            sigma_zscore=tick.sigma_zscore,
            inventory_base=tick.position.base_position,
            inventory_notional=tick.position.notional,
            equity=tick.equity,
            pnl=tick.pnl,
            drawdown_pct=drawdown_pct,
            quote_size_base=tick.decision.quote_size_base,
            quote_size_notional=tick.decision.quote_size_notional,
            maker_fill_count_1m=maker_fill_count_1m,
            cancel_count_1m=cancel_count_1m,
            fill_to_cancel_ratio=fill_to_cancel_ratio,
            time_in_book_p50_sec=time_in_book_p50,
            time_in_book_p90_sec=time_in_book_p90,
            open_order_age_buy_sec=buy_age,
            open_order_age_sell_sec=sell_age,
            requote_reason=requote_reason,
            mode=mode,
            consecutive_failures=consecutive_failures,
        )

        self._series["sigma"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.sigma))
        self._series["spread_bps"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.decision.spread_bps))
        self._series["distance_bid_bps"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.distance_bid_bps))
        self._series["distance_ask_bps"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.distance_ask_bps))
        self._series["inventory_notional"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.position.notional))
        self._series["mid_price"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.market.mid))
        self._series["quote_size_notional"].append(TimeSeriesPoint(t=tick.timestamp, value=tick.decision.quote_size_notional))

    def record_cancel(self, at: datetime | None = None) -> None:
        self._cancel_events.append(at or datetime.now(timezone.utc))

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

    @staticmethod
    def _trim_window(rows: deque[datetime], now: datetime, window_sec: float) -> None:
        while rows and (now - rows[0]).total_seconds() > window_sec:
            rows.popleft()

    def _open_order_ages(self, now: datetime) -> list[float]:
        ages: list[float] = []
        for order in self._open_orders:
            delta = (now - order.created_at).total_seconds()
            if delta >= 0:
                ages.append(delta)
        return sorted(ages)

    def _side_open_order_age(self, now: datetime, side: str) -> float:
        side_ages = [
            (now - order.created_at).total_seconds()
            for order in self._open_orders
            if order.side == side and (now - order.created_at).total_seconds() >= 0
        ]
        return max(side_ages) if side_ages else 0.0

    @staticmethod
    def _percentile(values: list[float], ratio: float) -> float:
        if not values:
            return 0.0
        idx = ceil((len(values) - 1) * max(0.0, min(1.0, ratio)))
        return values[idx]
