from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import MarketSnapshot, OrderSnapshot, PositionSnapshot, TradeSnapshot


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
