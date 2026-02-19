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


def test_runtime_profile_update(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_CONFIG_PATH", str(tmp_path / "runtime.json"))
    monkeypatch.setenv("EXCHANGE_CONFIG_PATH", str(tmp_path / "exchange.json"))
    monkeypatch.setenv("GRVT_USE_MOCK", "true")
    monkeypatch.setenv("APP_JWT_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        resp = client.put(
            "/api/config/runtime/profile",
            headers=headers,
            json={
                "aggressiveness": 78,
                "inventory_tolerance": 65,
                "risk_threshold": 40,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["aggressiveness"] == 78
        assert "runtime_preview" in body

        raw = client.get("/api/config/runtime", headers=headers)
        assert raw.status_code == 200
        raw_body = raw.json()
        assert raw_body["max_inventory_notional"] > 500
        assert raw_body["min_spread_bps"] < 10

    get_settings.cache_clear()


def test_exchange_update_forbidden_when_running(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_CONFIG_PATH", str(tmp_path / "runtime.json"))
    monkeypatch.setenv("EXCHANGE_CONFIG_PATH", str(tmp_path / "exchange.json"))
    monkeypatch.setenv("GRVT_USE_MOCK", "true")
    monkeypatch.setenv("APP_JWT_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)

        started = client.post("/api/engine/start", headers=headers)
        assert started.status_code == 200

        blocked = client.put(
            "/api/config/exchange",
            headers=headers,
            json={
                "grvt_env": "testnet",
            },
        )
        assert blocked.status_code == 409
        assert "禁止修改 API" in blocked.text

        stopped = client.post("/api/engine/stop", headers=headers)
        assert stopped.status_code == 200

    get_settings.cache_clear()


def test_exchange_update_in_idle(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_CONFIG_PATH", str(tmp_path / "runtime.json"))
    monkeypatch.setenv("EXCHANGE_CONFIG_PATH", str(tmp_path / "exchange.json"))
    monkeypatch.setenv("GRVT_USE_MOCK", "true")
    monkeypatch.setenv("APP_JWT_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)

        resp = client.put(
            "/api/config/exchange",
            headers=headers,
            json={
                "grvt_env": "prod",
                "grvt_use_mock": False,
                "grvt_api_key": "demo-key",
                "grvt_api_secret": "demo-secret",
                "grvt_trading_account_id": "demo-account",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["grvt_env"] == "prod"
        assert body["grvt_use_mock"] is False
        assert body["grvt_api_key_configured"] is True
        assert "grvt_api_key" not in body

        status_resp = client.get("/api/config/secrets/status", headers=headers)
        assert status_resp.status_code == 200
        status_body = status_resp.json()
        assert status_body["grvt_api_key_configured"] is True
        assert status_body["grvt_api_secret_configured"] is True

    get_settings.cache_clear()
