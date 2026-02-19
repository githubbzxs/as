from __future__ import annotations

from app.core.settings import Settings
from app.exchange.base import ExchangeAdapter
from app.exchange.grvt_live import GrvtLiveAdapter
from app.exchange.mock_grvt import MockGrvtAdapter


def build_exchange_adapter(settings: Settings) -> ExchangeAdapter:
    """根据配置构造交易所适配器。"""
    if settings.grvt_use_mock:
        return MockGrvtAdapter()
    return GrvtLiveAdapter(settings)
