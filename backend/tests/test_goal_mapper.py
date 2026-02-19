from app.schemas import GoalConfig, RuntimeConfig
from app.services.goal_mapper import (
    LEVERAGE_MULTIPLIER,
    MIN_INVENTORY_SINGLE_ORDER_RATIO,
    goal_to_runtime_config,
    runtime_to_goal_config,
)


def test_goal_to_runtime_throughput_more_aggressive_than_safe():
    current = RuntimeConfig()
    safe = goal_to_runtime_config(
        GoalConfig(principal_usdt=10, target_hourly_notional=10000, risk_profile="safe"),
        current,
    )
    throughput = goal_to_runtime_config(
        GoalConfig(principal_usdt=10, target_hourly_notional=10000, risk_profile="throughput"),
        current,
    )

    assert throughput.min_spread_bps < safe.min_spread_bps
    assert throughput.quote_interval_sec < safe.quote_interval_sec
    assert throughput.max_inventory_notional_pct >= safe.max_inventory_notional_pct


def test_runtime_to_goal_returns_valid_range():
    goal = runtime_to_goal_config(RuntimeConfig())

    assert goal.symbol == "BNB_USDT_Perp"
    assert goal.principal_usdt >= 1.0
    assert goal.target_hourly_notional >= 100.0
    assert goal.risk_profile in {"safe", "balanced", "throughput"}


def test_goal_to_runtime_overrides_symbol():
    current = RuntimeConfig(symbol="BNB_USDT_Perp")
    mapped = goal_to_runtime_config(
        GoalConfig(symbol="XRP_USDT_Perp", principal_usdt=10, target_hourly_notional=10000, risk_profile="balanced"),
        current,
    )
    assert mapped.symbol == "XRP_USDT_Perp"


def test_goal_to_runtime_uses_fixed_leverage_for_inventory_mapping():
    current = RuntimeConfig()
    goal = GoalConfig(symbol="BNB_USDT_Perp", principal_usdt=10, target_hourly_notional=10000, risk_profile="throughput")
    mapped = goal_to_runtime_config(goal, current)

    assert mapped.max_inventory_notional >= goal.principal_usdt * LEVERAGE_MULTIPLIER * mapped.max_inventory_notional_pct
    assert mapped.max_inventory_notional >= mapped.max_single_order_notional * MIN_INVENTORY_SINGLE_ORDER_RATIO


def test_runtime_to_goal_recovers_principal_scale_from_leverage_mapping():
    current = RuntimeConfig()
    goal = GoalConfig(symbol="BNB_USDT_Perp", principal_usdt=10, target_hourly_notional=10000, risk_profile="throughput")
    mapped = goal_to_runtime_config(goal, current)

    restored = runtime_to_goal_config(mapped)
    assert abs(restored.principal_usdt - goal.principal_usdt) < 1e-9
