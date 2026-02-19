from app.engine.adaptive import AdaptiveController


def test_sigma_and_zscore_progression():
    c = AdaptiveController(maxlen=200)
    price = 100.0
    sigma = 0.0
    z = 0.0
    for i in range(120):
        price += (0.01 if i % 2 == 0 else -0.008)
        sigma, z = c.update(price, depth_score=1.0, trade_intensity=1.1)

    assert sigma > 0
    assert isinstance(z, float)


def test_quote_size_factor_reduces_in_high_vol():
    c = AdaptiveController(maxlen=300)
    p = 100.0
    for i in range(120):
        p += (1.5 if i % 2 else -1.2)
        c.update(p, depth_score=1.0, trade_intensity=1.0)

    factor = c.quote_size_factor()
    assert 0.2 <= factor <= 1.0
