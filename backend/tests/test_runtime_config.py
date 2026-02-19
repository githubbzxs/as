from pathlib import Path

from app.services.runtime_config import RuntimeConfigStore


def test_runtime_config_store_update(tmp_path: Path):
    path = tmp_path / "runtime.json"
    store = RuntimeConfigStore(path)
    cfg = store.get()
    assert cfg.symbol

    updated = store.update({"symbol": "BNB_USDT_Perp", "equity_risk_pct": 0.12})
    assert updated.equity_risk_pct == 0.12

    store2 = RuntimeConfigStore(path)
    assert store2.get().equity_risk_pct == 0.12
    assert store2.get_goal().symbol == "BNB_USDT_Perp"
    assert store2.get_goal().target_hourly_notional >= 100


def test_runtime_config_store_migrates_legacy_format(tmp_path: Path):
    path = tmp_path / "runtime.json"
    path.write_text(
        '{"symbol":"BNB_USDT_Perp","equity_risk_pct":0.11,"max_inventory_notional":1800}',
        encoding="utf-8",
    )
    store = RuntimeConfigStore(path)
    assert store.get().equity_risk_pct == 0.11
    assert store.get_goal().symbol == "BNB_USDT_Perp"
    assert store.get_goal().principal_usdt >= 1.0
