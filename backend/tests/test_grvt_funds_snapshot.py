import asyncio

from app.core.settings import Settings
from app.exchange.grvt_live import GrvtLiveAdapter


class _FakeClient:
    def __init__(self, balance):
        self._balance = balance

    def fetch_balance(self, mode):
        assert mode == "aggregated"
        return self._balance


def _build_adapter(balance):
    adapter = GrvtLiveAdapter(Settings())
    adapter.__dict__["_client"] = _FakeClient(balance)
    return adapter


def test_fetch_account_funds_prefers_usdt_fields():
    adapter = _build_adapter(
        {
            "USDT": {"free": 8.0, "used": 2.0, "total": 10.0},
            "total": {"USDT": 10.0},
        }
    )

    funds = asyncio.run(adapter.fetch_account_funds())

    assert funds.equity_usdt == 10.0
    assert funds.free_usdt == 8.0
    assert funds.used_usdt == 2.0
    assert "USDT.free" in funds.source
    assert "USDT.total" in funds.source


def test_fetch_account_funds_uses_map_fallbacks():
    adapter = _build_adapter(
        {
            "free": {"USDT": 6.5},
            "used": {"USDT": 1.5},
            "total": {"USDT": 8.0},
        }
    )

    funds = asyncio.run(adapter.fetch_account_funds())

    assert funds.equity_usdt == 8.0
    assert funds.free_usdt == 6.5
    assert funds.used_usdt == 1.5
    assert "free.USDT" in funds.source
    assert "total.USDT" in funds.source


def test_fetch_account_funds_falls_back_to_equity_field():
    adapter = _build_adapter(
        {
            "equity": 12.0,
            "USDT": {"used": 2.0},
        }
    )

    funds = asyncio.run(adapter.fetch_account_funds())

    assert funds.equity_usdt == 12.0
    assert funds.free_usdt == 10.0
    assert funds.used_usdt == 2.0
    assert "equity" in funds.source
    assert "equity-used" in funds.source


def test_fetch_account_funds_invalid_balance_returns_zero():
    adapter = _build_adapter(None)
    funds = asyncio.run(adapter.fetch_account_funds())

    assert funds.equity_usdt == 0.0
    assert funds.free_usdt == 0.0
    assert funds.used_usdt == 0.0
    assert funds.source == "invalid-balance"
