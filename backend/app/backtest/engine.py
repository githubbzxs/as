from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import BacktestJobRequest, BacktestReport, GoalConfig, RuntimeConfig
from app.services.goal_mapper import goal_to_runtime_config


@dataclass(slots=True)
class PricePoint:
    timestamp: datetime
    mid: float


def _to_datetime(raw: str) -> datetime:
    value = raw.strip()
    if not value:
        raise ValueError("时间字段为空")

    if value.isdigit():
        ts = int(value)
        if ts > 10_000_000_000:
            ts = ts / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _pick_first(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        if key in row and row[key] not in {None, ""}:
            return str(row[key])
    raise ValueError(f"缺少字段: {keys}")


def load_price_points(csv_file: Path) -> list[PricePoint]:
    if not csv_file.exists():
        raise FileNotFoundError(f"数据文件不存在: {csv_file}")

    points: list[PricePoint] = []
    with csv_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = _to_datetime(_pick_first(row, ["timestamp", "ts", "time", "datetime"]))
            mid = float(_pick_first(row, ["mid", "mid_price", "price", "close"]))
            if mid <= 0:
                continue
            points.append(PricePoint(timestamp=ts, mid=mid))

    if len(points) < 2:
        raise ValueError("回测数据不足，至少需要 2 条有效价格记录")
    points.sort(key=lambda p: p.timestamp)
    return points


def run_backtest(request: BacktestJobRequest) -> BacktestReport:
    points = load_price_points(Path(request.data_file))
    goal = GoalConfig(
        principal_usdt=request.principal_usdt,
        target_hourly_notional=request.target_hourly_notional,
        risk_profile=request.risk_profile,
        env_mode="testnet",
    )
    runtime = goal_to_runtime_config(goal, RuntimeConfig(symbol=request.symbol)).model_copy(
        update={"symbol": request.symbol}
    )

    quote_notional = max(1.0, runtime.max_single_order_notional)
    inventory_cap_notional = max(
        runtime.max_inventory_notional,
        request.principal_usdt * runtime.max_inventory_notional_pct,
    )

    fee_rate = -0.00005  # 简化模型：默认按 maker 返佣估计
    cash = request.principal_usdt
    position_base = 0.0
    fills = 0
    total_notional = 0.0
    max_inventory_notional = 0.0
    peak_equity = request.principal_usdt
    max_drawdown_pct = 0.0

    for idx in range(len(points) - 1):
        current = points[idx]
        nxt = points[idx + 1]
        mid = current.mid
        if mid <= 0:
            continue

        half_spread_ratio = runtime.min_spread_bps / 20000.0
        bid = mid * (1.0 - half_spread_ratio)
        ask = mid * (1.0 + half_spread_ratio)
        quote_size_base = max(runtime.min_order_size_base, quote_notional / mid)

        current_inventory_notional = position_base * mid
        only_sell = current_inventory_notional > inventory_cap_notional
        only_buy = current_inventory_notional < -inventory_cap_notional

        if not only_sell and nxt.mid <= bid:
            notional = bid * quote_size_base
            fee = notional * fee_rate
            cash -= notional + fee
            position_base += quote_size_base
            fills += 1
            total_notional += abs(notional)
        elif not only_buy and nxt.mid >= ask:
            notional = ask * quote_size_base
            fee = notional * fee_rate
            cash += notional - fee
            position_base -= quote_size_base
            fills += 1
            total_notional += abs(notional)

        inventory_abs = abs(position_base * nxt.mid)
        max_inventory_notional = max(max_inventory_notional, inventory_abs)
        equity = cash + position_base * nxt.mid
        peak_equity = max(peak_equity, equity)
        if peak_equity > 0:
            drawdown_pct = (peak_equity - equity) / peak_equity * 100.0
            max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)

    duration_hours = max((points[-1].timestamp - points[0].timestamp).total_seconds() / 3600.0, 1e-9)
    estimated_hourly_notional = total_notional / duration_hours
    target_completion_ratio = 0.0
    if request.target_hourly_notional > 0:
        target_completion_ratio = estimated_hourly_notional / request.target_hourly_notional

    final_equity = cash + position_base * points[-1].mid
    return BacktestReport(
        symbol=request.symbol,
        points=len(points),
        fills=fills,
        total_notional=total_notional,
        estimated_hourly_notional=estimated_hourly_notional,
        target_hourly_notional=request.target_hourly_notional,
        target_completion_ratio=target_completion_ratio,
        max_drawdown_pct=max_drawdown_pct,
        max_inventory_notional=max_inventory_notional,
        final_equity=final_equity,
        runtime_preview={
            "min_spread_bps": runtime.min_spread_bps,
            "max_spread_bps": runtime.max_spread_bps,
            "quote_interval_sec": runtime.quote_interval_sec,
            "max_single_order_notional": runtime.max_single_order_notional,
            "max_inventory_notional_pct": runtime.max_inventory_notional_pct,
            "drawdown_kill_pct": runtime.drawdown_kill_pct,
        },
        started_at=points[0].timestamp,
        ended_at=points[-1].timestamp,
    )
