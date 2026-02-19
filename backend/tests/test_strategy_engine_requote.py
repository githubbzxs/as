from app.engine.strategy_engine import StrategyEngine


def test_collect_requote_reasons_classification():
    reasons = StrategyEngine._collect_requote_reasons(
        buy_order=None,
        sell_order={"id": "1"},
        only_sell=False,
        only_buy=False,
        buy_dev=False,
        sell_dev=True,
        ttl_expired=True,
    )

    assert "missing-side-buy" in reasons
    assert "price-deviation-sell" in reasons
    assert "ttl-expired" in reasons


def test_collect_requote_reasons_inventory_limit():
    reasons = StrategyEngine._collect_requote_reasons(
        buy_order={"id": "1"},
        sell_order={"id": "2"},
        only_sell=True,
        only_buy=False,
        buy_dev=False,
        sell_dev=False,
        ttl_expired=False,
    )

    assert reasons == ["inventory-limit"]


def test_new_client_order_id_is_numeric():
    order_id = StrategyEngine._new_client_order_id("buy")
    assert order_id.isdigit()
    assert len(order_id) >= 20
