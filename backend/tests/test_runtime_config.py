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
