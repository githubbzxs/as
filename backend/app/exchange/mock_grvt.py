from __future__ import annotations

import asyncio
import random
import uuid
from collections import deque
from datetime import datetime, timezone

from app.exchange.base import ExchangeAdapter
from app.models import MarketSnapshot, OrderSnapshot, PositionSnapshot, TradeSnapshot


class MockGrvtAdapter(ExchangeAdapter):
    """用于本地联调的模拟交易所实现。"""

    def __init__(self) -> None:
        self._mid_price = 620.0
        self._spread = 0.45
        self._equity = 10000.0
        self._base_position = 0.0
        self._open_orders: dict[str, OrderSnapshot] = {}
        self._trades: deque[TradeSnapshot] = deque(maxlen=300)
        self._rnd = random.Random(7)
        self._lock = asyncio.Lock()

    async def ping(self) -> bool:
        return True

    async def fetch_market_snapshot(self, symbol: str) -> MarketSnapshot:
        async with self._lock:
            move = self._rnd.gauss(0, 0.6)
            self._mid_price = max(5.0, self._mid_price + move)
            micro_spread = max(0.1, self._spread + self._rnd.gauss(0, 0.08))
            bid = self._mid_price - micro_spread / 2
            ask = self._mid_price + micro_spread / 2

            await self._simulate_fills(symbol)

            depth_score = max(0.2, min(2.5, 1.2 + self._rnd.gauss(0, 0.3)))
            trade_intensity = max(0.2, min(3.5, 1.0 + abs(self._rnd.gauss(0, 0.8))))
            return MarketSnapshot(
                symbol=symbol,
                bid=round(bid, 6),
                ask=round(ask, 6),
                mid=round((bid + ask) / 2, 6),
                depth_score=depth_score,
                trade_intensity=trade_intensity,
                timestamp=datetime.now(timezone.utc),
            )

    async def fetch_equity(self) -> float:
        async with self._lock:
            mtm = self._base_position * self._mid_price
            return self._equity + mtm

    async def fetch_position(self, symbol: str) -> PositionSnapshot:
        async with self._lock:
            return PositionSnapshot(
                symbol=symbol,
                base_position=self._base_position,
                notional=self._base_position * self._mid_price,
            )

    async def fetch_open_orders(self, symbol: str) -> list[OrderSnapshot]:
        async with self._lock:
            return sorted(self._open_orders.values(), key=lambda o: o.created_at)

    async def fetch_recent_trades(self, symbol: str, limit: int = 50) -> list[TradeSnapshot]:
        async with self._lock:
            data = list(self._trades)
            return data[-limit:]

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        price: float,
        size: float,
        post_only: bool,
        client_order_id: str,
    ) -> OrderSnapshot:
        async with self._lock:
            order = OrderSnapshot(
                order_id=client_order_id,
                side="buy" if side == "buy" else "sell",
                price=float(price),
                size=float(size),
                status="open",
                created_at=datetime.now(timezone.utc),
            )
            self._open_orders[order.order_id] = order
            return order

    async def cancel_order(self, symbol: str, order_id: str) -> None:
        async with self._lock:
            self._open_orders.pop(order_id, None)

    async def cancel_all_orders(self, symbol: str) -> None:
        async with self._lock:
            self._open_orders.clear()

    async def _simulate_fills(self, symbol: str) -> None:
        filled_ids: list[str] = []
        for order_id, order in self._open_orders.items():
            if order.side == "buy":
                trigger = order.price >= self._mid_price - self._spread * 0.6
            else:
                trigger = order.price <= self._mid_price + self._spread * 0.6
            probability = 0.12 if trigger else 0.02
            if self._rnd.random() < probability:
                filled_ids.append(order_id)

        for oid in filled_ids:
            order = self._open_orders.pop(oid, None)
            if not order:
                continue
            signed_size = order.size if order.side == "buy" else -order.size
            self._base_position += signed_size
            fee = abs(order.price * order.size) * 0.0002
            self._equity -= fee
            trade = TradeSnapshot(
                trade_id=str(uuid.uuid4()),
                side=order.side,
                price=order.price,
                size=order.size,
                fee=fee,
                created_at=datetime.now(timezone.utc),
            )
            self._trades.append(trade)
