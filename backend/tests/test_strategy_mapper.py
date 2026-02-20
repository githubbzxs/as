from app.schemas import RuntimeConfig, StrategyConfig
from app.services.strategy_mapper import runtime_to_strategy_config, strategy_to_runtime_config


def test_strategy_to_runtime_mapping():
    current = RuntimeConfig()
    strategy = StrategyConfig(
        symbol="XRP_USDT_Perp",
        as_gamma=0.16,
        as_sigma=0.002,
        as_liquidity_k=2.2,
        max_drawdown_pct=7.5,
        max_inventory_equity_ratio=0.55,
    )
    mapped = strategy_to_runtime_config(strategy, current)

    assert mapped.symbol == "XRP_USDT_Perp"
    assert mapped.base_gamma == 0.16
    assert mapped.as_sigma == 0.002
    assert mapped.liquidity_k == 2.2
    assert mapped.drawdown_kill_pct == 7.5
    assert mapped.max_inventory_equity_ratio == 0.55
    assert mapped.single_side_recover_ratio < mapped.max_inventory_equity_ratio
    assert mapped.min_spread_bps == 0.25
    assert mapped.max_spread_bps == 1.8
    assert mapped.requote_threshold_bps == 0.1
    assert mapped.requote_size_threshold_ratio == 0.08
    assert mapped.quote_interval_sec == 0.25
    assert mapped.min_order_age_before_requote_sec == 0.25


def test_runtime_to_strategy_mapping():
    runtime = RuntimeConfig(
        symbol="SUI_USDT_Perp",
        base_gamma=0.21,
        as_sigma=0.003,
        liquidity_k=1.9,
        drawdown_kill_pct=5.8,
        max_inventory_equity_ratio=0.62,
    )
    strategy = runtime_to_strategy_config(runtime)

    assert strategy.symbol == "SUI_USDT_Perp"
    assert strategy.as_gamma == 0.21
    assert strategy.as_sigma == 0.003
    assert strategy.as_liquidity_k == 1.9
    assert strategy.max_drawdown_pct == 5.8
    assert strategy.max_inventory_equity_ratio == 0.62


def test_strategy_mapping_supports_hype_symbol():
    current = RuntimeConfig()
    strategy = StrategyConfig(
        symbol="HYPE_USDT_Perp",
        as_gamma=0.11,
        as_sigma=0.0012,
        as_liquidity_k=1.7,
        max_drawdown_pct=8.0,
        max_inventory_equity_ratio=0.5,
    )

    mapped = strategy_to_runtime_config(strategy, current)
    assert mapped.symbol == "HYPE_USDT_Perp"
    assert runtime_to_strategy_config(mapped).symbol == "HYPE_USDT_Perp"
