from __future__ import annotations

from app.schemas import GoalConfig, GoalConfigView, RiskProfile, RuntimeConfig


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


LEVERAGE_MULTIPLIER = 50.0
MIN_INVENTORY_SINGLE_ORDER_RATIO = 1.8


_PROFILE_SINGLE_NOTIONAL_FACTOR: dict[RiskProfile, float] = {
    "safe": 0.35,
    "balanced": 0.55,
    "throughput": 0.75,
}

_PROFILE_PRESETS: dict[RiskProfile, dict[str, float | int]] = {
    "safe": {
        "quote_interval_sec": 0.90,
        "min_spread_bps": 1.20,
        "max_spread_bps": 8.00,
        "requote_threshold_bps": 0.40,
        "drawdown_kill_pct": 4.0,
        "volatility_kill_zscore": 2.4,
        "max_consecutive_failures": 4,
        "recovery_readonly_sec": 220,
        "base_gamma": 0.14,
        "max_inventory_notional_pct": 0.25,
    },
    "balanced": {
        "quote_interval_sec": 0.55,
        "min_spread_bps": 0.70,
        "max_spread_bps": 5.00,
        "requote_threshold_bps": 0.25,
        "drawdown_kill_pct": 6.0,
        "volatility_kill_zscore": 3.0,
        "max_consecutive_failures": 6,
        "recovery_readonly_sec": 140,
        "base_gamma": 0.10,
        "max_inventory_notional_pct": 0.40,
    },
    "throughput": {
        "quote_interval_sec": 0.30,
        "min_spread_bps": 0.35,
        "max_spread_bps": 2.80,
        "requote_threshold_bps": 0.15,
        "drawdown_kill_pct": 8.0,
        "volatility_kill_zscore": 3.6,
        "max_consecutive_failures": 8,
        "recovery_readonly_sec": 90,
        "base_gamma": 0.07,
        "max_inventory_notional_pct": 0.60,
    },
}


def goal_to_runtime_config(goal: GoalConfig, current: RuntimeConfig) -> RuntimeConfig:
    principal = max(1.0, float(goal.principal_usdt))
    effective_principal = principal * LEVERAGE_MULTIPLIER
    target_hourly = max(100.0, float(goal.target_hourly_notional))
    profile = goal.risk_profile
    preset = _PROFILE_PRESETS[profile]

    target_per_min = target_hourly / 60.0
    single_notional_raw = target_per_min * _PROFILE_SINGLE_NOTIONAL_FACTOR[profile]
    single_notional_cap = max(8.0, effective_principal * 80.0)
    max_single_order_notional = _clamp(single_notional_raw, 8.0, single_notional_cap)

    max_inventory_notional_pct = _clamp(float(preset["max_inventory_notional_pct"]), 0.0, 0.60)
    max_inventory_notional = max(30.0, effective_principal * max_inventory_notional_pct)
    max_inventory_notional = max(
        max_inventory_notional,
        max_single_order_notional * MIN_INVENTORY_SINGLE_ORDER_RATIO,
    )

    equity_risk_pct = _clamp((max_single_order_notional / effective_principal) * 0.08, 0.03, 0.20)
    min_spread_bps = float(preset["min_spread_bps"])
    max_spread_bps = max(min_spread_bps + 1.0, float(preset["max_spread_bps"]))

    merged = current.model_dump()
    merged.update(
        {
            "symbol": goal.symbol,
            "min_spread_bps": min_spread_bps,
            "max_spread_bps": max_spread_bps,
            "quote_interval_sec": float(preset["quote_interval_sec"]),
            "requote_threshold_bps": float(preset["requote_threshold_bps"]),
            "max_single_order_notional": max_single_order_notional,
            "max_inventory_notional_pct": max_inventory_notional_pct,
            "max_inventory_notional": max_inventory_notional,
            "equity_risk_pct": equity_risk_pct,
            "drawdown_kill_pct": float(preset["drawdown_kill_pct"]),
            "volatility_kill_zscore": float(preset["volatility_kill_zscore"]),
            "max_consecutive_failures": int(preset["max_consecutive_failures"]),
            "recovery_readonly_sec": int(preset["recovery_readonly_sec"]),
            "base_gamma": float(preset["base_gamma"]),
        }
    )
    return RuntimeConfig.model_validate(merged)


def runtime_to_goal_config(config: RuntimeConfig) -> GoalConfig:
    if config.min_spread_bps <= 0.45:
        profile: RiskProfile = "throughput"
    elif config.min_spread_bps <= 0.90:
        profile = "balanced"
    else:
        profile = "safe"

    effective_principal = max(
        1.0,
        config.max_inventory_notional / max(config.max_inventory_notional_pct, 1e-6),
    )
    principal = max(1.0, effective_principal / LEVERAGE_MULTIPLIER)
    target_hourly = max(
        100.0,
        config.max_single_order_notional / _PROFILE_SINGLE_NOTIONAL_FACTOR[profile] * 60.0,
    )
    return GoalConfig(
        symbol=config.symbol,
        principal_usdt=round(principal, 4),
        target_hourly_notional=round(target_hourly, 4),
        risk_profile=profile,
        env_mode="testnet",
    )


def goal_to_view(goal: GoalConfig, runtime: RuntimeConfig) -> GoalConfigView:
    return GoalConfigView(
        principal_usdt=goal.principal_usdt,
        target_hourly_notional=goal.target_hourly_notional,
        risk_profile=goal.risk_profile,
        env_mode=goal.env_mode,
        runtime_preview={
            "symbol": runtime.symbol,
            "min_spread_bps": runtime.min_spread_bps,
            "max_spread_bps": runtime.max_spread_bps,
            "quote_interval_sec": runtime.quote_interval_sec,
            "max_single_order_notional": runtime.max_single_order_notional,
            "max_inventory_notional_pct": runtime.max_inventory_notional_pct,
            "drawdown_kill_pct": runtime.drawdown_kill_pct,
        },
    )
