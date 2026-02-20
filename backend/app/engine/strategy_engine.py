from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from app.engine.adaptive import AdaptiveController
from app.engine.as_model import AsMarketMakerModel
from app.engine.risk_guard import RiskGuard, RiskInput
from app.exchange.base import ExchangeAdapter
from app.models import EngineTick, OrderSnapshot, PositionSnapshot, QuoteDecision, utcnow
from app.schemas import HealthStatus, RuntimeConfig
from app.services.alerting import AlertService
from app.services.event_bus import EventBus
from app.services.monitoring import MonitoringService
from app.services.runtime_config import RuntimeConfigStore


@dataclass(slots=True)
class SyncResult:
    requoted: bool
    reason: str = "none"
    open_orders: list[OrderSnapshot] | None = None


class StrategyEngine:
    """做市主引擎。"""

    _MIN_NOTIONAL_BUFFER_RATIO = 1.05

    def __init__(
        self,
        adapter: ExchangeAdapter,
        config_store: RuntimeConfigStore,
        monitor: MonitoringService,
        event_bus: EventBus,
        alert_service: AlertService,
    ) -> None:
        self._adapter = adapter
        self._config_store = config_store
        self._monitor = monitor
        self._event_bus = event_bus
        self._alert = alert_service

        self._logger = logging.getLogger("engine")

        self._as_model = AsMarketMakerModel()
        self._adaptive = AdaptiveController(maxlen=2000)
        self._risk = RiskGuard()

        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

        self._mode: str = "idle"
        self._running: bool = False
        self._kill_reason: str | None = None
        self._last_error: str | None = None
        self._readonly_until: datetime | None = None

        self._initial_equity: float | None = None
        self._day_start_equity: float | None = None
        self._equity_day: date | None = None
        self._engine_started_at: datetime | None = None
        self._last_heartbeat_at: datetime | None = None
        self._inventory_side_mode: str | None = None
        self._consecutive_failures: int = 0
        self._last_status_at: datetime = utcnow()

        self._exchange_connected = False

    async def start(self) -> str:
        if self._running:
            return self._mode
        self._stop_event.clear()
        self._running = True
        self._kill_reason = None
        self._last_error = None
        self._consecutive_failures = 0
        self._initial_equity = None
        self._day_start_equity = None
        self._equity_day = None
        self._engine_started_at = utcnow()
        self._last_heartbeat_at = None
        self._inventory_side_mode = None
        self._risk.reset_peak(0.0)
        self._monitor.reset_session(started_at=self._engine_started_at)

        self._mode = "running"
        self._readonly_until = None

        self._task = asyncio.create_task(self._run_loop(), name="strategy-engine-loop")
        await self._event_bus.publish("engine", {"status": "started", "mode": self._mode})
        await self._alert.send_event(
            level="INFO",
            event="ENGINE_START",
            message="做市引擎已启动，开始自动做市",
        )
        return self._mode

    async def stop(self, reason: str = "manual") -> str:
        self._running = False
        self._stop_event.set()

        current = asyncio.current_task()
        if self._task and not self._task.done() and self._task is not current:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._task is not current:
            self._task = None

        cfg = self._config_store.get()
        await self._cancel_all_orders_safe(cfg.symbol, stage="stop")
        await self._flatten_position_until_done(cfg, trigger="stop")

        self._mode = "idle"
        self._last_status_at = utcnow()
        await self._event_bus.publish("engine", {"status": "stopped", "reason": reason, "mode": self._mode})
        await self._alert.send_event(
            level="INFO",
            event="ENGINE_STOP",
            message="引擎已停止并完成 taker 平仓",
            details={"reason": reason},
        )
        return self._mode

    async def halt(self, reason: str) -> None:
        self._kill_reason = reason
        self._mode = "halted"
        self._running = False
        self._stop_event.set()

        current = asyncio.current_task()
        if self._task and not self._task.done() and self._task is not current:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        cfg = self._config_store.get()
        await self._cancel_all_orders_safe(cfg.symbol, stage="halt")
        await self._flatten_position_until_done(cfg, trigger="halt")

        self._last_status_at = utcnow()
        await self._event_bus.publish("engine", {"status": "halted", "reason": reason, "mode": self._mode})
        await self._alert.send_event(
            level="CRITICAL",
            event="KILL_SWITCH",
            message=reason,
        )

    async def refresh_runtime_config(self) -> None:
        await self._event_bus.publish("config", self._config_store.get().model_dump())

    def replace_adapter(self, adapter: ExchangeAdapter) -> None:
        """切换交易所连接实例（仅应在非运行态调用）。"""
        self._adapter = adapter
        self._exchange_connected = False
        self._last_error = None

    def status(self) -> HealthStatus:
        cfg = self._config_store.get()
        return HealthStatus(
            engine_running=self._running,
            mode=self._mode,
            kill_reason=self._kill_reason,
            last_error=self._last_error,
            exchange_connected=self._exchange_connected,
            symbol=cfg.symbol,
            updated_at=self._last_status_at,
        )

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    async def _run_loop(self) -> None:
        cfg = self._config_store.get()

        try:
            self._exchange_connected = await self._adapter.ping()
        except Exception:
            self._exchange_connected = False

        if not self._exchange_connected:
            self._last_error = "交易所连接失败"
            await self.halt("启动失败：交易所不可达")
            return

        while not self._stop_event.is_set():
            tick_started = utcnow()
            cfg = self._config_store.get()
            effective_quote_interval = self._effective_quote_interval(cfg.quote_interval_sec)
            self._adaptive.set_windows(cfg.sigma_window_sec, effective_quote_interval)
            self._adaptive.set_sigma_baseline(cfg.as_sigma)

            try:
                loop_started_monotonic = time.perf_counter()

                fetch_market_started = time.perf_counter()
                market = await self._adapter.fetch_market_snapshot(cfg.symbol)
                fetch_market_ms = (time.perf_counter() - fetch_market_started) * 1000.0

                fetch_account_started = time.perf_counter()
                funds, position = await asyncio.gather(
                    self._adapter.fetch_account_funds(),
                    self._adapter.fetch_position(cfg.symbol),
                )
                fetch_account_ms = (time.perf_counter() - fetch_account_started) * 1000.0
                equity = float(funds.equity_usdt)
                free_usdt = float(funds.free_usdt)

                if self._initial_equity is None:
                    self._initial_equity = equity
                    self._risk.reset_peak(equity)
                self._refresh_daily_equity_anchor(equity)

                sigma, sigma_z = self._adaptive.update(market.mid, market.depth_score, market.trade_intensity)
                depth_factor = self._adaptive.depth_factor()
                intensity_factor = self._adaptive.intensity_factor()
                size_factor = self._adaptive.quote_size_factor()

                effective_capacity_notional = self._effective_capacity_notional(cfg, free_usdt)
                inventory_usage_ratio = abs(float(position.notional)) / max(effective_capacity_notional, 1e-9)
                max_inventory_notional_runtime = self._runtime_inventory_cap_notional(cfg, effective_capacity_notional)
                max_inventory_base = max_inventory_notional_runtime / max(market.mid, 1e-9)
                effective_equity_for_sizing = max(float(equity), 1.0)
                min_notional = max(
                    1e-6,
                    market.mid * cfg.min_order_size_base * self._MIN_NOTIONAL_BUFFER_RATIO,
                )
                risk_notional = effective_equity_for_sizing * cfg.equity_risk_pct
                base_quote_notional = min(
                    cfg.max_single_order_notional,
                    risk_notional,
                )
                quote_notional = max(min_notional, base_quote_notional * size_factor)
                effective_liquidity_k = self._effective_liquidity_k(cfg.liquidity_k, depth_factor)

                decision = self._as_model.compute_quote(
                    mid_price=market.mid,
                    sigma=sigma,
                    inventory_base=position.base_position,
                    max_inventory_base=max_inventory_base,
                    base_gamma=cfg.base_gamma,
                    gamma_min=cfg.gamma_min,
                    gamma_max=cfg.gamma_max,
                    liquidity_k=effective_liquidity_k,
                    horizon_sec=cfg.order_ttl_sec,
                    min_spread_bps=self._effective_min_spread_bps(
                        cfg.min_spread_bps,
                        cfg.max_spread_bps,
                        depth_factor,
                        intensity_factor,
                    ),
                    max_spread_bps=cfg.max_spread_bps,
                    quote_size_notional=quote_notional,
                )
                self._ensure_min_quote_size(decision, market.mid, cfg.min_order_size_base)
                price_tick = self._infer_price_tick(market.bid, market.ask)
                self._post_only_guard(market.bid, market.ask, decision, price_tick)

                sync_result = SyncResult(requoted=False, reason="none")
                sync_orders_ms = 0.0
                if self._mode == "running":
                    sync_started = time.perf_counter()
                    sync_result = await self._sync_orders(
                        cfg=cfg,
                        effective_capacity_notional=effective_capacity_notional,
                        position=position,
                        decision=decision,
                    )
                    sync_orders_ms = (time.perf_counter() - sync_started) * 1000.0
                    if sync_result.requoted:
                        self._monitor.record_cancel(utcnow())

                if sync_result.open_orders is None:
                    open_orders, recent_trades = await asyncio.gather(
                        self._adapter.fetch_open_orders(cfg.symbol),
                        self._adapter.fetch_recent_trades(cfg.symbol, 100),
                    )
                else:
                    open_orders = sync_result.open_orders
                    recent_trades = await self._adapter.fetch_recent_trades(cfg.symbol, 100)
                self._monitor.update_orders(open_orders)
                self._monitor.update_trades(recent_trades)

                pnl_total = equity - (self._initial_equity or equity)
                pnl_daily = equity - (self._day_start_equity or equity)
                drawdown = self._risk.update_drawdown(equity)
                distance_bid_bps = self._distance_from_bid_bps(market.bid, decision.bid_price)
                distance_ask_bps = self._distance_from_ask_bps(market.ask, decision.ask_price)
                now = utcnow()
                engine_tick = EngineTick(
                    timestamp=now,
                    market=market,
                    decision=decision,
                    position=position,
                    equity=equity,
                    pnl=pnl_total,
                    pnl_total=pnl_total,
                    pnl_daily=pnl_daily,
                    sigma=sigma,
                    sigma_zscore=sigma_z,
                    free_usdt=free_usdt,
                    effective_capacity_notional=effective_capacity_notional,
                    inventory_usage_ratio=inventory_usage_ratio,
                    effective_liquidity_k=effective_liquidity_k,
                    distance_bid_bps=distance_bid_bps,
                    distance_ask_bps=distance_ask_bps,
                )
                self._monitor.update_tick(
                    engine_tick,
                    drawdown,
                    self._mode,
                    self._consecutive_failures,
                    requote_reason=sync_result.reason,
                )

                summary = self._monitor.summary
                loop_elapsed_ms = (time.perf_counter() - loop_started_monotonic) * 1000.0
                await self._event_bus.publish(
                    "tick",
                    {
                        "summary": summary.model_dump(mode="json"),
                        "open_orders": [
                            {
                                "order_id": o.order_id,
                                "side": o.side,
                                "price": o.price,
                                "size": o.size,
                                "status": o.status,
                                "created_at": o.created_at.isoformat(),
                            }
                            for o in open_orders
                        ],
                        "diagnostics": {
                            "target_bid": decision.bid_price,
                            "target_ask": decision.ask_price,
                            "distance_bid_bps": distance_bid_bps,
                            "distance_ask_bps": distance_ask_bps,
                            "requote_reason": sync_result.reason,
                            "open_order_age_buy_sec": summary.open_order_age_buy_sec,
                            "open_order_age_sell_sec": summary.open_order_age_sell_sec,
                            "max_inventory_notional_runtime": max_inventory_notional_runtime,
                            "free_usdt": free_usdt,
                            "effective_capacity_notional": effective_capacity_notional,
                            "inventory_usage_ratio": inventory_usage_ratio,
                            "effective_liquidity_k": effective_liquidity_k,
                            "funds_source": funds.source,
                            "inventory_side_mode": self._inventory_side_mode or "both",
                            "loop_elapsed_ms": round(loop_elapsed_ms, 3),
                            "fetch_market_ms": round(fetch_market_ms, 3),
                            "fetch_account_ms": round(fetch_account_ms, 3),
                            "sync_orders_ms": round(sync_orders_ms, 3),
                        },
                    },
                )

                await self._maybe_send_heartbeat(cfg, summary)

                risk_result = self._risk.evaluate(
                    RiskInput(
                        equity=equity,
                        drawdown_pct=drawdown,
                        sigma_zscore=sigma_z,
                        consecutive_failures=self._consecutive_failures,
                    ),
                    drawdown_kill_pct=cfg.drawdown_kill_pct,
                    volatility_kill_zscore=cfg.volatility_kill_zscore,
                    max_consecutive_failures=cfg.max_consecutive_failures,
                )
                if risk_result.triggered:
                    await self.halt(risk_result.reason or "未知熔断")
                    break

                self._last_status_at = utcnow()
                self._last_error = None
                self._exchange_connected = True
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._consecutive_failures += 1
                category = self._classify_error(exc)
                self._last_error = f"[{category}] {exc}"
                self._last_status_at = utcnow()
                self._exchange_connected = False
                self._logger.exception("涓诲惊鐜紓甯?%s): %s", category, exc)
                await self._event_bus.publish(
                    "error",
                    {
                        "message": str(exc),
                        "category": category,
                        "consecutive_failures": self._consecutive_failures,
                    },
                )
                await self._alert.send_event(
                    level="WARN",
                    event="ENGINE_ERROR",
                    message=f"[{category}] {exc}",
                    dedupe_key=f"engine-error-{category}",
                    min_interval_sec=60,
                )

            elapsed = (utcnow() - tick_started).total_seconds()
            sleep_for = max(0.01, effective_quote_interval - elapsed)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass

    @staticmethod
    def _effective_min_spread_bps(
        min_spread_bps: float,
        max_spread_bps: float,
        depth_factor: float,
        intensity_factor: float,
    ) -> float:
        effective = min_spread_bps * depth_factor * intensity_factor
        return max(0.1, min(effective, max(max_spread_bps - 0.05, 0.1)))

    @staticmethod
    def _effective_quote_interval(base_interval: float) -> float:
        return max(0.2, min(base_interval, 10.0))


    async def _cancel_all_orders_safe(self, symbol: str, stage: str) -> None:
        try:
            await self._adapter.cancel_all_orders(symbol)
        except Exception as exc:
            self._logger.warning("%s 鏃舵挙鍗曞け璐? %s", stage, exc)

    async def _flatten_position_until_done(self, cfg: RuntimeConfig, trigger: str) -> None:
        retries = 0
        delay = cfg.close_retry_base_delay_sec
        while True:
            try:
                pos = await self._adapter.fetch_position(cfg.symbol)
                pos_size = abs(float(pos.base_position))
                if pos_size <= cfg.close_position_epsilon_base:
                    await self._event_bus.publish(
                        "close_done",
                        {
                            "symbol": cfg.symbol,
                            "trigger": trigger,
                            "retries": retries,
                            "remaining_base": pos_size,
                        },
                    )
                    await self._alert.send_event(
                        level="INFO",
                        event="POSITION_FLAT",
                        message="仓位已完成 taker 平仓",
                        details={
                            "trigger": trigger,
                            "symbol": cfg.symbol,
                            "retries": retries,
                        },
                    )
                    return

                await self._adapter.flatten_position_taker(cfg.symbol)
                retries += 1
                await self._event_bus.publish(
                    "close_attempt",
                    {
                        "symbol": cfg.symbol,
                        "trigger": trigger,
                        "attempt": retries,
                        "position_base": pos.base_position,
                    },
                )
            except Exception as exc:
                retries += 1
                self._logger.exception("taker 平仓失败(%s) attempt=%s: %s", trigger, retries, exc)
                await self._event_bus.publish(
                    "close_retry",
                    {
                        "symbol": cfg.symbol,
                        "trigger": trigger,
                        "attempt": retries,
                        "error": str(exc),
                    },
                )
                await self._alert.send_event(
                    level="WARN",
                    event="POSITION_FLATTEN_RETRY",
                    message="taker 平仓失败，继续重试",
                    details={
                        "trigger": trigger,
                        "attempt": retries,
                        "error": str(exc),
                    },
                    dedupe_key=f"flatten-retry-{trigger}",
                    min_interval_sec=60,
                )

            await asyncio.sleep(min(delay, cfg.close_retry_max_delay_sec))
            delay = min(cfg.close_retry_max_delay_sec, max(cfg.close_retry_base_delay_sec, delay * 2))

    async def _maybe_send_heartbeat(self, cfg: RuntimeConfig, summary) -> None:
        if not cfg.tg_heartbeat_enabled:
            return
        now = utcnow()
        if self._last_heartbeat_at is not None:
            if (now - self._last_heartbeat_at).total_seconds() < cfg.tg_heartbeat_interval_sec:
                return
        self._last_heartbeat_at = now
        await self._alert.send_event(
            level="INFO",
            event="HEARTBEAT",
            message="运行状态摘要",
            details={
                "mode": summary.mode,
                "equity": round(summary.equity, 6),
                "pnl_total": round(summary.pnl_total, 6),
                "pnl_daily": round(summary.pnl_daily, 6),
                "inventory_notional": round(summary.inventory_notional, 6),
                "run_duration_sec": round(summary.run_duration_sec, 2),
                "total_trade_volume_notional": round(summary.total_trade_volume_notional, 6),
                "total_fee_rebate": round(summary.total_fee_rebate, 6),
                "total_fee_cost": round(summary.total_fee_cost, 6),
            },
            dedupe_key="heartbeat",
            min_interval_sec=cfg.tg_heartbeat_interval_sec,
        )

    def _refresh_daily_equity_anchor(self, equity: float) -> None:
        today = utcnow().date()
        if self._equity_day != today or self._day_start_equity is None:
            self._equity_day = today
            self._day_start_equity = equity

    @staticmethod
    def _runtime_inventory_cap_notional(cfg: RuntimeConfig, effective_capacity_notional: float) -> float:
        if cfg.max_inventory_notional_pct > 0:
            return max(0.0, effective_capacity_notional * cfg.max_inventory_notional_pct)
        return max(0.0, cfg.max_inventory_notional)

    @staticmethod
    def _effective_capacity_notional(cfg: RuntimeConfig, free_usdt: float) -> float:
        leverage = max(1.0, float(cfg.effective_leverage))
        return max(1e-6, max(0.0, float(free_usdt)) * leverage)

    @staticmethod
    def _effective_liquidity_k(base_k: float, depth_factor: float) -> float:
        baseline = max(1e-6, float(base_k))
        scaled = baseline * max(0.1, float(depth_factor))
        return max(baseline * 0.5, min(baseline * 2.0, scaled))

    def _post_only_guard(self, bid: float, ask: float, decision: QuoteDecision, price_tick: float) -> None:
        min_tick = max(0.0001, price_tick)
        decision.bid_price = min(decision.bid_price, ask - min_tick)
        decision.ask_price = max(decision.ask_price, bid + min_tick)
        if decision.bid_price >= decision.ask_price:
            decision.ask_price = decision.bid_price + min_tick
        decision.bid_price = self._round_price_by_tick(decision.bid_price, min_tick, "down")
        decision.ask_price = self._round_price_by_tick(decision.ask_price, min_tick, "up")
        if decision.bid_price >= decision.ask_price:
            decision.ask_price = self._round_price_by_tick(decision.bid_price + min_tick, min_tick, "up")

    async def _sync_orders(
        self,
        *,
        cfg: RuntimeConfig,
        effective_capacity_notional: float,
        position: PositionSnapshot,
        decision: QuoteDecision,
    ) -> SyncResult:
        orders = await self._adapter.fetch_open_orders(cfg.symbol)
        now = utcnow()
        buy_order = self._latest_order_by_side(orders, "buy")
        sell_order = self._latest_order_by_side(orders, "sell")

        only_buy, only_sell = self._resolve_inventory_side_mode(
            cfg,
            position.notional,
            effective_capacity_notional,
        )
        desired_sides: set[str] = {"buy", "sell"}
        if only_buy:
            desired_sides = {"buy"}
        elif only_sell:
            desired_sides = {"sell"}

        reasons: list[str] = []
        requoted = False

        if only_buy or only_sell:
            reasons.append("inventory-limit")

        if buy_order and "buy" not in desired_sides:
            await self._cancel_order_silent(cfg.symbol, buy_order.order_id)
            buy_order = None
            reasons.append("inventory-exit-buy")
            requoted = True
        if sell_order and "sell" not in desired_sides:
            await self._cancel_order_silent(cfg.symbol, sell_order.order_id)
            sell_order = None
            reasons.append("inventory-exit-sell")
            requoted = True

        if "buy" in desired_sides:
            side_reasons, side_changed = await self._ensure_side_order(
                cfg=cfg,
                side="buy",
                now=now,
                existing=buy_order,
                target_price=decision.bid_price,
                target_size=decision.quote_size_base,
            )
            reasons.extend(side_reasons)
            requoted = requoted or side_changed
        if "sell" in desired_sides:
            side_reasons, side_changed = await self._ensure_side_order(
                cfg=cfg,
                side="sell",
                now=now,
                existing=sell_order,
                target_price=decision.ask_price,
                target_size=decision.quote_size_base,
            )
            reasons.extend(side_reasons)
            requoted = requoted or side_changed

        if not requoted:
            return SyncResult(requoted=False, reason="none", open_orders=orders)

        try:
            self._consecutive_failures = 0
            refreshed_orders = await self._adapter.fetch_open_orders(cfg.symbol)
            reason_text = ",".join(dict.fromkeys(reasons)) if reasons else "none"
            return SyncResult(requoted=True, reason=reason_text, open_orders=refreshed_orders)
        except Exception:
            self._consecutive_failures += 1
            raise

    def _resolve_inventory_side_mode(
        self,
        cfg: RuntimeConfig,
        inventory_notional: float,
        effective_capacity_notional: float,
    ) -> tuple[bool, bool]:
        safe_capacity = max(abs(float(effective_capacity_notional)), 1e-9)
        usage_ratio = abs(float(inventory_notional)) / safe_capacity
        trigger_ratio = max(0.0, float(cfg.max_inventory_equity_ratio))
        recover_ratio = max(0.0, min(float(cfg.single_side_recover_ratio), trigger_ratio))

        if self._inventory_side_mode == "only_sell" and inventory_notional < 0:
            self._inventory_side_mode = "only_buy"
        elif self._inventory_side_mode == "only_buy" and inventory_notional > 0:
            self._inventory_side_mode = "only_sell"

        if self._inventory_side_mode is not None and usage_ratio <= recover_ratio:
            self._inventory_side_mode = None

        if self._inventory_side_mode is None and usage_ratio >= trigger_ratio:
            if inventory_notional > 0:
                self._inventory_side_mode = "only_sell"
            elif inventory_notional < 0:
                self._inventory_side_mode = "only_buy"

        return self._inventory_side_mode == "only_buy", self._inventory_side_mode == "only_sell"

    async def _ensure_side_order(
        self,
        *,
        cfg: RuntimeConfig,
        side: str,
        now: datetime,
        existing: OrderSnapshot | None,
        target_price: float,
        target_size: float,
    ) -> tuple[list[str], bool]:
        reasons: list[str] = []
        if existing is None:
            reasons.append(f"missing-side-{side}")
            await self._adapter.place_limit_order(
                symbol=cfg.symbol,
                side=side,
                price=target_price,
                size=target_size,
                post_only=True,
                client_order_id=self._new_client_order_id(side),
            )
            return reasons, True

        order_age = max(0.0, (now - existing.created_at).total_seconds())
        ttl_expired = order_age > cfg.order_ttl_sec
        price_dev = self._price_deviation_bps(existing.price, target_price) > cfg.requote_threshold_bps
        size_dev = self._size_deviation_ratio(existing.size, target_size) > cfg.requote_size_threshold_ratio

        if ttl_expired:
            reasons.append("ttl-expired")
        if price_dev:
            reasons.append(f"price-deviation-{side}")
        if size_dev:
            reasons.append(f"size-deviation-{side}")

        should_replace = ttl_expired or ((price_dev or size_dev) and order_age >= cfg.min_order_age_before_requote_sec)
        if not should_replace:
            return [], False

        # 先挂新单再撤旧单，尽量避免该侧出现“真空窗口”。
        await self._adapter.place_limit_order(
            symbol=cfg.symbol,
            side=side,
            price=target_price,
            size=target_size,
            post_only=True,
            client_order_id=self._new_client_order_id(side),
        )
        await self._cancel_order_silent(cfg.symbol, existing.order_id)
        return reasons, True

    async def _cancel_order_silent(self, symbol: str, order_id: str) -> None:
        try:
            await self._adapter.cancel_order(symbol, order_id)
        except Exception as exc:
            self._logger.warning("撤单失败(order_id=%s): %s", order_id, exc)

    @staticmethod
    def _latest_order_by_side(orders: list[OrderSnapshot], side: str) -> OrderSnapshot | None:
        candidates = [o for o in orders if o.side == side]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.created_at)

    @staticmethod
    def _collect_requote_reasons(
        *,
        buy_order,
        sell_order,
        only_sell: bool,
        only_buy: bool,
        buy_dev: bool,
        sell_dev: bool,
        buy_size_dev: bool,
        sell_size_dev: bool,
        ttl_expired: bool,
    ) -> list[str]:
        reasons: list[str] = []
        if only_sell or only_buy:
            reasons.append("inventory-limit")
        if not buy_order and not only_sell:
            reasons.append("missing-side-buy")
        if not sell_order and not only_buy:
            reasons.append("missing-side-sell")
        if buy_dev:
            reasons.append("price-deviation-buy")
        if sell_dev:
            reasons.append("price-deviation-sell")
        if buy_size_dev:
            reasons.append("size-deviation-buy")
        if sell_size_dev:
            reasons.append("size-deviation-sell")
        if ttl_expired:
            reasons.append("ttl-expired")
        return reasons

    @staticmethod
    def _new_client_order_id(side: str) -> str:
        # 使用较短的纯数字，避免交易所侧整数精度与类型转换导致重复判定。
        side_flag = "1" if side == "buy" else "2"
        nonce_ms = int(utcnow().timestamp() * 1_000)
        suffix = uuid.uuid4().int % 10_000
        return f"{side_flag}{nonce_ms}{suffix:04d}"

    @staticmethod
    def _classify_error(exc: Exception) -> str:
        text = str(exc).lower()
        if "event_time" in text or "malformed syntax" in text or "order_book" in text or "ticker" in text:
            return "market_data"
        if "invalid literal for int" in text or "order_id" in text:
            return "order_id"
        if "trading_account_id" in text or "api_key" in text or "unauthorized" in text or "forbidden" in text:
            return "auth"
        return "unknown"

    @staticmethod
    def _price_deviation_bps(old: float, new: float) -> float:
        if old <= 0:
            return math.inf
        return abs(new - old) / old * 10000

    @staticmethod
    def _size_deviation_ratio(old: float, new: float) -> float:
        baseline = max(abs(float(old)), abs(float(new)), 1e-9)
        return abs(float(new) - float(old)) / baseline

    @staticmethod
    def _distance_from_bid_bps(best_bid: float, bid_price: float) -> float:
        if best_bid <= 0:
            return 0.0
        return max(0.0, (best_bid - bid_price) / best_bid * 10000)

    @staticmethod
    def _distance_from_ask_bps(best_ask: float, ask_price: float) -> float:
        if best_ask <= 0:
            return 0.0
        return max(0.0, (ask_price - best_ask) / best_ask * 10000)

    @staticmethod
    def _ensure_min_quote_size(decision: QuoteDecision, mid_price: float, min_size_base: float) -> None:
        if min_size_base <= 0:
            return
        if decision.quote_size_base >= min_size_base:
            return
        decision.quote_size_base = min_size_base
        decision.quote_size_notional = min_size_base * max(mid_price, 1e-9)

    @staticmethod
    def _infer_price_tick(bid: float, ask: float) -> float:
        tick = 0.0001
        for price in (bid, ask):
            txt = f"{price:.10f}".rstrip("0").rstrip(".")
            if "." not in txt:
                continue
            decimals = len(txt.split(".")[1])
            tick = max(tick, 10 ** (-decimals))
        return tick

    @staticmethod
    def _round_price_by_tick(price: float, tick: float, side: str) -> float:
        if tick <= 0:
            return max(0.0001, price)
        unit = price / tick
        if side == "down":
            rounded = math.floor(unit + 1e-12) * tick
        else:
            rounded = math.ceil(unit - 1e-12) * tick
        return max(0.0001, rounded)
