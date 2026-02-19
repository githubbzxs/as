from __future__ import annotations

import asyncio

from app.core.settings import Settings
from app.exchange.grvt_live import GrvtLiveAdapter


class _ClientWithBrokenOrderBook:
    def fetch_ticker(self, symbol: str) -> dict:
        return {
            "best_bid_price": 610.1,
            "best_ask_price": 610.3,
            "mid_price": 610.2,
            "buy_volume_u": 1200.0,
            "sell_volume_u": 1100.0,
        }

    def fetch_order_book(self, symbol: str, depth: int) -> dict:
        raise KeyError("event_time")


def test_fetch_market_snapshot_fallback_when_order_book_error():
    adapter = GrvtLiveAdapter(Settings())
    adapter.__dict__["_client"] = _ClientWithBrokenOrderBook()

    snap = asyncio.run(adapter.fetch_market_snapshot("BNB_USDT-PERP"))

    assert snap.symbol == "BNB_USDT_Perp"
    assert snap.bid > 0
    assert snap.ask > 0
    assert snap.mid > 0
    assert snap.depth_score >= 0.2


def test_extract_order_id_accepts_string_client_order_id():
    payload = {
        "metadata": {
            "client_order_id": "bid-d4f1782781464ece",
        }
    }
    assert GrvtLiveAdapter._extract_order_id(payload) == "bid-d4f1782781464ece"
