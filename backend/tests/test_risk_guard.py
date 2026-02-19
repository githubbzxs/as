from app.engine.risk_guard import RiskGuard, RiskInput


def test_drawdown_computation():
    g = RiskGuard()
    assert g.update_drawdown(1000) == 0
    assert g.update_drawdown(1100) == 0
    dd = g.update_drawdown(990)
    assert round(dd, 2) == 10.0


def test_risk_trigger_by_consecutive_failures():
    g = RiskGuard()
    result = g.evaluate(
        RiskInput(equity=1000, drawdown_pct=1.0, sigma_zscore=0.0, consecutive_failures=6),
        drawdown_kill_pct=8.0,
        volatility_kill_zscore=4.0,
        max_consecutive_failures=5,
    )
    assert result.triggered is True


def test_risk_trigger_by_drawdown():
    g = RiskGuard()
    result = g.evaluate(
        RiskInput(equity=900, drawdown_pct=9.2, sigma_zscore=0.0, consecutive_failures=1),
        drawdown_kill_pct=8.0,
        volatility_kill_zscore=4.0,
        max_consecutive_failures=5,
    )
    assert result.triggered is True
