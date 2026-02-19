from __future__ import annotations

from app.schemas import RuntimeConfig, RuntimeProfileConfig, RuntimeProfileView


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_ratio(score: float) -> float:
    return _clamp(score, 0.0, 100.0) / 100.0


def _avg(values: list[float]) -> float:
    if not values:
        return 50.0
    return sum(values) / len(values)


def _to_score(value: float, low: float, high: float, inverse: bool = False) -> float:
    span = max(high - low, 1e-9)
    normalized = (value - low) / span
    normalized = _clamp(normalized, 0.0, 1.0)
    if inverse:
        normalized = 1.0 - normalized
    return normalized * 100.0


def profile_to_runtime_config(profile: RuntimeProfileConfig, current: RuntimeConfig) -> RuntimeConfig:
    """将三旋钮画像映射到运行参数。"""

    a = _to_ratio(profile.aggressiveness)
    i = _to_ratio(profile.inventory_tolerance)
    r = _to_ratio(profile.risk_threshold)

    # 成交优先：高激进度时明显收窄价差和重报价门槛。
    min_spread_bps = 0.35 + (1.0 - a) * 3.2
    max_spread_bps = 2.2 + (1.0 - a) * 16.0
    if max_spread_bps < min_spread_bps + 1.0:
        max_spread_bps = min_spread_bps + 1.0

    merged = current.model_dump()
    merged.update(
        {
            "base_gamma": 0.18 - 0.14 * a,
            "min_spread_bps": min_spread_bps,
            "max_spread_bps": max_spread_bps,
            "requote_threshold_bps": 0.15 + (1.0 - a) * 0.95,
            "quote_interval_sec": 0.25 + (1.0 - a) * 0.85,
            "max_inventory_notional_pct": 0.05 + i * 1.45,
            "max_inventory_notional": 500.0 + i * 12000.0,
            "max_single_order_notional": 120.0 + i * 680.0,
            "equity_risk_pct": 0.03 + i * 0.22,
            "drawdown_kill_pct": 3.0 + r * 9.0,
            "volatility_kill_zscore": 1.6 + r * 3.4,
            "max_consecutive_failures": int(round(2 + r * 12)),
            "recovery_readonly_sec": int(round(300 - r * 250)),
        }
    )

    return RuntimeConfig.model_validate(merged)


def runtime_to_profile_config(config: RuntimeConfig) -> RuntimeProfileConfig:
    """从运行参数反推三旋钮画像。"""

    aggressiveness = _avg(
        [
            _to_score(config.base_gamma, 0.04, 0.18, inverse=True),
            _to_score(config.min_spread_bps, 0.35, 3.55, inverse=True),
            _to_score(config.quote_interval_sec, 0.25, 1.10, inverse=True),
            _to_score(config.requote_threshold_bps, 0.15, 1.10, inverse=True),
        ]
    )
    inventory_tolerance = _avg(
        [
            _to_score(config.max_inventory_notional_pct, 0.05, 1.50),
            _to_score(config.max_inventory_notional, 500.0, 12500.0),
            _to_score(config.max_single_order_notional, 120.0, 800.0),
            _to_score(config.equity_risk_pct, 0.03, 0.25),
        ]
    )
    risk_threshold = _avg(
        [
            _to_score(config.drawdown_kill_pct, 3.0, 12.0),
            _to_score(config.volatility_kill_zscore, 1.6, 5.0),
            _to_score(float(config.max_consecutive_failures), 2.0, 14.0),
            _to_score(float(config.recovery_readonly_sec), 50.0, 300.0, inverse=True),
        ]
    )

    return RuntimeProfileConfig(
        aggressiveness=round(_clamp(aggressiveness, 0.0, 100.0), 2),
        inventory_tolerance=round(_clamp(inventory_tolerance, 0.0, 100.0), 2),
        risk_threshold=round(_clamp(risk_threshold, 0.0, 100.0), 2),
    )


def runtime_to_profile_view(config: RuntimeConfig) -> RuntimeProfileView:
    profile = runtime_to_profile_config(config)
    return RuntimeProfileView(
        aggressiveness=profile.aggressiveness,
        inventory_tolerance=profile.inventory_tolerance,
        risk_threshold=profile.risk_threshold,
        runtime_preview={
            "base_gamma": config.base_gamma,
            "min_spread_bps": config.min_spread_bps,
            "max_spread_bps": config.max_spread_bps,
            "max_inventory_notional_pct": config.max_inventory_notional_pct,
            "max_inventory_notional": config.max_inventory_notional,
            "drawdown_kill_pct": config.drawdown_kill_pct,
        },
    )
