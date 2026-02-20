from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from functools import cached_property
from typing import Any

from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv

from app.core.settings import Settings
from app.exchange.base import ExchangeAdapter
from app.models import AccountFundsSnapshot, MarketSnapshot, OrderSnapshot, PositionSnapshot, TradeSnapshot


@dataclass(frozen=True, slots=True)
class InstrumentConstraints:
    min_size: float
    size_step: float
    tick_size: float
    base_decimals: int


class GrvtLiveAdapter(ExchangeAdapter):
    """基于 grvt-pysdk 的实盘交易适配器。"""

    FIXED_SCALE = 1_000_000_000

    def __init__(
        self,
        settings: Settings,
        *,
        grvt_env: str | None = None,
        grvt_api_key: str | None = None,
        grvt_api_secret: str | None = None,
        grvt_trading_account_id: str | None = None,
    ) -> None:
        self._settings = settings
        self._logger = logging.getLogger("grvt.live")
        self._grvt_env = settings.grvt_env if grvt_env is None else grvt_env
        self._grvt_api_key = settings.grvt_api_key if grvt_api_key is None else grvt_api_key
        self._grvt_api_secret = settings.grvt_api_secret if grvt_api_secret is None else grvt_api_secret
        self._grvt_trading_account_id = (
            settings.grvt_trading_account_id if grvt_trading_account_id is None else grvt_trading_account_id
        )
        self._instrument_constraints_cache: dict[str, InstrumentConstraints] = {}

    @cached_property
    def _client(self) -> GrvtCcxt:
        env_raw = str(self._grvt_env).lower()
        env_map = {
            "prod": GrvtEnv.PROD,
            "production": GrvtEnv.PROD,
            "testnet": GrvtEnv.TESTNET,
            "staging": GrvtEnv.STAGING,
            "dev": GrvtEnv.DEV,
        }
        env = env_map.get(env_raw, GrvtEnv.TESTNET)
        params = {
            "api_key": self._grvt_api_key,
            "private_key": self._grvt_api_secret,
            "trading_account_id": self._grvt_trading_account_id,
        }
        return GrvtCcxt(env=env, parameters=params, order_book_ccxt_format=True)

    async def ping(self) -> bool:
        try:
            symbol = "BTC_USDT_Perp"
            await asyncio.to_thread(self._client.fetch_ticker, symbol)
            return True
        except Exception:
            return False

    async def fetch_market_snapshot(self, symbol: str) -> MarketSnapshot:
        ex_symbol = self._normalize_symbol(symbol)
        ticker_result, ob_result = await asyncio.gather(
            asyncio.to_thread(self._client.fetch_ticker, ex_symbol),
            asyncio.to_thread(self._client.fetch_order_book, ex_symbol, 10),
            return_exceptions=True,
        )

        if isinstance(ticker_result, Exception):
            raise ticker_result

        ticker = ticker_result
        order_book: dict[str, Any] = {}
        if isinstance(ob_result, Exception):
            self._logger.warning("璇诲彇 order_book 澶辫触锛岄檷绾т负 ticker-only: %s", ob_result)
        elif isinstance(ob_result, dict):
            order_book = ob_result

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
            symbol=ex_symbol,
            bid=best_bid,
            ask=best_ask,
            mid=mid,
            depth_score=depth_score,
            trade_intensity=trade_intensity,
            timestamp=datetime.now(timezone.utc),
        )

    async def fetch_account_funds(self) -> AccountFundsSnapshot:
        balance = await asyncio.to_thread(self._client.fetch_balance, "aggregated")
        if not isinstance(balance, dict):
            return AccountFundsSnapshot(equity_usdt=0.0, free_usdt=0.0, used_usdt=0.0, source="invalid-balance")

        source_parts: list[str] = []
        equity = 0.0
        free = 0.0
        used = 0.0

        usdt = balance.get("USDT", {})
        if isinstance(usdt, dict):
            if usdt.get("free") is not None:
                free = self._decode_fixed(usdt.get("free", 0.0))
                source_parts.append("USDT.free")
            if usdt.get("used") is not None:
                used = self._decode_fixed(usdt.get("used", 0.0))
                source_parts.append("USDT.used")
            if usdt.get("total") is not None:
                equity = self._decode_fixed(usdt.get("total", 0.0))
                source_parts.append("USDT.total")

        free_from_map = self._extract_usdt_from_map(balance.get("free"))
        if free_from_map is not None:
            free = free_from_map
            source_parts.append("free.USDT")

        used_from_map = self._extract_usdt_from_map(balance.get("used"))
        if used_from_map is not None:
            used = used_from_map
            source_parts.append("used.USDT")

        total_from_map = self._extract_usdt_from_map(balance.get("total"))
        if total_from_map is not None:
            equity = total_from_map
            source_parts.append("total.USDT")

        if equity <= 0:
            for key in ("equity", "account_value", "nav"):
                if balance.get(key) is None:
                    continue
                equity = self._decode_fixed(balance.get(key))
                source_parts.append(key)
                break

        if equity <= 0 and (free > 0 or used > 0):
            equity = max(0.0, free + used)
            source_parts.append("free+used")

        if free <= 0 and equity > 0:
            free = max(0.0, equity - max(0.0, used))
            source_parts.append("equity-used")

        if not source_parts:
            self._logger.warning("fetch_balance 未命中标准权益字段，可用keys=%s", ",".join(balance.keys()))
        source = ",".join(dict.fromkeys(source_parts)) if source_parts else "unknown"
        return AccountFundsSnapshot(
            equity_usdt=float(max(0.0, equity)),
            free_usdt=float(max(0.0, free)),
            used_usdt=float(max(0.0, used)),
            source=source,
        )

    async def fetch_equity(self) -> float:
        funds = await self.fetch_account_funds()
        return float(funds.equity_usdt)

    async def fetch_position(self, symbol: str) -> PositionSnapshot:
        ex_symbol = self._normalize_symbol(symbol)
        positions = await asyncio.to_thread(self._client.fetch_positions, [ex_symbol])
        base_position = 0.0
        notional = 0.0
        for item in positions or []:
            instrument = str(item.get("instrument", ""))
            if not self._symbol_equal(instrument, ex_symbol):
                continue
            size = self._decode_fixed(item.get("size", 0.0))
            is_long = bool(item.get("is_long", True))
            signed_size = size if is_long else -size
            base_position += signed_size
            mark_price = self._decode_fixed(item.get("mark_price", 0.0))
            notional += signed_size * mark_price
        return PositionSnapshot(symbol=ex_symbol, base_position=base_position, notional=notional)

    async def fetch_open_orders(self, symbol: str) -> list[OrderSnapshot]:
        ex_symbol = self._normalize_symbol(symbol)
        orders = await asyncio.to_thread(self._client.fetch_open_orders, ex_symbol)
        results: list[OrderSnapshot] = []
        for order in orders or []:
            if not isinstance(order, dict):
                continue
            side = self._parse_side(order)
            leg = self._first_leg(order)
            price = self._decode_fixed(leg.get("limit_price", 0.0))
            size = self._decode_fixed(leg.get("size", 0.0))
            order_id = self._extract_order_id(order)
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
        ex_symbol = self._normalize_symbol(symbol)
        data = await asyncio.to_thread(self._client.fetch_my_trades, ex_symbol, None, limit, {})
        rows = data.get("result", []) if isinstance(data, dict) else []
        trades: list[TradeSnapshot] = []
        for row in rows[-limit:]:
            if not isinstance(row, dict):
                continue
            side = "buy" if bool(row.get("is_taker_buyer", True)) else "sell"
            trades.append(
                TradeSnapshot(
                    trade_id=str(row.get("trade_id") or row.get("id") or ""),
                    side=side,
                    price=self._decode_fixed(row.get("price", 0.0)),
                    size=self._decode_fixed(row.get("size", 0.0)),
                    fee=self._decode_fixed(row.get("fee", 0.0)),
                    created_at=self._parse_dt(row.get("event_time") or row.get("created_at")),
                    symbol=ex_symbol,
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
        ex_symbol = self._normalize_symbol(symbol)
        constraints = await self._get_instrument_constraints(ex_symbol)
        quantized_size = self._quantize_order_size(size, constraints)
        if abs(quantized_size - float(size)) > 1e-12:
            self._logger.info(
                "涓嬪崟閲忓凡鎸変氦鏄撳姝ラ暱瀵归綈 symbol=%s raw_size=%.12f quantized_size=%.12f size_step=%.12f min_size=%.12f",
                ex_symbol,
                float(size),
                quantized_size,
                constraints.size_step,
                constraints.min_size,
            )
        params = {
            "post_only": bool(post_only),
            "client_order_id": client_order_id,
        }
        result = await asyncio.to_thread(
            self._client.create_order,
            ex_symbol,
            "limit",
            "buy" if side == "buy" else "sell",
            quantized_size,
            price,
            params,
        )
        oid = self._extract_order_id(result if isinstance(result, dict) else {}) or str(client_order_id)
        return OrderSnapshot(
            order_id=oid,
            side="buy" if side == "buy" else "sell",
            price=float(price),
            size=quantized_size,
            status="open",
            created_at=datetime.now(timezone.utc),
        )

    async def cancel_order(self, symbol: str, order_id: str) -> None:
        ex_symbol = self._normalize_symbol(symbol)
        await asyncio.to_thread(self._client.cancel_order, order_id, ex_symbol, {})

    async def cancel_all_orders(self, symbol: str) -> None:
        ex_symbol = self._normalize_symbol(symbol)
        await asyncio.to_thread(self._client.cancel_all_orders, {"symbol": ex_symbol})

    async def close_position_taker(
        self,
        symbol: str,
        side: str,
        size: float,
        reduce_only: bool = True,
    ) -> OrderSnapshot:
        ex_symbol = self._normalize_symbol(symbol)
        amount = max(0.0, float(size))
        params = {
            "post_only": False,
            "reduce_only": bool(reduce_only),
            "time_in_force": "IOC",
        }
        result = await asyncio.to_thread(
            self._client.create_order,
            ex_symbol,
            "market",
            "buy" if side == "buy" else "sell",
            amount,
            None,
            params,
        )
        payload = result if isinstance(result, dict) else {}
        oid = self._extract_order_id(payload) or f"close-{datetime.now(timezone.utc).timestamp()}"
        return OrderSnapshot(
            order_id=oid,
            side="buy" if side == "buy" else "sell",
            price=0.0,
            size=amount,
            status=str(payload.get("status", "closed")).lower(),
            created_at=datetime.now(timezone.utc),
        )

    async def flatten_position_taker(self, symbol: str) -> None:
        pos = await self.fetch_position(symbol)
        size = abs(float(pos.base_position))
        if size <= 1e-12:
            return
        side = "sell" if pos.base_position > 0 else "buy"
        await self.close_position_taker(symbol=symbol, side=side, size=size, reduce_only=True)

    async def _get_instrument_constraints(self, symbol: str) -> InstrumentConstraints:
        ex_symbol = self._normalize_symbol(symbol)
        cache_key = ex_symbol.lower()
        cached = self._instrument_constraints_cache.get(cache_key)
        if cached is not None:
            return cached

        constraints = await asyncio.to_thread(self._load_instrument_constraints, ex_symbol)
        self._instrument_constraints_cache[cache_key] = constraints
        return constraints

    def _load_instrument_constraints(self, symbol: str) -> InstrumentConstraints:
        instrument = self._fetch_instrument(symbol)
        if instrument is None:
            self._logger.warning("鏈鍙栧埌浜ゆ槗瀵瑰厓鏁版嵁锛屼娇鐢ㄩ粯璁や笅鍗曟闀?symbol=%s", symbol)
            return InstrumentConstraints(
                min_size=0.0,
                size_step=1e-6,
                tick_size=0.0,
                base_decimals=6,
            )
        return self._build_instrument_constraints(instrument)

    def _fetch_instrument(self, symbol: str) -> dict[str, Any] | None:
        try:
            market = self._client.fetch_market(symbol)
            instrument = self._extract_instrument(market, symbol)
            if instrument is not None:
                return instrument
        except Exception as exc:
            self._logger.warning("fetch_market 璇诲彇浜ゆ槗瀵瑰厓鏁版嵁澶辫触 symbol=%s: %s", symbol, exc)

        params: dict[str, Any] = {"kind": "PERPETUAL"}
        parts = symbol.split("_")
        if len(parts) >= 3:
            params["base"] = parts[0]
            params["quote"] = parts[1]

        try:
            markets = self._client.fetch_markets(params)
        except TypeError:
            try:
                markets = self._client.fetch_markets({})
            except Exception as exc:
                self._logger.warning("fetch_markets 璇诲彇浜ゆ槗瀵瑰厓鏁版嵁澶辫触 symbol=%s: %s", symbol, exc)
                return None
        except Exception as exc:
            self._logger.warning("fetch_markets 璇诲彇浜ゆ槗瀵瑰厓鏁版嵁澶辫触 symbol=%s: %s", symbol, exc)
            return None
        return self._extract_instrument(markets, symbol)

    @classmethod
    def _extract_instrument(cls, payload: Any, symbol: str) -> dict[str, Any] | None:
        rows: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            result = payload.get("result")
            if isinstance(result, dict):
                rows.append(result)
            elif isinstance(result, list):
                rows.extend(item for item in result if isinstance(item, dict))
            if "instrument" in payload:
                rows.append(payload)
        elif isinstance(payload, list):
            rows.extend(item for item in payload if isinstance(item, dict))

        if not rows:
            return None

        for row in rows:
            instrument = str(row.get("instrument", "")).strip()
            if instrument and cls._symbol_equal(instrument, symbol):
                return row
        return rows[0] if len(rows) == 1 else None

    def _build_instrument_constraints(self, instrument: dict[str, Any]) -> InstrumentConstraints:
        min_size = max(0.0, self._decode_fixed(instrument.get("min_size", 0.0)))
        tick_size = max(0.0, self._decode_fixed(instrument.get("tick_size", 0.0)))
        base_decimals = max(0, self._safe_int(instrument.get("base_decimals"), 0))

        size_step = 0.0
        explicit_step_found = False
        for key in (
            "size_step",
            "size_increment",
            "step_size",
            "quantity_step",
            "lot_step",
            "order_size_step",
            "contract_size_step",
        ):
            candidate = self._decode_fixed(instrument.get(key, 0.0))
            if candidate > 0:
                size_step = candidate
                explicit_step_found = True
                break

        if size_step <= 0 and base_decimals > 0:
            size_step = 10 ** (-base_decimals)
        if size_step <= 0 and min_size > 0:
            size_step = self._infer_decimal_step(min_size)
        if size_step <= 0:
            size_step = 1e-6
        if min_size > 0 and not explicit_step_found:
            size_step = max(size_step, self._infer_decimal_step(min_size))

        return InstrumentConstraints(
            min_size=min_size,
            size_step=size_step,
            tick_size=tick_size,
            base_decimals=base_decimals,
        )

    @staticmethod
    def _quantize_order_size(raw_size: float, constraints: InstrumentConstraints) -> float:
        raw_dec = Decimal(str(max(0.0, float(raw_size))))
        step_dec = Decimal(str(max(constraints.size_step, 1e-12)))
        min_dec = Decimal(str(max(constraints.min_size, 0.0)))

        quantized = (raw_dec / step_dec).to_integral_value(rounding=ROUND_DOWN) * step_dec
        if min_dec > 0 and quantized < min_dec:
            quantized = (min_dec / step_dec).to_integral_value(rounding=ROUND_UP) * step_dec

        if quantized <= 0:
            raise ValueError(
                "涓嬪崟閲忛噺鍖栧悗鏃犳晥"
                f" raw_size={raw_size} size_step={constraints.size_step} min_size={constraints.min_size}"
            )
        return float(quantized)

    @staticmethod
    def _infer_decimal_step(value: float) -> float:
        dec = Decimal(str(abs(float(value))))
        exponent = dec.as_tuple().exponent
        if exponent >= 0:
            return 1.0
        return float(Decimal(1).scaleb(exponent))

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _extract_usdt_from_map(self, payload: Any) -> float | None:
        if not isinstance(payload, dict):
            return None
        if payload.get("USDT") is None:
            return None
        return self._decode_fixed(payload.get("USDT"))

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

    @staticmethod
    def _extract_order_id(payload: dict[str, Any]) -> str:
        candidates: list[Any] = [
            payload.get("order_id"),
            payload.get("id"),
            payload.get("metadata", {}).get("order_id") if isinstance(payload.get("metadata"), dict) else None,
            payload.get("metadata", {}).get("client_order_id") if isinstance(payload.get("metadata"), dict) else None,
        ]
        for value in candidates:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

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
            txt = str(raw).strip()
            if txt.isdigit():
                if len(txt) >= 19:
                    ns = int(txt)
                    return datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc)
                if len(txt) >= 13:
                    ms = int(txt)
                    return datetime.fromtimestamp(ms / 1_000, tz=timezone.utc)
                sec = int(txt)
                return datetime.fromtimestamp(sec, tz=timezone.utc)
        except Exception:
            pass
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = str(symbol or "").strip().replace("-", "_")
        if normalized.upper().endswith("_PERP"):
            normalized = f"{normalized[:-5]}_Perp"
        return normalized

    @classmethod
    def _symbol_equal(cls, left: str, right: str) -> bool:
        return cls._normalize_symbol(left).lower() == cls._normalize_symbol(right).lower()

