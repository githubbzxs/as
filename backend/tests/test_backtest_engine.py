from pathlib import Path

from app.backtest.engine import run_backtest
from app.schemas import BacktestJobRequest


def test_backtest_engine_generates_report(tmp_path: Path):
    data = tmp_path / "prices.csv"
    data.write_text(
        "\n".join(
            [
                "timestamp,mid",
                "2026-02-19T00:00:00Z,100",
                "2026-02-19T00:01:00Z,99.8",
                "2026-02-19T00:02:00Z,100.4",
                "2026-02-19T00:03:00Z,100.1",
                "2026-02-19T00:04:00Z,100.8",
            ]
        ),
        encoding="utf-8",
    )

    report = run_backtest(
        BacktestJobRequest(
            data_file=str(data),
            symbol="BNB_USDT_Perp",
            principal_usdt=10.0,
            target_hourly_notional=10000.0,
            risk_profile="throughput",
        )
    )
    assert report.points == 5
    assert report.total_notional >= 0
    assert report.target_hourly_notional == 10000.0
    assert "max_single_order_notional" in report.runtime_preview
