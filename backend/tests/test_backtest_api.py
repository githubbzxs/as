import time

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


def test_backtest_job_api(tmp_path, monkeypatch):
    _set_paths(tmp_path, monkeypatch)
    data = tmp_path / "prices.csv"
    data.write_text(
        "\n".join(
            [
                "timestamp,mid",
                "2026-02-19T00:00:00Z,100",
                "2026-02-19T00:01:00Z,99.8",
                "2026-02-19T00:02:00Z,100.4",
            ]
        ),
        encoding="utf-8",
    )

    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        create_resp = client.post(
            "/api/backtest/jobs",
            headers=headers,
            json={
                "data_file": str(data),
                "symbol": "BNB_USDT_Perp",
                "principal_usdt": 10.0,
                "target_hourly_notional": 10000.0,
                "risk_profile": "balanced",
            },
        )
        assert create_resp.status_code == 200
        job_id = create_resp.json()["job_id"]

        status_value = "queued"
        for _ in range(50):
            status_resp = client.get(f"/api/backtest/jobs/{job_id}", headers=headers)
            assert status_resp.status_code == 200
            status_value = status_resp.json()["status"]
            if status_value in {"completed", "failed"}:
                break
            time.sleep(0.05)
        assert status_value == "completed"

        report_resp = client.get(f"/api/backtest/jobs/{job_id}/report", headers=headers)
        assert report_resp.status_code == 200
        assert report_resp.json()["symbol"] == "BNB_USDT_Perp"

    get_settings.cache_clear()
