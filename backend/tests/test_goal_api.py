from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import create_app


def _auth_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/auth/login",
        json={
            "username": "admin",
            "password": "admin123",
        },
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _set_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNTIME_CONFIG_PATH", str(tmp_path / "runtime.json"))
    monkeypatch.setenv("EXCHANGE_CONFIG_PATH", str(tmp_path / "exchange.json"))
    monkeypatch.setenv("TELEGRAM_CONFIG_PATH", str(tmp_path / "telegram.json"))
    monkeypatch.setenv("APP_JWT_SECRET", "test-secret")
    get_settings.cache_clear()


def test_strategy_config_update(tmp_path, monkeypatch):
    _set_paths(tmp_path, monkeypatch)
    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        put_resp = client.put(
            "/api/config/strategy",
            headers=headers,
            json={
                "symbol": "BNB_USDT_Perp",
                "as_gamma": 0.12,
                "as_sigma": 0.002,
                "as_liquidity_k": 1.8,
                "max_drawdown_pct": 8.5,
                "max_inventory_equity_ratio": 0.6,
            },
        )
        assert put_resp.status_code == 200
        body = put_resp.json()
        assert body["symbol"] == "BNB_USDT_Perp"
        assert body["as_gamma"] == 0.12
        assert body["as_sigma"] == 0.002
        assert body["runtime_preview"]["quote_interval_sec"] > 0

        get_resp = client.get("/api/config/strategy", headers=headers)
        assert get_resp.status_code == 200
        got = get_resp.json()
        assert got["symbol"] == "BNB_USDT_Perp"
        assert got["as_liquidity_k"] == 1.8

        metrics_resp = client.get("/api/metrics", headers=headers)
        assert metrics_resp.status_code == 200
        summary = metrics_resp.json()["summary"]
        assert "wear_per_10k" in summary

    get_settings.cache_clear()


def test_strategy_symbol_change_blocked_when_engine_running(tmp_path, monkeypatch):
    _set_paths(tmp_path, monkeypatch)
    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        client.app.state.container.engine._mode = "running"  # noqa: SLF001
        put_resp = client.put(
            "/api/config/strategy",
            headers=headers,
            json={
                "symbol": "XRP_USDT_Perp",
                "as_gamma": 0.12,
                "as_sigma": 0.002,
                "as_liquidity_k": 1.8,
                "max_drawdown_pct": 8.5,
                "max_inventory_equity_ratio": 0.6,
            },
        )
        assert put_resp.status_code == 409
        client.app.state.container.engine._mode = "idle"  # noqa: SLF001

    get_settings.cache_clear()


def test_strategy_config_accepts_hype_symbol(tmp_path, monkeypatch):
    _set_paths(tmp_path, monkeypatch)
    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        put_resp = client.put(
            "/api/config/strategy",
            headers=headers,
            json={
                "symbol": "HYPE_USDT_Perp",
                "as_gamma": 0.12,
                "as_sigma": 0.002,
                "as_liquidity_k": 1.8,
                "max_drawdown_pct": 8.5,
                "max_inventory_equity_ratio": 0.6,
            },
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["symbol"] == "HYPE_USDT_Perp"

        get_resp = client.get("/api/config/strategy", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["symbol"] == "HYPE_USDT_Perp"

    get_settings.cache_clear()
