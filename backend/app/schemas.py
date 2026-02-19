from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HealthStatus(BaseModel):
    engine_running: bool
    mode: Literal["idle", "readonly", "running", "halted"]
    kill_reason: str | None = None
    last_error: str | None = None
    exchange_connected: bool
    symbol: str
    updated_at: datetime


class RuntimeConfig(BaseModel):
    symbol: str = "BNB_USDT_Perp"

    equity_risk_pct: float = Field(default=0.10, ge=0.001, le=1.0)
    max_inventory_notional: float = Field(default=2000.0, ge=10)
    max_single_order_notional: float = Field(default=350.0, ge=1)

    min_spread_bps: float = Field(default=1.2, ge=0.1)
    max_spread_bps: float = Field(default=8.0, ge=1)

    requote_threshold_bps: float = Field(default=0.4, ge=0.1)
    order_ttl_sec: int = Field(default=15, ge=1, le=300)
    quote_interval_sec: float = Field(default=0.6, ge=0.2, le=10)

    sigma_window_sec: int = Field(default=60, ge=10, le=600)
    depth_window_sec: int = Field(default=30, ge=5, le=300)
    trade_intensity_window_sec: int = Field(default=30, ge=5, le=300)

    drawdown_kill_pct: float = Field(default=10.0, ge=0.1, le=80)
    volatility_kill_zscore: float = Field(default=4.0, ge=1.0, le=10.0)
    max_consecutive_failures: int = Field(default=6, ge=1, le=50)

    recovery_readonly_sec: int = Field(default=180, ge=10, le=1800)

    base_gamma: float = Field(default=0.12, ge=0.01, le=5.0)
    gamma_min: float = Field(default=0.02, ge=0.001, le=2.0)
    gamma_max: float = Field(default=0.8, ge=0.01, le=10.0)
    liquidity_k: float = Field(default=1.5, ge=0.1, le=30.0)

    @field_validator("max_spread_bps")
    @classmethod
    def validate_spread(cls, v: float, info):
        data = info.data
        min_spread = data.get("min_spread_bps")
        if min_spread is not None and v < min_spread:
            raise ValueError("max_spread_bps 不能小于 min_spread_bps")
        return v


class RuntimeProfileConfig(BaseModel):
    aggressiveness: float = Field(default=55.0, ge=0, le=100)
    inventory_tolerance: float = Field(default=40.0, ge=0, le=100)
    risk_threshold: float = Field(default=45.0, ge=0, le=100)


class RuntimeProfileView(RuntimeProfileConfig):
    runtime_preview: dict[str, float | int]


class ExchangeConfigUpdateRequest(BaseModel):
    grvt_api_key: str | None = None
    grvt_api_secret: str | None = None
    grvt_trading_account_id: str | None = None

    clear_grvt_api_key: bool = False
    clear_grvt_api_secret: bool = False
    clear_grvt_trading_account_id: bool = False


class ExchangeConfigView(BaseModel):
    grvt_env: str
    grvt_api_key_configured: bool
    grvt_api_secret_configured: bool
    grvt_trading_account_id_configured: bool
    updated_at: datetime


class TelegramConfigUpdateRequest(BaseModel):
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    clear_telegram_bot_token: bool = False
    clear_telegram_chat_id: bool = False


class TelegramConfigView(BaseModel):
    telegram_bot_token_configured: bool
    telegram_chat_id_configured: bool
    updated_at: datetime


class SecretsStatus(BaseModel):
    grvt_api_key_configured: bool
    grvt_api_secret_configured: bool
    grvt_trading_account_id_configured: bool
    app_jwt_secret_configured: bool
    telegram_configured: bool


class OrderView(BaseModel):
    order_id: str
    side: Literal["buy", "sell"]
    price: float
    size: float
    status: str
    created_at: datetime


class TradeView(BaseModel):
    trade_id: str
    side: Literal["buy", "sell"]
    price: float
    size: float
    fee: float = 0.0
    created_at: datetime


class MetricsSummary(BaseModel):
    timestamp: datetime
    mid_price: float
    spread_bps: float
    distance_bid_bps: float = 0.0
    distance_ask_bps: float = 0.0
    sigma: float
    sigma_zscore: float
    inventory_base: float
    inventory_notional: float
    equity: float
    pnl: float
    drawdown_pct: float
    quote_size_base: float
    quote_size_notional: float
    maker_fill_count_1m: int = 0
    cancel_count_1m: int = 0
    fill_to_cancel_ratio: float = 0.0
    time_in_book_p50_sec: float = 0.0
    time_in_book_p90_sec: float = 0.0
    open_order_age_buy_sec: float = 0.0
    open_order_age_sell_sec: float = 0.0
    requote_reason: str = "none"
    mode: str
    consecutive_failures: int


class TimeSeriesPoint(BaseModel):
    t: datetime
    value: float


class MetricsResponse(BaseModel):
    summary: MetricsSummary
    series: dict[str, list[TimeSeriesPoint]]


class EngineCommandResponse(BaseModel):
    message: str
    mode: str


class StreamEnvelope(BaseModel):
    type: str
    ts: datetime
    payload: dict
