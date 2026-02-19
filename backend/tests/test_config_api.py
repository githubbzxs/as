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


def test_runtime_profile_update(tmp_path, monkeypatch):
    _set_paths(tmp_path, monkeypatch)

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
    _set_paths(tmp_path, monkeypatch)

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        app.state.container.engine._mode = "running"  # noqa: SLF001

        blocked = client.put(
            "/api/config/exchange",
            headers=headers,
            json={
                "grvt_api_key": "demo-key",
            },
        )
        assert blocked.status_code == 409
        assert "detail" in blocked.json()
        app.state.container.engine._mode = "idle"  # noqa: SLF001

    get_settings.cache_clear()


def test_exchange_update_in_idle(tmp_path, monkeypatch):
    _set_paths(tmp_path, monkeypatch)

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)

        resp = client.put(
            "/api/config/exchange",
            headers=headers,
            json={
                "grvt_api_key": "demo-key",
                "grvt_api_secret": "demo-secret",
                "grvt_trading_account_id": "demo-account",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["grvt_env"] == "prod"
        assert body["grvt_api_key_configured"] is True
        assert "grvt_api_key" not in body

        status_resp = client.get("/api/config/secrets/status", headers=headers)
        assert status_resp.status_code == 200
        status_body = status_resp.json()
        assert status_body["grvt_api_key_configured"] is True
        assert status_body["grvt_api_secret_configured"] is True

    get_settings.cache_clear()


def test_telegram_update_and_status(tmp_path, monkeypatch):
    _set_paths(tmp_path, monkeypatch)

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)

        before = client.get("/api/config/telegram", headers=headers)
        assert before.status_code == 200
        assert before.json()["telegram_bot_token_configured"] is False

        updated = client.put(
            "/api/config/telegram",
            headers=headers,
            json={
                "telegram_bot_token": "bot-token-1",
                "telegram_chat_id": "chat-id-1",
            },
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["telegram_bot_token_configured"] is True
        assert body["telegram_chat_id_configured"] is True

        status_resp = client.get("/api/config/secrets/status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["telegram_configured"] is True

        app.state.container.engine._mode = "running"  # noqa: SLF001
        blocked = client.put(
            "/api/config/telegram",
            headers=headers,
            json={"telegram_chat_id": "chat-id-2"},
        )
        assert blocked.status_code == 409
        app.state.container.engine._mode = "idle"  # noqa: SLF001

    get_settings.cache_clear()
