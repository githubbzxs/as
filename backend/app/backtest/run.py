from __future__ import annotations

import argparse
import json

from app.backtest.engine import run_backtest
from app.schemas import BacktestJobRequest


def main() -> int:
    parser = argparse.ArgumentParser(description="简化回测运行器")
    parser.add_argument("--data", required=True, help="CSV 数据文件路径")
    parser.add_argument("--symbol", default="BNB_USDT_Perp", help="交易对")
    parser.add_argument("--principal", type=float, default=10.0, help="本金(USDT)")
    parser.add_argument("--target-hourly", type=float, default=10000.0, help="目标小时交易量(USDT)")
    parser.add_argument(
        "--risk-profile",
        choices=["safe", "balanced", "throughput"],
        default="throughput",
        help="风险档位",
    )
    parser.add_argument("--out", default="", help="结果输出 JSON 文件路径（可选）")
    args = parser.parse_args()

    request = BacktestJobRequest(
        data_file=args.data,
        symbol=args.symbol,
        principal_usdt=args.principal,
        target_hourly_notional=args.target_hourly,
        risk_profile=args.risk_profile,
    )
    report = run_backtest(request)
    payload = report.model_dump(mode="json")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(f"回测完成，结果已写入: {args.out}")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
