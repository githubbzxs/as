from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import uuid
from datetime import datetime, timedelta

from app.engine.adaptive import AdaptiveController
from app.engine.as_model import AsMarketMakerModel
from app.engine.risk_guard import RiskGuard, RiskInput
from app.exchange.base import ExchangeAdapter
from app.models import EngineTick, PositionSnapshot, QuoteDecision, utcnow
from app.schemas import HealthStatus, RuntimeConfig
from app.services.alerting import AlertService
from app.services.event_bus import EventBus
from app.services.monitoring import MonitoringService
from app.services.runtime_config import RuntimeConfigStore


class StrategyEngine:
    """做市主引擎。"""

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

        cfg = self._config_store.get()
        self._mode = "readonly"
        self._readonly_until = utcnow() + timedelta(seconds=cfg.recovery_readonly_sec)

        self._task = asyncio.create_task(self._run_loop(), name="strategy-engine-loop")
        await self._event_bus.publish("engine", {"status": "started", "mode": self._mode})
        await self._alert.send("Engine", "做市引擎已启动，进入只读预热阶段")
        return self._mode

    async def stop(self, reason: str = "manual") -> str:
        self._running = False
        self._stop_event.set()
        self._mode = "idle"
        try:
            cfg = self._config_store.get()
            await self._adapter.cancel_all_orders(cfg.symbol)
        except Exception as exc:
            self._logger.warning("停止时撤单失败: %s", exc)

        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None

        await self._event_bus.publish("engine", {"status": "stopped", "reason": reason, "mode": self._mode})
        return self._mode

    async def halt(self, reason: str) -> None:
        self._kill_reason = reason
        self._mode = "halted"
        self._running = False
        self._stop_event.set()

        cfg = self._config_store.get()
        try:
            await self._adapter.cancel_all_orders(cfg.symbol)
        except Exception as exc:
            self._logger.warning("熔断撤单失败: %s", exc)

        await self._event_bus.publish("engine", {"status": "halted", "reason": reason, "mode": self._mode})
        await self._alert.send("KillSwitch", reason)

    async def refresh_runtime_config(self) -> None:
        await self._event_bus.publish("config", self._config_store.get().model_dump())

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

            try:
                market = await self._adapter.fetch_market_snapshot(cfg.symbol)
                equity = await self._adapter.fetch_equity()
                position = await self._adapter.fetch_position(cfg.symbol)

                if self._initial_equity is None:
                    self._initial_equity = equity
                    self._risk.reset_peak(equity)

                sigma, sigma_z = self._adaptive.update(market.mid, market.depth_score, market.trade_intensity)
                depth_factor = self._adaptive.depth_factor()
                intensity_factor = self._adaptive.intensity_factor()
                size_factor = self._adaptive.quote_size_factor()

                max_inventory_base = cfg.max_inventory_notional / max(market.mid, 1e-9)
                base_quote_notional = min(
                    cfg.max_single_order_notional,
                    max(1.0, equity * cfg.equity_risk_pct * 0.5),
                )
                quote_notional = max(5.0, base_quote_notional * size_factor)

                decision = self._as_model.compute_quote(
                    mid_price=market.mid,
                    sigma=sigma,
                    inventory_base=position.base_position,
                    max_inventory_base=max_inventory_base,
                    base_gamma=cfg.base_gamma,
                    gamma_min=cfg.gamma_min,
                    gamma_max=cfg.gamma_max,
                    liquidity_k=cfg.liquidity_k,
                    horizon_sec=cfg.order_ttl_sec,
                    min_spread_bps=cfg.min_spread_bps * depth_factor * intensity_factor,
                    max_spread_bps=cfg.max_spread_bps,
                    quote_size_notional=quote_notional,
                )
                self._post_only_guard(market.bid, market.ask, decision)

                if self._mode == "readonly" and self._readonly_until and utcnow() >= self._readonly_until:
                    self._mode = "running"
                    await self._alert.send("Engine", "只读预热结束，开始自动做市")

                if self._mode == "running":
                    await self._sync_orders(cfg, position, decision)

                pnl = equity - (self._initial_equity or equity)
                drawdown = self._risk.update_drawdown(equity)
                engine_tick = EngineTick(
                    timestamp=utcnow(),
                    market=market,
                    decision=decision,
                    position=position,
                    equity=equity,
                    pnl=pnl,
                    sigma=sigma,
                    sigma_zscore=sigma_z,
                )
                self._monitor.update_tick(engine_tick, drawdown, self._mode, self._consecutive_failures)

                open_orders = await self._adapter.fetch_open_orders(cfg.symbol)
                recent_trades = await self._adapter.fetch_recent_trades(cfg.symbol, 100)
                self._monitor.update_orders(open_orders)
                self._monitor.update_trades(recent_trades)

                await self._event_bus.publish(
                    "tick",
                    {
                        "summary": self._monitor.summary.model_dump(mode="json"),
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
                    },
                )

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
                self._last_error = str(exc)
                self._last_status_at = utcnow()
                self._exchange_connected = False
                self._logger.exception("主循环异常: %s", exc)
                await self._event_bus.publish(
                    "error",
                    {
                        "message": str(exc),
                        "consecutive_failures": self._consecutive_failures,
                    },
                )
                await self._alert.send("EngineError", str(exc))

            elapsed = (utcnow() - tick_started).total_seconds()
            sleep_for = max(0.01, cfg.quote_interval_sec - elapsed)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass

    def _post_only_guard(self, bid: float, ask: float, decision: QuoteDecision) -> None:
        min_tick = max(0.0001, decision.reservation_price * 0.00001)
        decision.bid_price = min(decision.bid_price, ask - min_tick)
        decision.ask_price = max(decision.ask_price, bid + min_tick)
        if decision.bid_price >= decision.ask_price:
            decision.ask_price = decision.bid_price + min_tick

    async def _sync_orders(self, cfg: RuntimeConfig, position: PositionSnapshot, decision: QuoteDecision) -> None:
        orders = await self._adapter.fetch_open_orders(cfg.symbol)
        buy_order = next((o for o in orders if o.side == "buy"), None)
        sell_order = next((o for o in orders if o.side == "sell"), None)

        max_inventory = cfg.max_inventory_notional
        only_sell = position.notional > max_inventory
        only_buy = position.notional < -max_inventory

        need_requote = False
        if not buy_order and not only_sell:
            need_requote = True
        if not sell_order and not only_buy:
            need_requote = True

        if buy_order and self._price_deviation_bps(buy_order.price, decision.bid_price) > cfg.requote_threshold_bps:
            need_requote = True
        if sell_order and self._price_deviation_bps(sell_order.price, decision.ask_price) > cfg.requote_threshold_bps:
            need_requote = True

        ttl_expired = any((utcnow() - o.created_at).total_seconds() > cfg.order_ttl_sec for o in orders)
        if ttl_expired:
            need_requote = True

        if not need_requote:
            return

        await self._adapter.cancel_all_orders(cfg.symbol)

        try:
            if not only_sell:
                await self._adapter.place_limit_order(
                    symbol=cfg.symbol,
                    side="buy",
                    price=decision.bid_price,
                    size=decision.quote_size_base,
                    post_only=True,
                    client_order_id=f"bid-{uuid.uuid4().hex[:16]}",
                )
            if not only_buy:
                await self._adapter.place_limit_order(
                    symbol=cfg.symbol,
                    side="sell",
                    price=decision.ask_price,
                    size=decision.quote_size_base,
                    post_only=True,
                    client_order_id=f"ask-{uuid.uuid4().hex[:16]}",
                )
            self._consecutive_failures = 0
        except Exception:
            self._consecutive_failures += 1
            raise

    @staticmethod
    def _price_deviation_bps(old: float, new: float) -> float:
        if old <= 0:
            return math.inf
        return abs(new - old) / old * 10000
