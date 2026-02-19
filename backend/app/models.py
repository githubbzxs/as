from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


@dataclass(slots=True)
class MarketSnapshot:
    symbol: str
    bid: float
    ask: float
    mid: float
    depth_score: float
    trade_intensity: float
    timestamp: datetime


@dataclass(slots=True)
class PositionSnapshot:
    symbol: str
    base_position: float
    notional: float


@dataclass(slots=True)
class OrderSnapshot:
    order_id: str
    side: Literal["buy", "sell"]
    price: float
    size: float
    status: str
    created_at: datetime


@dataclass(slots=True)
class TradeSnapshot:
    trade_id: str
    side: Literal["buy", "sell"]
    price: float
    size: float
    fee: float
    created_at: datetime


@dataclass(slots=True)
class QuoteDecision:
    bid_price: float
    ask_price: float
    quote_size_base: float
    quote_size_notional: float
    spread_bps: float
    gamma: float
    reservation_price: float


@dataclass(slots=True)
class EngineTick:
    timestamp: datetime
    market: MarketSnapshot
    decision: QuoteDecision
    position: PositionSnapshot
    equity: float
    pnl: float
    sigma: float
    sigma_zscore: float



def utcnow() -> datetime:
    return datetime.now(timezone.utc)
