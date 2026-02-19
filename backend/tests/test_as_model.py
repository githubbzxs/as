from app.engine.as_model import AsMarketMakerModel


def test_as_quote_within_spread_bounds():
    model = AsMarketMakerModel()
    decision = model.compute_quote(
        mid_price=100.0,
        sigma=0.002,
        inventory_base=0.0,
        max_inventory_base=10.0,
        base_gamma=0.12,
        gamma_min=0.02,
        gamma_max=0.8,
        liquidity_k=1.5,
        horizon_sec=15,
        min_spread_bps=4.0,
        max_spread_bps=60.0,
        quote_size_notional=100.0,
    )

    assert decision.bid_price < decision.ask_price
    assert 4.0 <= decision.spread_bps <= 60.0
    assert decision.quote_size_base > 0


def test_inventory_bias_moves_reservation_price():
    model = AsMarketMakerModel()
    neutral = model.compute_quote(
        mid_price=100.0,
        sigma=0.002,
        inventory_base=0.0,
        max_inventory_base=10.0,
        base_gamma=0.12,
        gamma_min=0.02,
        gamma_max=0.8,
        liquidity_k=1.5,
        horizon_sec=15,
        min_spread_bps=4.0,
        max_spread_bps=60.0,
        quote_size_notional=100.0,
    )
    long_inv = model.compute_quote(
        mid_price=100.0,
        sigma=0.002,
        inventory_base=5.0,
        max_inventory_base=10.0,
        base_gamma=0.12,
        gamma_min=0.02,
        gamma_max=0.8,
        liquidity_k=1.5,
        horizon_sec=15,
        min_spread_bps=4.0,
        max_spread_bps=60.0,
        quote_size_notional=100.0,
    )

    assert long_inv.reservation_price < neutral.reservation_price
