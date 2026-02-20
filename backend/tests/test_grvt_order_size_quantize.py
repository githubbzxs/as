from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from app.core.settings import Settings
from app.exchange.base import PositionDustError
from app.exchange.grvt_live import GrvtLiveAdapter, InstrumentConstraintsError


class _ClientWithInstrument:
    def __init__(
        self,
        *,
        min_size: float,
        base_decimals: int,
        size_step: float | None = None,
        market_overrides: dict | None = None,
    ) -> None:
        self._min_size = min_size
        self._base_decimals = base_decimals
        self._size_step = size_step
        self._market_overrides = market_overrides or {}
        self.last_amount: float | None = None
        self.last_order_type: str | None = None
        self.last_params: dict | None = None

    def fetch_market(self, symbol: str) -> dict:
        payload = {
            "instrument": symbol,
            "min_size": self._min_size,
            "base_decimals": self._base_decimals,
            "tick_size": 0.01,
        }
        if self._size_step is not None:
            payload["size_step"] = self._size_step
        payload.update(self._market_overrides)
        return payload

    def fetch_markets(self, params: dict) -> list[dict]:
        return []

    def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float,
        params: dict,
    ) -> dict:
        self.last_amount = float(amount)
        self.last_order_type = order_type
        self.last_params = params
        return {"order_id": "oid-1", "symbol": symbol, "type": order_type, "side": side, "price": price, "params": params}


class _ClientWithoutInstrument:
    def __init__(self) -> None:
        self.last_amount: float | None = None

    def fetch_market(self, symbol: str) -> dict:
        return {"instrument": "OTHER_USDT_Perp", "min_size": 0.0, "base_decimals": 0}

    def fetch_markets(self, params: dict) -> list[dict]:
        return []

    def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float,
        params: dict,
    ) -> dict:
        self.last_amount = float(amount)
        return {"order_id": "oid-unexpected"}


@dataclass(frozen=True)
class _QuantCase:
    symbol: str
    min_size: float
    size_step: float
    raw_size: float
    expected: float


@pytest.mark.parametrize(
    "case",
    [
        _QuantCase(symbol="BNB_USDT_Perp", min_size=0.01, size_step=0.01, raw_size=0.075440228, expected=0.07),
        _QuantCase(symbol="XRP_USDT_Perp", min_size=1.0, size_step=1.0, raw_size=137.89, expected=137.0),
        _QuantCase(symbol="SUI_USDT_Perp", min_size=0.5, size_step=0.5, raw_size=18.74, expected=18.5),
        _QuantCase(symbol="HYPE_USDT_Perp", min_size=0.25, size_step=0.25, raw_size=7.78, expected=7.75),
    ],
)
def test_place_limit_order_quantizes_size_for_supported_symbols(case: _QuantCase):
    adapter = GrvtLiveAdapter(Settings())
    fake_client = _ClientWithInstrument(min_size=case.min_size, base_decimals=9, size_step=case.size_step)
    adapter.__dict__["_client"] = fake_client

    order = asyncio.run(
        adapter.place_limit_order(
            symbol=case.symbol,
            side="buy",
            price=607.49,
            size=case.raw_size,
            post_only=True,
            client_order_id="cid-1",
        )
    )

    assert fake_client.last_amount is not None
    assert abs(fake_client.last_amount - case.expected) < 1e-12
    assert abs(order.size - case.expected) < 1e-12


def test_place_limit_order_bumps_size_to_min_size():
    adapter = GrvtLiveAdapter(Settings())
    fake_client = _ClientWithInstrument(min_size=0.01, base_decimals=9)
    adapter.__dict__["_client"] = fake_client

    order = asyncio.run(
        adapter.place_limit_order(
            symbol="BNB_USDT_Perp",
            side="sell",
            price=607.60,
            size=0.0012,
            post_only=True,
            client_order_id="cid-2",
        )
    )

    assert fake_client.last_amount is not None
    assert abs(fake_client.last_amount - 0.01) < 1e-12
    assert abs(order.size - 0.01) < 1e-12


def test_place_limit_order_prefers_explicit_size_step():
    adapter = GrvtLiveAdapter(Settings())
    fake_client = _ClientWithInstrument(min_size=0.001, base_decimals=9, size_step=0.005)
    adapter.__dict__["_client"] = fake_client

    order = asyncio.run(
        adapter.place_limit_order(
            symbol="BNB_USDT_Perp",
            side="buy",
            price=607.49,
            size=0.0179,
            post_only=True,
            client_order_id="cid-3",
        )
    )

    assert fake_client.last_amount is not None
    assert abs(fake_client.last_amount - 0.015) < 1e-12
    assert abs(order.size - 0.015) < 1e-12


def test_place_limit_order_reads_ccxt_style_constraints():
    adapter = GrvtLiveAdapter(Settings())
    fake_client = _ClientWithInstrument(
        min_size=0.0,
        base_decimals=0,
        size_step=None,
        market_overrides={
            "instrument": "XRP/USDT:USDT",
            "symbol": "XRP/USDT:USDT",
            "base": "XRP",
            "quote": "USDT",
            "limits": {"amount": {"min": 1.0}},
            "precision": {"amount": 1, "price": 0.0001},
            "info": {"symbol": "XRP/USDT:USDT"},
        },
    )
    adapter.__dict__["_client"] = fake_client

    order = asyncio.run(
        adapter.place_limit_order(
            symbol="XRP_USDT_Perp",
            side="buy",
            price=0.5321,
            size=3.87,
            post_only=True,
            client_order_id="cid-ccxt-1",
        )
    )

    assert fake_client.last_amount is not None
    assert abs(fake_client.last_amount - 3.0) < 1e-12
    assert abs(order.size - 3.0) < 1e-12


def test_place_limit_order_blocks_when_constraints_missing():
    adapter = GrvtLiveAdapter(Settings())
    fake_client = _ClientWithoutInstrument()
    adapter.__dict__["_client"] = fake_client

    with pytest.raises(InstrumentConstraintsError):
        asyncio.run(
            adapter.place_limit_order(
                symbol="SUI_USDT_Perp",
                side="buy",
                price=1.11,
                size=10.0,
                post_only=True,
                client_order_id="cid-missing-1",
            )
        )

    assert fake_client.last_amount is None


def test_close_position_taker_quantizes_reduce_only_size():
    adapter = GrvtLiveAdapter(Settings())
    fake_client = _ClientWithInstrument(min_size=0.5, base_decimals=9, size_step=0.5)
    adapter.__dict__["_client"] = fake_client

    order = asyncio.run(
        adapter.close_position_taker(
            symbol="SUI_USDT_Perp",
            side="sell",
            size=2.37,
            reduce_only=True,
        )
    )

    assert fake_client.last_amount is not None
    assert abs(fake_client.last_amount - 2.0) < 1e-12
    assert fake_client.last_order_type == "market"
    assert fake_client.last_params is not None
    assert fake_client.last_params["reduce_only"] is True
    assert fake_client.last_params["reduceOnly"] is True
    assert order.size == 2.0


def test_close_position_taker_raises_dust_when_position_below_min_size():
    adapter = GrvtLiveAdapter(Settings())
    fake_client = _ClientWithInstrument(min_size=1.0, base_decimals=9, size_step=1.0)
    adapter.__dict__["_client"] = fake_client

    with pytest.raises(PositionDustError):
        asyncio.run(
            adapter.close_position_taker(
                symbol="XRP_USDT_Perp",
                side="sell",
                size=0.6,
                reduce_only=True,
            )
        )

    assert fake_client.last_amount is None
