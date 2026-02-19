from app.schemas import RuntimeConfig, RuntimeProfileConfig
from app.services.profile_mapper import profile_to_runtime_config, runtime_to_profile_config


def test_profile_to_runtime_aggressiveness_direction():
    base = RuntimeConfig()
    low = profile_to_runtime_config(
        RuntimeProfileConfig(aggressiveness=10, inventory_tolerance=50, risk_threshold=50),
        base,
    )
    high = profile_to_runtime_config(
        RuntimeProfileConfig(aggressiveness=90, inventory_tolerance=50, risk_threshold=50),
        base,
    )

    assert high.min_spread_bps < low.min_spread_bps
    assert high.quote_interval_sec < low.quote_interval_sec
    assert high.base_gamma < low.base_gamma


def test_profile_to_runtime_inventory_and_risk_direction():
    base = RuntimeConfig()
    conservative = profile_to_runtime_config(
        RuntimeProfileConfig(aggressiveness=50, inventory_tolerance=10, risk_threshold=10),
        base,
    )
    tolerant = profile_to_runtime_config(
        RuntimeProfileConfig(aggressiveness=50, inventory_tolerance=90, risk_threshold=90),
        base,
    )

    assert tolerant.max_inventory_notional > conservative.max_inventory_notional
    assert tolerant.max_single_order_notional > conservative.max_single_order_notional
    assert tolerant.drawdown_kill_pct > conservative.drawdown_kill_pct
    assert tolerant.recovery_readonly_sec < conservative.recovery_readonly_sec


def test_runtime_to_profile_in_range():
    profile = runtime_to_profile_config(RuntimeConfig())
    assert 0 <= profile.aggressiveness <= 100
    assert 0 <= profile.inventory_tolerance <= 100
    assert 0 <= profile.risk_threshold <= 100
