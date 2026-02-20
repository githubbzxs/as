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
class AccountFundsSnapshot:
    equity_usdt: float
    free_usdt: float
    used_usdt: float
    source: str = "unknown"


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
    symbol: str | None = None


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
    pnl_total: float
    pnl_daily: float
    sigma: float
    sigma_zscore: float
    free_usdt: float = 0.0
    effective_capacity_notional: float = 0.0
    inventory_usage_ratio: float = 0.0
    effective_liquidity_k: float = 0.0
    distance_bid_bps: float = 0.0
    distance_ask_bps: float = 0.0



def utcnow() -> datetime:
    return datetime.now(timezone.utc)
