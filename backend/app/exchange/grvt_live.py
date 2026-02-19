from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from functools import cached_property
from typing import Any

from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv

from app.core.settings import Settings
from app.exchange.base import ExchangeAdapter
from app.models import MarketSnapshot, OrderSnapshot, PositionSnapshot, TradeSnapshot


class GrvtLiveAdapter(ExchangeAdapter):
    """基于 grvt-pysdk 的真实交易适配器。"""

    FIXED_SCALE = 1_000_000_000

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger("grvt.live")

    @cached_property
    def _client(self) -> GrvtCcxt:
        env_raw = str(self._settings.grvt_env).lower()
        env_map = {
            "prod": GrvtEnv.PROD,
            "production": GrvtEnv.PROD,
            "testnet": GrvtEnv.TESTNET,
            "staging": GrvtEnv.STAGING,
            "dev": GrvtEnv.DEV,
        }
        env = env_map.get(env_raw, GrvtEnv.TESTNET)
        params = {
            "api_key": self._settings.grvt_api_key,
            "private_key": self._settings.grvt_api_secret,
            "trading_account_id": self._settings.grvt_trading_account_id,
        }
        return GrvtCcxt(env=env, parameters=params, order_book_ccxt_format=True)

    async def ping(self) -> bool:
        try:
            symbol = "BTC_USDT-PERP"
            await asyncio.to_thread(self._client.fetch_ticker, symbol)
            return True
        except Exception:
            return False

    async def fetch_market_snapshot(self, symbol: str) -> MarketSnapshot:
        ticker_task = asyncio.to_thread(self._client.fetch_ticker, symbol)
        ob_task = asyncio.to_thread(self._client.fetch_order_book, symbol, 10)
        ticker, order_book = await asyncio.gather(ticker_task, ob_task)

        bids = order_book.get("bids", []) if isinstance(order_book, dict) else []
        asks = order_book.get("asks", []) if isinstance(order_book, dict) else []

        best_bid = self._safe_px_size(bids[0], 0) if bids else self._decode_fixed(ticker.get("best_bid_price"))
        best_ask = self._safe_px_size(asks[0], 0) if asks else self._decode_fixed(ticker.get("best_ask_price"))

        if best_bid <= 0:
            best_bid = self._decode_fixed(ticker.get("mid_price"))
        if best_ask <= 0:
            best_ask = self._decode_fixed(ticker.get("mid_price"))

        mid = (best_bid + best_ask) / 2 if best_bid and best_ask else self._decode_fixed(ticker.get("mid_price"))

        depth_bid = sum(self._safe_px_size(level, 1) for level in bids[:5])
        depth_ask = sum(self._safe_px_size(level, 1) for level in asks[:5])
        depth_score = max(0.2, min(3.5, (depth_bid + depth_ask) / 20.0))

        buy_vol = self._decode_fixed(ticker.get("buy_volume_u", 0.0))
        sell_vol = self._decode_fixed(ticker.get("sell_volume_u", 0.0))
        trade_intensity = max(0.2, min(3.5, (buy_vol + sell_vol) / max(1.0, mid) / 20.0))

        return MarketSnapshot(
            symbol=symbol,
            bid=best_bid,
            ask=best_ask,
            mid=mid,
            depth_score=depth_score,
            trade_intensity=trade_intensity,
            timestamp=datetime.now(timezone.utc),
        )

    async def fetch_equity(self) -> float:
        balance = await asyncio.to_thread(self._client.fetch_balance, "aggregated")
        usdt = balance.get("USDT", {}) if isinstance(balance, dict) else {}
        total = usdt.get("total") if isinstance(usdt, dict) else None
        if total is None:
            total = balance.get("total", {}).get("USDT", 0.0) if isinstance(balance, dict) else 0.0
        return float(total or 0.0)

    async def fetch_position(self, symbol: str) -> PositionSnapshot:
        positions = await asyncio.to_thread(self._client.fetch_positions, [symbol])
        base_position = 0.0
        notional = 0.0
        for item in positions or []:
            instrument = str(item.get("instrument", ""))
            if instrument != symbol:
                continue
            size = self._decode_fixed(item.get("size", 0.0))
            is_long = bool(item.get("is_long", True))
            signed_size = size if is_long else -size
            base_position += signed_size
            mark_price = self._decode_fixed(item.get("mark_price", 0.0))
            notional += signed_size * mark_price
        return PositionSnapshot(symbol=symbol, base_position=base_position, notional=notional)

    async def fetch_open_orders(self, symbol: str) -> list[OrderSnapshot]:
        orders = await asyncio.to_thread(self._client.fetch_open_orders, symbol)
        results: list[OrderSnapshot] = []
        for order in orders or []:
            side = self._parse_side(order)
            leg = self._first_leg(order)
            price = self._decode_fixed(leg.get("limit_price", 0.0))
            size = self._decode_fixed(leg.get("size", 0.0))
            order_id = str(order.get("order_id") or order.get("id") or order.get("metadata", {}).get("client_order_id", ""))
            created_at = self._parse_dt(order.get("create_time_ns") or order.get("created_at"))
            status = str(order.get("state", "open")).lower()
            if not order_id:
                continue
            results.append(
                OrderSnapshot(
                    order_id=order_id,
                    side=side,
                    price=price,
                    size=size,
                    status=status,
                    created_at=created_at,
                )
            )
        return results

    async def fetch_recent_trades(self, symbol: str, limit: int = 50) -> list[TradeSnapshot]:
        data = await asyncio.to_thread(self._client.fetch_my_trades, symbol, None, limit, {})
        rows = data.get("result", []) if isinstance(data, dict) else []
        trades: list[TradeSnapshot] = []
        for row in rows[-limit:]:
            side = "buy" if bool(row.get("is_taker_buyer", True)) else "sell"
            trades.append(
                TradeSnapshot(
                    trade_id=str(row.get("trade_id") or row.get("id") or ""),
                    side=side,
                    price=self._decode_fixed(row.get("price", 0.0)),
                    size=self._decode_fixed(row.get("size", 0.0)),
                    fee=self._decode_fixed(row.get("fee", 0.0)),
                    created_at=self._parse_dt(row.get("event_time") or row.get("created_at")),
                )
            )
        return trades

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        price: float,
        size: float,
        post_only: bool,
        client_order_id: str,
    ) -> OrderSnapshot:
        params = {
            "post_only": bool(post_only),
            "client_order_id": client_order_id,
        }
        result = await asyncio.to_thread(
            self._client.create_order,
            symbol,
            "limit",
            "buy" if side == "buy" else "sell",
            size,
            price,
            params,
        )
        oid = str(result.get("order_id") or result.get("id") or result.get("metadata", {}).get("client_order_id") or client_order_id)
        return OrderSnapshot(
            order_id=oid,
            side="buy" if side == "buy" else "sell",
            price=float(price),
            size=float(size),
            status="open",
            created_at=datetime.now(timezone.utc),
        )

    async def cancel_order(self, symbol: str, order_id: str) -> None:
        await asyncio.to_thread(self._client.cancel_order, order_id, symbol, {})

    async def cancel_all_orders(self, symbol: str) -> None:
        await asyncio.to_thread(self._client.cancel_all_orders, {"symbol": symbol})

    def _decode_fixed(self, value: Any) -> float:
        if value is None:
            return 0.0
        try:
            num = float(value)
        except Exception:
            return 0.0
        if abs(num) >= self.FIXED_SCALE:
            return num / self.FIXED_SCALE
        return num

    def _safe_px_size(self, level: Any, idx: int) -> float:
        if isinstance(level, (list, tuple)) and len(level) > idx:
            return float(level[idx])
        if isinstance(level, dict):
            key = "price" if idx == 0 else "size"
            return self._decode_fixed(level.get(key, 0.0))
        return 0.0

    def _first_leg(self, order: dict) -> dict:
        legs = order.get("legs") if isinstance(order, dict) else None
        if isinstance(legs, list) and legs:
            return legs[0]
        return {}

    def _parse_side(self, order: dict) -> str:
        leg = self._first_leg(order)
        is_buy = leg.get("is_buying_asset")
        if is_buy is None:
            side = str(order.get("side", "buy")).lower()
            return "buy" if side == "buy" else "sell"
        return "buy" if bool(is_buy) else "sell"

    def _parse_dt(self, raw: Any) -> datetime:
        if raw is None:
            return datetime.now(timezone.utc)
        try:
            txt = str(raw)
            if len(txt) >= 19 and txt.isdigit():
                ns = int(txt)
                return datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc)
        except Exception:
            pass
        return datetime.now(timezone.utc)
