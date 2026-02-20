from __future__ import annotations

from app.schemas import RuntimeConfig, StrategyConfig, StrategyConfigView


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


AGGRESSIVE_EXECUTION_PRESET: dict[str, float] = {
    "min_spread_bps": 0.25,
    "max_spread_bps": 1.8,
    "requote_threshold_bps": 0.10,
    "requote_size_threshold_ratio": 0.08,
    "order_ttl_sec": 20.0,
    "quote_interval_sec": 0.25,
    "min_order_age_before_requote_sec": 0.25,
}


def strategy_to_runtime_config(strategy: StrategyConfig, current: RuntimeConfig) -> RuntimeConfig:
    recover_ratio = _clamp(strategy.max_inventory_equity_ratio * 0.75, 0.0, strategy.max_inventory_equity_ratio)
    merged = current.model_dump()
    merged.update(
        {
            "symbol": strategy.symbol,
            "base_gamma": strategy.as_gamma,
            "as_sigma": strategy.as_sigma,
            "liquidity_k": strategy.as_liquidity_k,
            "drawdown_kill_pct": strategy.max_drawdown_pct,
            "max_inventory_equity_ratio": strategy.max_inventory_equity_ratio,
            "single_side_recover_ratio": recover_ratio,
            "max_inventory_notional_pct": strategy.max_inventory_equity_ratio,
            "min_spread_bps": AGGRESSIVE_EXECUTION_PRESET["min_spread_bps"],
            "max_spread_bps": AGGRESSIVE_EXECUTION_PRESET["max_spread_bps"],
            "requote_threshold_bps": AGGRESSIVE_EXECUTION_PRESET["requote_threshold_bps"],
            "requote_size_threshold_ratio": AGGRESSIVE_EXECUTION_PRESET["requote_size_threshold_ratio"],
            "order_ttl_sec": int(AGGRESSIVE_EXECUTION_PRESET["order_ttl_sec"]),
            "quote_interval_sec": AGGRESSIVE_EXECUTION_PRESET["quote_interval_sec"],
            "min_order_age_before_requote_sec": AGGRESSIVE_EXECUTION_PRESET["min_order_age_before_requote_sec"],
        }
    )
    return RuntimeConfig.model_validate(merged)


def runtime_to_strategy_config(config: RuntimeConfig) -> StrategyConfig:
    return StrategyConfig(
        symbol=config.symbol,
        as_gamma=config.base_gamma,
        as_sigma=config.as_sigma,
        as_liquidity_k=config.liquidity_k,
        max_drawdown_pct=config.drawdown_kill_pct,
        max_inventory_equity_ratio=config.max_inventory_equity_ratio,
    )


def strategy_to_view(strategy: StrategyConfig, runtime: RuntimeConfig) -> StrategyConfigView:
    return StrategyConfigView(
        symbol=strategy.symbol,
        as_gamma=strategy.as_gamma,
        as_sigma=strategy.as_sigma,
        as_liquidity_k=strategy.as_liquidity_k,
        max_drawdown_pct=strategy.max_drawdown_pct,
        max_inventory_equity_ratio=strategy.max_inventory_equity_ratio,
        runtime_preview={
            "min_spread_bps": runtime.min_spread_bps,
            "max_spread_bps": runtime.max_spread_bps,
            "quote_interval_sec": runtime.quote_interval_sec,
            "order_ttl_sec": runtime.order_ttl_sec,
            "requote_threshold_bps": runtime.requote_threshold_bps,
            "min_order_age_before_requote_sec": runtime.min_order_age_before_requote_sec,
        },
    )
