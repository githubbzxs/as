from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import AccountFundsSnapshot, MarketSnapshot, OrderSnapshot, PositionSnapshot, TradeSnapshot


class PositionDustError(RuntimeError):
    """仓位小于交易所可成交最小量，无法继续 taker 平仓。"""

    def __init__(self, symbol: str, remaining_size: float, min_close_size: float) -> None:
        self.symbol = symbol
        self.remaining_size = float(remaining_size)
        self.min_close_size = float(min_close_size)
        super().__init__(
            f"position_dust_uncloseable symbol={symbol} remaining_size={remaining_size} min_close_size={min_close_size}"
        )


class ExchangeAdapter(ABC):
    """交易所抽象层。"""

    @abstractmethod
    async def ping(self) -> bool:
        """探测交易所连通性。"""

    @abstractmethod
    async def fetch_market_snapshot(self, symbol: str) -> MarketSnapshot:
        """读取盘口快照。"""

    @abstractmethod
    async def fetch_equity(self) -> float:
        """读取账户权益。"""

    @abstractmethod
    async def fetch_account_funds(self) -> AccountFundsSnapshot:
        """读取账户资金快照（权益/可用/占用）。"""

    @abstractmethod
    async def fetch_position(self, symbol: str) -> PositionSnapshot:
        """读取持仓。"""

    @abstractmethod
    async def fetch_open_orders(self, symbol: str) -> list[OrderSnapshot]:
        """读取当前挂单。"""

    @abstractmethod
    async def fetch_recent_trades(self, symbol: str, limit: int = 50) -> list[TradeSnapshot]:
        """读取最近成交。"""

    @abstractmethod
    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        price: float,
        size: float,
        post_only: bool,
        client_order_id: str,
    ) -> OrderSnapshot:
        """下限价单。"""

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> None:
        """撤单。"""

    @abstractmethod
    async def cancel_all_orders(self, symbol: str) -> None:
        """全撤。"""

    @abstractmethod
    async def close_position_taker(
        self,
        symbol: str,
        side: str,
        size: float,
        reduce_only: bool = True,
    ) -> OrderSnapshot:
        """按 taker 方式提交平仓单。"""

    @abstractmethod
    async def flatten_position_taker(self, symbol: str) -> None:
        """读取净仓并执行 taker 全平。"""
