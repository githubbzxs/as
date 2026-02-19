from __future__ import annotations

from app.core.settings import Settings
from app.exchange.base import ExchangeAdapter
from app.exchange.grvt_live import GrvtLiveAdapter


def build_exchange_adapter(
    settings: Settings,
    *,
    grvt_env: str | None = None,
    grvt_api_key: str | None = None,
    grvt_api_secret: str | None = None,
    grvt_trading_account_id: str | None = None,
) -> ExchangeAdapter:
    """根据配置构造交易所适配器。"""
    return GrvtLiveAdapter(
        settings,
        grvt_env=grvt_env,
        grvt_api_key=grvt_api_key,
        grvt_api_secret=grvt_api_secret,
        grvt_trading_account_id=grvt_trading_account_id,
    )
